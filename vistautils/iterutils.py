from typing import Iterable, Tuple, TypeVar

import vistautils.iter_utils

# deprecated, present for backwards compatibility
_T = TypeVar("_T")


# noinspection PyTypeHints
def tile_with_pairs(iterable: Iterable[_T]) -> Iterable[Tuple[_T, _T]]:
    # noinspection PyTypeChecker
    return vistautils.iter_utils.windowed(  # type: ignore
        iterable, 2, partial_windows=False
    )
