from unittest import TestCase

from immutablecollections import immutableset, immutablesetmultidict

from vistautils._graph import Digraph, ParameterInterpolationError


class TestGraph(TestCase):
    # This graph is taken from
    # https://upload.wikimedia.org/wikipedia/commons/thumb/0/03/Directed_acyclic_graph_2.svg/360px-Directed_acyclic_graph_2.svg.png
    # with the addition of a node "1" not participating in any edges.
    GRAPH = Digraph(
        nodes=("1", "2", "3", "5", "7", "8", "9", "10", "11"),
        edges=(
            ("5", "11"),
            ("7", "11"),
            ("7", "8"),
            ("3", "8"),
            ("3", "10"),
            ("11", "2"),
            ("11", "9"),
            ("11", "10"),
            ("8", "9"),
        ),
    )

    def test_initialization(self) -> None:
        self.assertEqual(
            self.GRAPH.predecessors,
            immutablesetmultidict(
                (
                    ("2", "11"),
                    ("8", "3"),
                    ("8", "7"),
                    ("9", "8"),
                    ("9", "11"),
                    ("10", "3"),
                    ("10", "11"),
                    ("11", "5"),
                    ("11", "7"),
                )
            ),
        )

        with self.assertRaisesRegex(
            RuntimeError, f"These nodes are not in the master list: {immutableset(['3'])}"
        ):
            Digraph(nodes=("1", "2"), edges=(("1", "2"), ("1", "3")))

    def test_in_degree(self) -> None:
        self.assertEqual(self.GRAPH.in_degree()["1"], 0)
        self.assertEqual(self.GRAPH.in_degree()["2"], 1)
        self.assertEqual(self.GRAPH.in_degree()["8"], 2)

        self.assertEqual(
            dict(self.GRAPH.in_degree()),
            {"1": 0, "2": 1, "3": 0, "5": 0, "7": 0, "8": 2, "9": 2, "10": 2, "11": 2},
        )

    def test_topological_sort(self) -> None:
        # TODO How to test that a sequence is a valid topological sort when >1 solution is possible?

        g1 = Digraph(nodes=("a", "b", "c"), edges=(("a", "b"), ("b", "c"), ("c", "b")))
        g2 = Digraph(nodes=("a", "b", "c"), edges=(("a", "b"), ("b", "c"), ("c", "a")))

        with self.assertRaisesRegex(
            ParameterInterpolationError,
            r"These interpolated parameters form at least one "
            r"graph cycle that must be fixed: \('b', 'c'\)",
        ):
            tuple(g1.topological_sort())
        with self.assertRaisesRegex(
            ParameterInterpolationError,
            r"These interpolated parameters form at least one "
            r"graph cycle that must be fixed: \('a', 'b', 'c'\)",
        ):
            tuple(g2.topological_sort())
