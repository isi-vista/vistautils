from typing import Iterable, Sized, TypeVar

from vistautils.misc_utils import str_list_limited

T = TypeVar("T")


def get_only(seq: Iterable[T]) -> T:
    """
    Get the only element of a sequence or raise an `ValueError`
    """
    it = iter(seq)
    try:
        first_element = it.__next__()
        # we use the sentinel approach rather than the usual (evil) Python "attempt can catch the
        # exception" approach to avoid raising zillions of spurious exceptions on the expected
        # code path, which makes debugging a pain
        sentinel = object()
        second_element = next(it, sentinel)
        if second_element is sentinel:
            return first_element
        else:
            got_msg: str
            if isinstance(seq, Sized):
                got_msg = str_list_limited(seq, limit=10)
            else:
                got_msg = f"{first_element!r}, {second_element!r}, and possibly more."
            raise ValueError(f"Expected one item in sequence but got {got_msg}")
    except StopIteration:
        raise ValueError("Expected one item in sequence but got none")
