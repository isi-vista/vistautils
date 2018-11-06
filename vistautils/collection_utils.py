from typing import Iterable, TypeVar

T = TypeVar("T")


def get_only(seq: Iterable[T]) -> T:
    """
    Get the only element of a sequence or raise an `ValueError`
    """
    it = iter(seq)
    try:
        val = it.__next__()
        # we use the sentinel approach rather than the usual (evil) Python "attempt can catch the
        # exception" approach to avoid raising zillions of spurious exceptions on the expected
        # code path, which makes debugging a pain
        sentinel = object()
        second_element = next(it, sentinel)
        if second_element is sentinel:
            return val
        else:
            raise ValueError(
                "Expected one item in sequence but got multiple: %r" % (seq,)
            )
    except StopIteration:
        raise ValueError("Expected one item in sequence but got none")
