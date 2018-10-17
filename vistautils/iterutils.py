from typing import TypeVar, Iterable, Tuple

import vistautils.iter_utils

# deprecated, present for backwards compatibility
_T = TypeVar('_T')


# noinspection PyTypeHints
def tile_with_pairs(iterable: Iterable[_T]) -> Iterable[Tuple[_T, _T]]:
    # noinspection PyTypeChecker
    return vistautils.iter_utils.windowed(iterable, 2, partial_windows=False)  # type: ignore
