from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any

from pydantic import ValidationError

from src.config.llm_config import (
    ADDRESS_MATCH_PROMPT,
    COMPANY_NAME_MATCH_PROMPT,
    FUZZY_MATCH_PROMPT,
    REVIEW_SUMMARY_PROMPT,
    VENDOR_NAME_MATCH_PROMPT,
)
from src.config.settings import settings
from src.core.exceptions.llm_exc import LLMServiceError
from src.schemas.semantic_match_schema import (
    FuzzyMatchResult,
    SemanticMatchResult,
)

_GROQ_HTTP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (compatible; ValidationService/1.0; "
        "+https://api.groq.com)"
    ),
}


def extract_json_text(
    response_text: str,
) -> str:
    stripped_text = response_text.strip()

    if stripped_text.startswith(
        "{",
    ) or stripped_text.startswith(
        "[",
    ):
        return stripped_text

    fenced_match = re.search(
        r"```(?:json)?\s*([\s\S]*?)\s*```",
        stripped_text,
    )

    if fenced_match:
        return fenced_match.group(
            1,
        ).strip()

    return stripped_text


def _validate_groq_configuration() -> None:
    if not settings.GROQ_API_KEY:
        raise LLMServiceError(
            "GROQ_API_KEY is not configured",
            provider="groq",
        )


def _build_llm_error_detail(
    status_code: int,
    error_body: str,
) -> str:
    if status_code in (401, 403):
        if error_body.strip():
            return (
                "Groq API key is invalid or unauthorized: "
                f"{error_body.strip()}"
            )

        return "Groq API key is invalid or unauthorized."

    if error_body.strip():
        return (
            f"Groq API request failed with HTTP "
            f"{status_code}: {error_body.strip()}"
        )

    return f"Groq API request failed with HTTP {status_code}."


