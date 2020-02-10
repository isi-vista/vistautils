from datetime import date
from functools import partial
from typing import Any, Callable, Sized, Tuple, Type, Union

from attr import Factory, attrib, validators

import immutablecollections

import vistautils.preconditions

import deprecation


@deprecation.deprecated(
    deprecated_in="0.19.0",
    removed_in=date(2020, 8, 10),
    details="Deprecated, use attrib(validator=instance_of(type))",
)
def attrib_instance_of(type_: Union[Type, Tuple[Type, ...]], *args, **kwargs):
    # Mypy does not understand these arguments
    return attrib(  # type: ignore
        validator=validators.instance_of(type_), *args, **kwargs
    )


# TODO cannot currently be used with additional validators:
# https://github.com/isi-nlp/isi-flexnlp/issues/188
@deprecation.deprecated(
    deprecated_in="0.19.0",
    removed_in=date(2020, 8, 10),
    details="Deprecated, use attrib(default=<default>, validator=optional(instance_of(<type>)))",
)
def attrib_opt_instance_of(
    type_: Union[Type, Tuple[Type, ...]], *args, default=None, **kwargs
):
    # Mypy does not understand these arguments
    return attrib(  # type: ignore
        validator=opt_instance_of(type_), default=default, *args, **kwargs
    )


@deprecation.deprecated(
    deprecated_in="0.19.0",
    removed_in=date(2020, 8, 10),
    details="Deprecated, use attrib(factory=<factory>",
)
def attrib_factory(factory: Callable, *args, **kwargs):
    # Mypy does not understand these arguments
    return attrib(default=Factory(factory), *args, **kwargs)  # type: ignore


@deprecation.deprecated(
    deprecated_in="0.19.0",
    removed_in=date(2020, 8, 10),
    details="Deprecated, use attrib(converter=<collection factory>)",
)
def attrib_immutable(
    type_: Type[immutablecollections.ImmutableCollection], *args, **kwargs
):
    _check_immutable_collection(type_)
    # Mypy does not understand these arguments
    return attrib(converter=type_.of, *args, **kwargs)  # type: ignore


@deprecation.deprecated(
    deprecated_in="0.19.0",
    removed_in=date(2020, 8, 10),
    details="Deprecated with no direct replacement as the builders are also deprecated. "
    "Instead, create an empty private list using attrib(factory=list, init=False) "
    "and append items to be passed to the immutablecollections factory function.",
)
def attrib_private_immutable_builder(
    type_: Type[immutablecollections.ImmutableCollection], *args, **kwargs
):
    """
    Create an immutable collection builder private attribute.

    This is called "private" because it will not appear as a constructor argument.
    """
    _check_immutable_collection(type_)
    # Mypy does not understand these arguments
    return attrib(  # type: ignore
        default=Factory(type_.builder), init=False, *args, **kwargs
    )


# TODO: The use of Type[ImmutableCollection] causes Mypy warnings
# Perhaps the solution is to make ImmutableCollection a Protocol?
@deprecation.deprecated(
    deprecated_in="0.19.0",
    removed_in=date(2020, 8, 10),
    details="Deprecated, use attrib(converter=<collection factory>, default=<collection factory>)",
)
def attrib_opt_immutable(
    type_: Type[immutablecollections.ImmutableCollection], *args, **kwargs
):
    """Return a attrib with a converter for optional collections.

    The returned attrib will create an empty collection of the
    specified type if either the attribute is not specified or it is
    specified with the value of None. Handling None allows for easier
    handling of arguments with a default absent value.
    """
    _check_immutable_collection(type_)
    # Mypy does not understand these arguments
    return attrib(  # type: ignore
        converter=partial(_empty_immutable_if_none, type_=type_),
        default=type_.empty(),
        *args,
        **kwargs
    )


@deprecation.deprecated(
    deprecated_in="0.19.0",
    removed_in=date(2020, 8, 10),
    details="Deprecated, use optional(instance_of(<type>))",
)
def opt_instance_of(type_: Union[Type, Tuple[Type, ...]]) -> Callable:
    # Mypy does not understand these arguments
    return validators.instance_of((type_, type(None)))  # type: ignore


def _check_immutable_collection(type_):
    vistautils.preconditions.check_arg(
        issubclass(type_, immutablecollections.ImmutableCollection),
        "Type {} is not an immutable collection".format(type_),
    )


def _empty_immutable_if_none(
    val: Any, type_: Type[immutablecollections.ImmutableCollection]
) -> immutablecollections.ImmutableCollection:
    if val is None:
        return type_.empty()
    else:
        return type_.of(val)


# Unused arguments are to match the attrs validator signature
# noinspection PyUnusedLocal
def non_empty(_self: Any, _attr: Any, val: Sized) -> bool:
    return len(val) > 0
