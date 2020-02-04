import re

from vistautils.memory_amount import MemoryAmount, MemoryUnit

import pytest

UNIT_PARSE_TEST_PAIRS = [
    (MemoryUnit.KILOBYTES, "K"),
    (MemoryUnit.MEGABYTES, "M"),
    (MemoryUnit.GIGABYTES, "G"),
    (MemoryUnit.TERABYTES, "T"),
]


@pytest.mark.parametrize("reference_unit,string_to_parse", UNIT_PARSE_TEST_PAIRS)
def test_memory_unit(reference_unit: MemoryUnit, string_to_parse: str):
    assert reference_unit == MemoryUnit.parse(string_to_parse)
    assert reference_unit == MemoryUnit.parse(string_to_parse.lower())


def test_bad_memory_unit():
    exception_pattern = re.compile("For a memory unit, expected one of.* but got .*")
    with pytest.raises(RuntimeError, match=exception_pattern):
        MemoryUnit.parse("A")
    with pytest.raises(RuntimeError, match=exception_pattern):
        MemoryUnit.parse("foo")


UNITS = [
    MemoryUnit.KILOBYTES,
    MemoryUnit.MEGABYTES,
    MemoryUnit.GIGABYTES,
    MemoryUnit.TERABYTES,
]
AMOUNTS = [(42, "42"), (1, "1")]
SPACES = ["", " "]
SUFFIXES = ["", "B", "b"]


@pytest.mark.parametrize("reference_amount,amount_string", AMOUNTS)
@pytest.mark.parametrize("reference_unit,unit_string", UNIT_PARSE_TEST_PAIRS)
@pytest.mark.parametrize("spaces", SPACES)
@pytest.mark.parametrize("suffix", SUFFIXES)
def test_memory_amount(
    reference_amount: int,
    amount_string: str,
    reference_unit: MemoryUnit,
    unit_string: str,
    spaces: str,
    suffix: str,
):
    parsed = MemoryAmount.parse(f"{amount_string}{spaces}{unit_string}{suffix}")
    assert reference_amount == parsed.amount
    assert reference_unit == parsed.unit