def _post_groq_json(
    request_body: dict[str, Any],
    *,
    api_key: str,
    timeout: int = 60,
) -> dict[str, Any]:
    headers = {
        **_GROQ_HTTP_HEADERS,
        "Authorization": f"Bearer {api_key}",
    }
    request = urllib.request.Request(
        url=(
            f"{settings.GROQ_API_BASE_URL.rstrip('/')}"
            "/chat/completions"
        ),
        data=json.dumps(
            request_body,
        ).encode(
            "utf-8",
        ),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            return json.loads(
                response.read().decode(
                    "utf-8",
                ),
            )
    except urllib.error.HTTPError as error:
        error_body = error.read().decode(
            "utf-8",
        )

        raise LLMServiceError(
            _build_llm_error_detail(
                status_code=error.code,
                error_body=error_body,
            ),
            provider="groq",
            status_code=error.code,
        ) from error


def _extract_chat_completion_text(
    response_payload: dict[str, Any],
) -> str:
    choices = response_payload.get(
        "choices",
        [],
    )

    if not choices:
        raise LLMServiceError(
            "LLM response did not contain choices",
            provider="groq",
        )

    choice = choices[0]
    message = choice.get(
        "message",
        {},
    )
    content = message.get(
        "content",
        "",
    )

    if not content:
        raise LLMServiceError(
            "LLM response did not contain content",
            provider="groq",
        )

    return extract_json_text(
        str(content).strip(),
    )


def _call_groq_llm(
    prompt: str,
    *,
    max_retries: int = 2,
) -> str:
    _validate_groq_configuration()

    request_body: dict[str, Any] = {
        "model": settings.GROQ_LLM_MODEL,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"{prompt}\n\n"
                    "Return valid JSON only."
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": settings.GROQ_LLM_MAX_TOKENS,
        "response_format": {
            "type": "json_object",
        },
    }

    last_error: LLMServiceError | None = None

    for attempt in range(
        max_retries + 1,
    ):
        try:
            response_payload = _post_groq_json(
                request_body,
                api_key=settings.GROQ_API_KEY,
            )

            return _extract_chat_completion_text(
                response_payload,
            )
        except LLMServiceError as error:
            last_error = error

            if (
                attempt < max_retries
                and error.status_code in {413, 429}
            ):
                time.sleep(
                    5 * (attempt + 1),
                )
                continue

            raise

    if last_error is not None:
        raise last_error

    raise LLMServiceError(
        "Groq API request failed.",
        provider="groq",
    )


def _call_groq_plain_text(
    prompt: str,
    *,
    max_retries: int = 2,
) -> str:
    _validate_groq_configuration()

    request_body: dict[str, Any] = {
        "model": settings.GROQ_LLM_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0,
        "max_tokens": settings.GROQ_LLM_MAX_TOKENS,
    }

    last_error: LLMServiceError | None = None

    for attempt in range(
        max_retries + 1,
    ):
        try:
            response_payload = _post_groq_json(
                request_body,
                api_key=settings.GROQ_API_KEY,
            )

            choices = response_payload.get(
                "choices",
                [],
            )

            if not choices:
                raise LLMServiceError(
                    "LLM response did not contain choices",
                    provider="groq",
                )

            content = choices[0].get(
                "message",
                {},
            ).get(
                "content",
                "",
            )

            if not content:
                raise LLMServiceError(
                    "LLM response did not contain content",
                    provider="groq",
                )

            return str(
                content,
            ).strip()
        except LLMServiceError as error:
            last_error = error

            if (
                attempt < max_retries
                and error.status_code in {413, 429}
            ):
                time.sleep(
                    5 * (attempt + 1),
                )
                continue

            raise

    if last_error is not None:
        raise last_error

    raise LLMServiceError(
        "Groq API request failed.",
        provider="groq",
    )


def _parse_semantic_match(
    response_text: str,
) -> SemanticMatchResult:
    json_text = extract_json_text(
        response_text,
    )

    try:
        return SemanticMatchResult.model_validate_json(
            json_text,
        )
    except ValidationError as error:
        preview = json_text[:200]
        raise LLMServiceError(
            "LLM returned invalid semantic match JSON: "
            f"{error}. Preview: {preview}",
            provider="groq",
        ) from error


_FUZZY_MATCH_CONFIDENCE_THRESHOLD = 0.90


def _parse_fuzzy_match(
    response_text: str,
) -> FuzzyMatchResult:
    json_text = extract_json_text(
        response_text,
    )

    try:
        return FuzzyMatchResult.model_validate_json(
            json_text,
        )
    except ValidationError as error:
        preview = json_text[:200]
        raise LLMServiceError(
            "LLM returned invalid fuzzy match JSON: "
            f"{error}. Preview: {preview}",
            provider="groq",
        ) from error


def _apply_fuzzy_match_threshold(
    result: FuzzyMatchResult,
) -> SemanticMatchResult:
    if (
        result.is_match
        and result.confidence
        <= _FUZZY_MATCH_CONFIDENCE_THRESHOLD
    ):
        return SemanticMatchResult(
            is_match=False,
            reason=(
                f"Confidence {result.confidence:.2f} is below the "
                f"automatic match threshold "
                f"({_FUZZY_MATCH_CONFIDENCE_THRESHOLD:.2f}). "
                f"{result.reason}"
            ).strip(),
        )

    return SemanticMatchResult(
        is_match=result.is_match,
        reason=result.reason,
    )


def compare_company_names_semantically(
    extracted: str,
    master: str,
) -> SemanticMatchResult:
    prompt = COMPANY_NAME_MATCH_PROMPT.format(
        extracted=extracted,
        master=master,
    )
    response_text = _call_groq_llm(
        prompt,
    )

    return _parse_semantic_match(
        response_text,
    )


def compare_addresses_semantically(
    extracted: str,
    master: str,
) -> SemanticMatchResult:
    prompt = ADDRESS_MATCH_PROMPT.format(
        extracted=extracted,
        master=master,
    )
    response_text = _call_groq_llm(
        prompt,
    )

    return _parse_semantic_match(
        response_text,
    )


def compare_vendor_names_semantically(
    extracted: str,
    master: str,
) -> SemanticMatchResult:
    prompt = VENDOR_NAME_MATCH_PROMPT.format(
        extracted=extracted,
        master=master,
    )
    response_text = _call_groq_llm(
        prompt,
    )

    return _parse_semantic_match(
        response_text,
    )


def compare_line_items_semantically(
    extracted: str,
    master: str,
) -> SemanticMatchResult:
    prompt = FUZZY_MATCH_PROMPT.format(
        extracted=extracted,
        master=master,
    )
    response_text = _call_groq_llm(
        prompt,
    )

    fuzzy_result = _parse_fuzzy_match(
        response_text,
    )

    return _apply_fuzzy_match_threshold(
        fuzzy_result,
    )


def generate_review_executive_summary(
    payload: dict[str, Any],
) -> str:
    prompt = REVIEW_SUMMARY_PROMPT.format(
        payload=json.dumps(
            payload,
            indent=2,
        ),
    )

    return _call_groq_plain_text(
        prompt,
    )
