from typing import TypeVar, Iterable

T = TypeVar('T')


def get_only(seq: Iterable[T]) -> T:
    """
    Get the only element of a sequence or raise an `ValueError`
    """
    it = iter(seq)
    try:
        val = it.__next__()
        try:
            it.__next__()
        except StopIteration:
            return val
        raise ValueError("Expected one item in sequence but got %r" % (seq,))
    except StopIteration:
        raise ValueError("Expected one item in sequence but got none")
