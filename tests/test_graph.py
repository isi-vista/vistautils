from unittest import TestCase

from immutablecollections import immutablesetmultidict
from vistautils._graph import Digraph


class TestGraph(TestCase):
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

    def test_in_degree(self) -> None:
        self.assertEqual(self.GRAPH.in_degree()["1"], 0)
        self.assertEqual(self.GRAPH.in_degree()["2"], 1)
        self.assertEqual(self.GRAPH.in_degree()["3"], 0)
        self.assertEqual(self.GRAPH.in_degree()["5"], 0)
        self.assertEqual(self.GRAPH.in_degree()["7"], 0)
        self.assertEqual(self.GRAPH.in_degree()["8"], 2)
        self.assertEqual(self.GRAPH.in_degree()["9"], 2)
        self.assertEqual(self.GRAPH.in_degree()["10"], 2)
        self.assertEqual(self.GRAPH.in_degree()["11"], 2)

        self.assertEqual(
            dict(self.GRAPH.in_degree()),
            {"1": 0, "2": 1, "3": 0, "5": 0, "7": 0, "8": 2, "9": 2, "10": 2, "11": 2},
        )
