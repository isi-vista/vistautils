"""
immutablecollections provides immutable collections in the spirit of
those provided by Google's Guava in Java.

Each immutable collection can be created with the `of` static method,
which accepts an iterable of the same type as the equivalent mutable
built-in. For example, an ImmutableDict will accept a dict or an
iterable of (key, value) tuples, just like the dict builtin.
Empty collections can be created with the `empty` static method. There
is a dedicated method for an empty collection to avoid the potential
bugs enabled by allowing `of` to be provided the value None or no
arguments.

Immutable collections efficiently reuse objects when possible. In the
following example, x and y will refer to the same object:
x = ImmutableList.of([1, 2, 3])
y = ImmutableList.of(x)

Immutable collections will only compare equal with objects of the same
type. For example, ImmutableList.of([1, 2, 3]) is equal to
ImmutableList.of([1, 2, 3]) but will not be equal to the list [1, 2, 3]
or the tuple (1, 2, 3). This behavior is analogous to the relationship
between lists and tuples (which can never compare equal), but differs
from the relationship between sets and frozensets, which can compare
equal.
"""

# Easiest to just use the same exception
# noinspection PyUnresolvedReferences
from attr.exceptions import FrozenInstanceError

from flexnlp.utils.immutablecollections.immutablecollection import ImmutableCollection
from flexnlp.utils.immutablecollections.immutabledict import ImmutableDict
from flexnlp.utils.immutablecollections.immutablelist import ImmutableList
from flexnlp.utils.immutablecollections.immutableset import ImmutableSet
from flexnlp.utils.immutablecollections.utils import ImmutableMixin
