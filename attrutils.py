from functools import partial
from typing import Any, Callable, Sized, Tuple, Type, Union

from attr import Factory, attrib, validators

import flexnlp.utils.immutablecollections
import flexnlp.utils.preconditions


# TODO cannot currently be used with additional validators:
# https://github.com/isi-nlp/isi-flexnlp/issues/188
def attrib_instance_of(type_: Union[Type, Tuple[Type, ...]], *args, **kwargs):
    return attrib(validator=validators.instance_of(type_), *args, **kwargs)


# TODO cannot currently be used with additional validators:
# https://github.com/isi-nlp/isi-flexnlp/issues/188
def attrib_opt_instance_of(type_: Union[Type, Tuple[Type, ...]], *args, default=None, **kwargs):
    return attrib(validator=opt_instance_of(type_), default=default, *args, **kwargs)


def attrib_factory(factory: Callable, *args, **kwargs):
    return attrib(default=Factory(factory), *args, **kwargs)


def attrib_immutable(type_: Type[flexnlp.utils.immutablecollections.ImmutableCollection], *args,
                     **kwargs):
    _check_immutable_collection(type_)
    return attrib(convert=type_.of, *args, **kwargs)


def attrib_private_immutable_builder(
        type_: Type[flexnlp.utils.immutablecollections.ImmutableCollection], *args, **kwargs):
    """
    Create an immutable collection builder private attribute.

    This is called "private" because it will not appear as a constructor argument.
    """
    _check_immutable_collection(type_)
    return attrib(default=Factory(type_.builder), init=False, *args, **kwargs)


# TODO: The use of Type[ImmutableCollection] causes mypy warnings
# Perhaps the solution is to make ImmutableCollection a Protocol?
def attrib_opt_immutable(type_: Type[flexnlp.utils.immutablecollections.ImmutableCollection],
                         *args, **kwargs):
    """Return a attrib with a converter for optional collections.

    The returned attrib will create an empty collection of the
    specified type if either the attribute is not specified or it is
    specified with the value of None. Handling None allows for easier
    handling of arguments with a default absent value.
    """
    _check_immutable_collection(type_)
    return attrib(convert=partial(_empty_immutable_if_none, type_=type_),
                  default=type_.empty(), *args, **kwargs)


def opt_instance_of(type_: Union[Type, Tuple[Type, ...]]) -> Callable:
    return validators.instance_of((type_, type(None)))


def _check_immutable_collection(type_):
    flexnlp.utils.preconditions.check_arg(
        issubclass(type_, flexnlp.utils.immutablecollections.ImmutableCollection),
        "Type {} is not an immutable collection".format(type_))


def _empty_immutable_if_none(val: Any,
                             type_: Type[flexnlp.utils.immutablecollections.ImmutableCollection]) \
        -> flexnlp.utils.immutablecollections.ImmutableCollection:
    if val is None:
        return type_.empty()
    else:
        return type_.of(val)


# Unused arguments are to match the attrs validator signature
# noinspection PyUnusedLocal
def non_empty(self: Any, attr: Any, val: Sized) -> bool:  # pylint: disable=unused-argument
    return len(val) > 0
