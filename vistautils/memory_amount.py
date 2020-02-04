import re
from enum import Enum, auto, unique
from typing import Mapping

from attr import attrib, attrs
from attr.validators import and_, in_, instance_of

from immutablecollections import immutabledict

from vistautils.range import Range


@unique
class MemoryUnit(Enum):
    """
    A unit in which memory can be measured.
    """

    KILOBYTES = auto()
    MEGABYTES = auto()
    GIGABYTES = auto()
    TERABYTES = auto()

    @staticmethod
    def parse(memory_unit_string: str) -> "MemoryUnit":
        """
        Parses a string of the format "[K|M|G|T]" as a memory unit.

        Throws a `RuntimeException` on parse failure.

        This may be expanded to accept more formats in the future.
        """
        ret = _STRING_TO_UNIT.get(memory_unit_string.upper())
        if ret:
            return ret
        else:
            raise RuntimeError(
                f"For a memory unit, expected one of {set(_STRING_TO_UNIT.keys())}"
                f" but got {memory_unit_string}"
            )


_STRING_TO_UNIT: Mapping[str, MemoryUnit] = immutabledict(
    [
        ("K", MemoryUnit.KILOBYTES),
        ("M", MemoryUnit.MEGABYTES),
        ("G", MemoryUnit.GIGABYTES),
        ("T", MemoryUnit.TERABYTES),
    ]
)


@attrs(frozen=True, slots=True)
class MemoryAmount:
    """
    An amount of memory, consisting of an *amount*
    paired with its corresponding `MemoryUnit` *unit*.
    """

    amount: int = attrib(validator=and_(instance_of(int), in_(Range.at_least(1))))
    unit: MemoryUnit = attrib(validator=None)

    _PARSE_PATTERN = re.compile(r"(\d+) ?([TtGgMmKk])[bB]?")

    @staticmethod
    def parse(memory_string: str) -> "MemoryAmount":
        parts = MemoryAmount._PARSE_PATTERN.match(memory_string)
        if parts:
            return MemoryAmount(
                amount=int(parts.group(1)), unit=MemoryUnit.parse(parts.group(2))
            )
        else:
            raise RuntimeError(
                f"Cannot parse {memory_string} as an amount of memory.  "
                f"Expected an integer followed by K, M, G, or T"
            )
