"""Amaç tabanlı ajan ve BFS rota planlama testleri."""

import itertools
import unittest

from agents import bfs_distances, route_rooms, shortest_path
from environment import Action, Grid

L, R, U, D = Action.LEFT, Action.RIGHT, Action.UP, Action.DOWN
ALL_GRID_SIZES = [(r, c) for r in range(1, 7) for c in range(1, 7) if r * c >= 2]


class ShortestPathTests(unittest.TestCase):
    def test_same_start_and_goal_gives_empty_route(self):
        self.assertEqual(shortest_path(Grid(3, 3), "B2", "B2"), ())

    def test_examples_follow_documented_direction_order(self):
        # Komşu sırası Sol, Sağ, Yukarı, Aşağı: eşit yollar arasında yatay önce gelir.
        grid = Grid(3, 3)
        self.assertEqual(shortest_path(grid, "A1", "C3"), (R, R, D, D))
        self.assertEqual(shortest_path(grid, "C3", "A1"), (L, L, U, U))
        self.assertEqual(shortest_path(grid, "A1", "B3"), (R, R, D))
        self.assertEqual(shortest_path(Grid(1, 2), "A", "B"), (R,))

    def test_every_pair_in_every_grid_is_shortest_and_valid(self):
        """35 grid boyutunda bütün başlangıç-hedef çiftleri."""
        checked = 0
        for rows, cols in ALL_GRID_SIZES:
            grid = Grid(rows, cols)
            for start, goal in itertools.product(grid.rooms, repeat=2):
                route = shortest_path(grid, start, goal)
                (r1, c1), (r2, c2) = grid.position_of(start), grid.position_of(goal)
                self.assertEqual(len(route), abs(r1 - r2) + abs(c1 - c2))
                rooms = route_rooms(grid, start, route)  # her hareket geçerli olmalı
                self.assertEqual(rooms[-1] if rooms else start, goal)
                checked += 1
        self.assertEqual(checked, sum((r * c) ** 2 for r, c in ALL_GRID_SIZES))

    def test_result_is_deterministic(self):
        grid = Grid(6, 6)
        self.assertEqual({shortest_path(grid, "A1", "F6") for _ in range(20)}, {shortest_path(grid, "A1", "F6")})

    def test_bfs_distances_match_route_lengths(self):
        grid = Grid(4, 5)
        for start in grid.rooms:
            distances = bfs_distances(grid, start)
            self.assertEqual(set(distances), set(grid.rooms))
            for goal in grid.rooms:
                self.assertEqual(distances[goal], len(shortest_path(grid, start, goal)))

    def test_invalid_rooms_are_rejected(self):
        with self.assertRaises(ValueError):
            shortest_path(Grid(2, 2), "A1", "Z9")
        with self.assertRaises(ValueError):
            shortest_path(Grid(2, 2), "Z9", "A1")
        with self.assertRaises(ValueError):
            route_rooms(Grid(2, 2), "A1", (L,))


if __name__ == "__main__":
    unittest.main()
