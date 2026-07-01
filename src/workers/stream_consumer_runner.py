from __future__ import annotations

import asyncio
import logging
import signal

from src.messaging.redis_stream_consumer import RedisStreamConsumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger(__name__)


async def _run_consumer() -> None:
    consumer = RedisStreamConsumer()
    stop_event = asyncio.Event()

    def _request_shutdown() -> None:
        logger.info("Shutdown requested for extraction stream consumer")
        stop_event.set()

    loop = asyncio.get_running_loop()

    for sig in (
        signal.SIGINT,
        signal.SIGTERM,
    ):
        try:
            loop.add_signal_handler(
                sig,
                _request_shutdown,
            )
        except NotImplementedError:
            signal.signal(
                sig,
                lambda *_args: _request_shutdown(),
            )

    await consumer.start()
    logger.info("Extraction stream consumer runner started")

    try:
        await stop_event.wait()
    finally:
        await consumer.stop()
        logger.info("Extraction stream consumer runner stopped")


def main() -> None:
    asyncio.run(
        _run_consumer(),
    )


if __name__ == "__main__":
    main()
