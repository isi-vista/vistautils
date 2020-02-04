import importlib
from itertools import chain
from pathlib import Path
from typing import Any, Generic, Iterable, List, Mapping, Sequence, Type, TypeVar, Union

from attr import attrib, attrs, validators

from vistautils import preconditions


def str_list_limited(_list: Iterable[Any], limit: int) -> str:
    """
    Get the string representation of a list which is not too long.

    If the size of the input list is less or equal to the limit, returns str(list).
    If the size exceeds the limit, returns a string representation which matches str(list) for
    the first limit items, and the has the string "and N more", where N is the number of items
    not shown.

    This is useful for producing exception messages for collection lookups, so you can give
    the user some idea what is in the collection without potentially blowing up their terminal
    for large collections.
    """
    if limit < 0:
        raise ValueError("Limit must be positive")
    if not isinstance(_list, List):
        _list = list(_list)

    if len(_list) <= limit:
        return str(_list)
    else:
        return (
            "["
            + ", ".join(repr(x) for x in _list[:limit])
            + " and %s more" % (len(_list) - limit)
            + "]"
        )


T = TypeVar("T")


def eval_in_context_of_modules(
    to_eval: str,
    context: Mapping[Any, Any],
    *,
    context_modules: Sequence[str],
    expected_type: Type[T],
) -> T:
    """
    Evaluate the given expression in the specified context.

    Optionally, enforce that the result is of the expected type, throwing a
    `RuntimeException` otherwise.

    The context of evaluation will be that given by `context` augmented by the import of the
    modules whose names are given in `context_modules`.  If you want this to be evaluated in the
    context of the call site, pass `locals` as the context.

    Just like with `eval` itself, never pass anything from an uncontrolled source to this method,
    since it could allow arbitrary code execution.
    """
    # we make a copy so we do not alter the calling context
    context = dict(context)

    # import into the context to be used for evaluation any additional modules requested
    for module_name in context_modules:
        package_parts = module_name.split(".")
        # emulate the import statement's behavior of importing parent packages
        for package_part_idx in range(len(package_parts)):
            package_name = ".".join(package_parts[0 : package_part_idx + 1])
            if package_name not in context:
                context[package_name] = importlib.import_module(package_name)
    ret = eval(to_eval, context)  # pylint:disable=eval-used
    if isinstance(ret, expected_type):
        return ret
    else:
        raise TypeError(
            "Expected result of evaluating {!s} to be of type {!s} but "
            "got {!s}".format(to_eval, expected_type, ret)
        )


def pathify(p: Union[str, Path]) -> Path:
    """
    Allow functions to take strings or proper `Path`s

    If the input is a `Path`, it is returned unchanged. If a string, it is changed to a `Path`
    """
    if isinstance(p, Path):
        return p
    else:
        return Path(p)


def strip_extension(name: str) -> str:
    """
    Remove a single extension from a file name, if present.
    """
    last_dot = name.rfind(".")
    if last_dot > -1:
        return name[:last_dot]
    else:
        return name


def flatten_once_to_list(iterable_of_iterables: Iterable[Iterable[T]]) -> List[T]:
    """
    Removes one level of nesting from nested iterables.

    Taken from the itertools recipes.
    """
    return list(chain.from_iterable(iterable_of_iterables))


# can't set slots=True or you get https://github.com/python-attrs/attrs/issues/313
@attrs(frozen=True)
class WithId(Generic[T]):
    """
    Pair some object with some ID.

    This is typically used as an input to an Ingester when no document ID can be extracted
    from the data itself.
    """

    # can't use attr_instance_of due to circular import problems
    id: str = attrib()
    item: T = attrib()

    def __attrs_post_init__(self) -> None:
        preconditions.check_arg(self.item is not None)
        preconditions.check_arg(isinstance(self.id, str), "Id must be a string")
        preconditions.check_arg(self.id, "Doc IDs may not be empty")


@attrs(frozen=True)
class Scored(Generic[T]):
    """
    An item together with a score.
    """

    item: T = attrib()
    score: float = attrib(validator=validators.instance_of(float))

    def __attrs_post_init__(self) -> None:
        preconditions.check_arg(self.item is not None, "Item of a scored may not be None")
        preconditions.check_arg(isinstance(self.score, float))
