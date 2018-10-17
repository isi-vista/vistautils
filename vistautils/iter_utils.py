from collections import deque
from itertools import islice
from typing import Iterable, TypeVar, Tuple

from vistautils.preconditions import check_arg

_T = TypeVar("_T")


def windowed(iterable: Iterable[_T], window_size: int, *,
             partial_windows: bool = False) -> Iterable[Tuple[_T, ...]]:
    check_arg(window_size >= 1)
    if partial_windows:
        return _possibly_incomplete_windows(iterable, window_size)
    else:
        return _complete_windows(iterable, window_size)


def _complete_windows(iterable: Iterable[_T], window_size: int) -> Iterable[Tuple[_T, ...]]:
    """
    Complete sliding windows of the given size over an iterable.

    For a sequence ``(x_0, x_1, ...., x_n)`` and window size ``w``, this will return
    the sequence ``(x_0, ..., x_{0+w}), (x_1, ..., x_{1+w}), ...``. This will *not* return
    incomplete windows at the end of an iterable (that is, if ``x_{i+w}`` would be outside
    the input sequence).

    Implementation borrowed from Jerry Kindall and ShadowRange(?) at
    https://stackoverflow.com/a/40937024/413345
    """
    it = iter(iterable)
    win = deque(islice(it, window_size), window_size)
    if len(win) < window_size:
        return
    # cache method access for slight speed boost
    append = win.append
    yield tuple(win)
    for e in it:
        append(e)
        yield tuple(win)


def _possibly_incomplete_windows(iterable: Iterable[_T], window_size: int) \
        -> Iterable[Tuple[_T, ...]]:
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
    it = iter(iterable)
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
