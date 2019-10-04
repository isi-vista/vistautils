# suppress lots of spurious pylint errors due to @overloads
# pylint:disable=unused-argument
# pylint:disable=function-redefined
import itertools
from collections import deque
from itertools import islice
from typing import Generic, Iterable, Iterator, Optional, Tuple, TypeVar, Union, overload

from attr import attrs

from vistautils.preconditions import check_arg

_T = TypeVar("_T")


# drop will return an Iterable if it receives an Iterable and an Iterator if it receives an Iterator
# see PEP 484: https://www.python.org/dev/peps/pep-0484/#function-method-overloading


@overload
def drop(it: Iterator[_T], num_to_skip: int) -> Iterator[_T]:
    raise NotImplementedError(
        "This should be impossible to call; this function definition is for the type checker only"
    )


@overload  # noqa: F811
def drop(it: Iterable[_T], num_to_skip: int) -> Iterable[_T]:
    raise NotImplementedError(
        "This should be impossible to call; this function definition is for the type checker only"
    )


def drop(it, num_to_skip: int):  # noqa: F811
    """
    Skip `num_to_skip` elements of an ``Iterable`` or ``Iterator``.

    If `it` is an ``Iterator``, makes an ``Iterator`` which returns elements of the original
    iterator starting from the `num_to_skip+1`th element.

    If `it` is an ``Iterable``, makes an ``Iterable`` which returns elements of the original
    iterable starting from the `num_to_skip+1`th element.

    `num_to_skip` must be non-negative or a `ValueError` will be raised.
    """
    check_arg(
        num_to_skip >= 0,
        "Number of items to skip must be positive but got %s",
        (num_to_skip,),
    )
    if hasattr(it, "__next__"):
        return itertools.islice(it, num_to_skip, None)
    else:
        return _DropIterable(it, num_to_skip)


# used by `only`
_SENTINEL = object()


def only(it: Union[Iterator[_T], Iterable[_T]]) -> _T:
    """
    Get the only element in `iterable` or throw an exception.

    If `iterable` has exactly one element, return that element.
    If it has zero or more than one, a ``LookupError`` will be raised.
    """
    if hasattr(it, "__next__"):
        # noinspection PyTypeHints
        iterator: Iterator[_T] = it  # type: ignore
    else:
        iterator = iter(it)

    try:
        ret = next(iterator)
    except StopIteration:
        raise ValueError("Expected only a single element in an iterable, but got none")

    second_element = next(iterator, _SENTINEL)
    if second_element != _SENTINEL:
        raise ValueError("Expected only a single element in iterable, but got at least 2")
    return ret


@overload
def windowed(
    it: Iterator[_T], window_size: int, *, partial_windows: bool = False
) -> Iterator[Tuple[_T, ...]]:
    raise NotImplementedError(
        "This should be impossible to call; this function definition is for the type checker only"
    )


@overload  # noqa: F811
def windowed(
    it: Iterable[_T], window_size: int, *, partial_windows: bool = False
) -> Iterable[Tuple[_T, ...]]:
    raise NotImplementedError(
        "This should be impossible to call; this function definition is for the type checker only"
    )


def windowed(it, window_size: int, *, partial_windows: bool = False):  # noqa: F811
    check_arg(window_size >= 1)

    if not hasattr(it, "__next__"):
        return _WindowedIterable(
            wrapped_iterable=it, window_size=window_size, partial_windows=partial_windows
        )

    # we know at this point that it is an Iterable, but mypy might not, hence the ignores below
    if partial_windows:
        return _possibly_incomplete_windows(it, window_size)
    else:
        return _complete_windows(it, window_size)


# implementation helpers for drop()


@attrs(auto_attribs=True)
class _DropIterable(Generic[_T], Iterable[_T]):
    # we dispense with type and sign checks here since they already happened in drop
    _wrapped_iterable: Iterable[_T]
    _num_to_drop: int

    def __iter__(self) -> Iterator[_T]:
        return drop(iter(self._wrapped_iterable), self._num_to_drop)


# implementation helpers for windowed()


@attrs(auto_attribs=True)
class _WindowedIterable(Generic[_T], Iterable[Tuple[_T, ...]]):
    # we dispense with checks on these fields because `windowed` already handles it
    _wrapped_iterable: Iterable[_T]
    _window_size: int
    _partial_windows: bool

    def __iter__(self) -> Iterator[Tuple[_T, ...]]:
        return windowed(
            iter(self._wrapped_iterable),
            self._window_size,
            partial_windows=self._partial_windows,
        )


def _complete_windows(it: Iterator[_T], window_size: int) -> Iterator[Tuple[_T, ...]]:
    """
    Complete sliding windows of the given size over an iterable.

    For a sequence ``(x_0, x_1, ...., x_n)`` and window size ``w``, this will return
    the sequence ``(x_0, ..., x_{0+w}), (x_1, ..., x_{1+w}), ...``. This will *not* return
    incomplete windows at the end of an iterable (that is, if ``x_{i+w}`` would be outside
    the input sequence).

    Implementation borrowed from Jerry Kindall and ShadowRange(?) at
    https://stackoverflow.com/a/40937024/413345
    """
    win = deque(islice(it, window_size), window_size)
    if len(win) < window_size:
        return
    # cache method access for slight speed boost
    append = win.append
    yield tuple(win)
    for e in it:
        append(e)
        yield tuple(win)


def _possibly_incomplete_windows(
    it: Iterator[_T], window_size: int
) -> Iterator[Tuple[_T, ...]]:
    """
    All sliding windows of the given size over an iterable.

    For a sequence ``(x_0, x_1, ...., x_n)`` and window size ``w``, this will return
    the sequence ``(x_0, ..., x_{0+w}), (x_1, ..., x_{1+w}), ...``. This *will* return
    incomplete windows at the end of an iterable (that is, if ``x_{i+w}`` would be outside
    the input sequence); the positions in a window beyond an iterable will be filled with
    ``fill_value``.

    Adapted from complete windowing implementation borrowed from Jerry Kindall and ShadowRange(?) at
    https://stackoverflow.com/a/40937024/413345
    """
    win = deque(islice(it, window_size), window_size)
    if not win:
        return
    # cache method access for slight speed boost
    append = win.append
    yield tuple(win)
    for e in it:
        append(e)
        yield tuple(win)
    # add incomplete windows at the end
    popleft = win.popleft
    for _ in range(window_size - 1):
        popleft()
        if win:
            yield tuple(win)
        else:
            # if the window size exceeds the sequence size, we need to stop popping early
            # or we will have a bunch of empty tuples at the end
            break


def non_none(iterable: Iterable[Optional[_T]]) -> Iterable[_T]:
    """
    Make an iterator which contains all elements from *iterable* which are not *None*.
    """
    return (x for x in iterable if x is not None)
