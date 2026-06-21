from enum import Enum as PyEnum
from typing import TypeVar

from sqlalchemy import Enum as SAEnum

E = TypeVar("E", bound=PyEnum)


def pg_enum(enum_class: type[E]) -> SAEnum:
    return SAEnum(
        enum_class,
        values_callable=lambda members: [member.value for member in members],
    )


def user_role_enum(enum_class: type[E]) -> SAEnum:
    return SAEnum(
        enum_class,
        values_callable=lambda members: [member.name for member in members],
    )


def allocation_match_type_enum(enum_class: type[E]) -> SAEnum:
    return SAEnum(
        enum_class,
        values_callable=lambda members: [member.name for member in members],
    )
