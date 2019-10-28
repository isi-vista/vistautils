"""This file contains a minimal graph implementation meant only to support
`vistautils.parameters.Parameters` and should not be used for anything else.
"""

from typing import Any, Iterator, Tuple

from attr import attrib, attrs

from immutablecollections import (
    ImmutableSet,
    ImmutableSetMultiDict,
    immutableset,
    immutablesetmultidict,
)


class ParameterInterpolationError(Exception):
    pass


def validate_edges(
    instance: "Digraph", _, edges: ImmutableSetMultiDict[str, str]
) -> None:
    nodes_from_edges = set()
    for k, v in edges.items():
        nodes_from_edges.add(k)
        nodes_from_edges.add(v)
    nodes_only_in_edges = nodes_from_edges - set(instance.nodes)
    if nodes_only_in_edges:
        raise RuntimeError(
            f"These nodes are not in the master list: {nodes_only_in_edges}"
        )


# mypy is confused
def _to_immutableset(items: Any) -> ImmutableSet[str]:
    if not items:
        return immutableset()
    return immutableset(items)


# mypy is confused
def _to_immutablesetmultidict(items: Any) -> ImmutableSetMultiDict[str, str]:
    if not items:
        return immutablesetmultidict()
    return immutablesetmultidict(items)


@attrs(frozen=True, slots=True)
class Digraph:
    """A directed graph implementation.

    Requirements:

    - The edges are expected to be in successor form: for each key node, its value nodes are all
      being pointed to. Worded another way, each edge must be in (node_from, node_to)
      form. `predecessors` is the inverse.
    - The nodes that participate in the edges must appear in the master node list.
    """

    nodes: ImmutableSet[str] = attrib(converter=_to_immutableset, default=immutableset())
    edges: ImmutableSetMultiDict[str, str] = attrib(
        converter=_to_immutablesetmultidict,
        default=immutablesetmultidict(),
        validator=validate_edges,
    )
    predecessors: ImmutableSetMultiDict[str, str] = attrib(init=False)

    def in_degree(self):
        return InDegreeView(self)

    def topological_sort(self) -> Iterator[str]:
        """Algorithm adapted from NetworkX

        https://github.com/networkx/networkx/blob/39a1c6f5471cd3adf476a3bd5355dcaa2e8a6160/networkx/algorithms/dag.py#L121
        """
        indegree_map = {v: d for v, d in self.in_degree() if d > 0}
        zero_indegree = [v for v, d in self.in_degree() if d == 0]

        while zero_indegree:
            node = zero_indegree.pop()
            for child in self.edges[node]:
                indegree_map[child] -= 1
                if indegree_map[child] == 0:
                    zero_indegree.append(child)
                    del indegree_map[child]

            yield node

        # Because this method is only for supporting parameter interpolation, provide a
        # user-friendly error message here to avoid needing access to `indegree_map` externally.
        if indegree_map:
            raise ParameterInterpolationError(
                "These interpolated parameters form at least one graph cycle "
                f"that must be fixed: {tuple(indegree_map.keys())}"
            )

    @predecessors.default
    def init_predecessors(self) -> ImmutableSetMultiDict[str, str]:
        return self.edges.invert_to_set_multidict()


class InDegreeView:
    """This is a greatly simplified combination of DiDegreeView and InDegreeView from NetworkX."""

    def __init__(self, graph: Digraph) -> None:
        self.pred = graph.predecessors
        self.nodes = graph.nodes

    def __repr__(self) -> str:
        return "%s(%r)" % (self.__class__.__name__, dict(self))

    def __getitem__(self, n: str) -> int:
        return len(self.pred[n])

    def __iter__(self) -> Iterator[Tuple[str, int]]:
        for n in self.nodes:
            yield (n, len(self.pred[n]))
