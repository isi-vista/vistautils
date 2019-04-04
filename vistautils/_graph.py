from typing import Any, Iterator, Tuple

from attr import attrib, attrs

from immutablecollections import (
    immutableset,
    ImmutableSet,
    ImmutableSetMultiDict,
    immutablesetmultidict,
)


class GraphAlgoUnfeasible(Exception):
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


def _to_immutableset(items: Any) -> ImmutableSet[str]:
    if not items:
        return immutableset()
    return immutableset(items)


def _to_immutablesetmultidict(items: Any) -> ImmutableSetMultiDict[str, str]:
    if not items:
        return immutablesetmultidict()
    return immutablesetmultidict(items)


@attrs(frozen=True, slots=True)
class Digraph:
    nodes: ImmutableSet[str] = attrib(converter=_to_immutableset, default=immutableset())
    # edges are stored as successors in adjacency list format
    edges: ImmutableSetMultiDict[str, str] = attrib(
        converter=_to_immutablesetmultidict,
        default=immutablesetmultidict(),
        validator=validate_edges,
    )
    predecessors: ImmutableSetMultiDict[str, str] = attrib(init=False)

    def in_degree(self):
        return InDegreeView(self)

    def topological_sort(self) -> Iterator[str]:
        indegree_map = {v: d for v, d in self.in_degree() if d > 0}
        zero_indegree = [v for v, d in self.in_degree() if d == 0]

        while zero_indegree:
            node = zero_indegree.pop()
            if node not in self.nodes:
                raise RuntimeError("Graph changed during iteration")
            for child in self.edges[node]:
                try:
                    indegree_map[child] -= 1
                except KeyError:
                    raise RuntimeError("Graph changed during iteration")
                if indegree_map[child] == 0:
                    zero_indegree.append(child)
                    del indegree_map[child]

            yield node

        if indegree_map:
            raise GraphAlgoUnfeasible(
                "Graph contains a cycle or graph changed during iteration"
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
