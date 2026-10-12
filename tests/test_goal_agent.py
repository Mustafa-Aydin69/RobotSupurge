"""Amaç tabanlı ajan ve BFS rota planlama testleri."""

import itertools
import random
import unittest
from fractions import Fraction

from agents import (
    GOAL_DIRTY, GOAL_EXPLORE, GOAL_UNKNOWN, GoalBasedAgent, bfs_distances,
    route_rooms, shortest_path,
)
from environment import Action, Grid, Status

L, R, U, D = Action.LEFT, Action.RIGHT, Action.UP, Action.DOWN
CLEAN, DIRTY = Status.CLEAN, Status.DIRTY


def make_goal_agent(rows, cols, seed=0):
    return GoalBasedAgent(grid=Grid(rows, cols), rng=random.Random(seed))


def remember(agent, *percepts):
    """İç modeli algı dizisiyle kurar (yalnızca update_model; eylem yok)."""
    for percept in percepts:
        agent.update_model(percept)


def corridor_example():
    """Plan örneği 1: 1×5 koridor, ajan A3'e varınca yaşlar A1=10, A2=1, A4=2, A5=3."""
    agent = make_goal_agent(1, 5)
    remember(agent, ("A1", CLEAN), *[("A3", CLEAN)] * 6, ("A5", CLEAN), ("A4", CLEAN), ("A2", CLEAN))
    agent.update_model(("A3", CLEAN))  # adım 11
    return agent


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


class TargetSelectionTests(unittest.TestCase):
    def test_exploration_score_matches_plan_example(self):
        agent = corridor_example()
        snap = agent.model_snapshot()
        self.assertEqual([snap.age_of(r) for r in ("A1", "A2", "A4", "A5")], [10, 1, 2, 3])
        target = agent.choose_target("A3")
        self.assertEqual((target.room, target.kind, target.distance), ("A1", GOAL_EXPLORE, 2))
        self.assertEqual(target.score, Fraction(12, 2))   # (10 + 2) / 2

    def test_known_dirty_room_has_highest_priority(self):
        agent = make_goal_agent(3, 3)
        # C3 kirli bilinir; A2 bilinmiyor ve daha yakın; yine de kirli oda seçilir.
        remember(agent, ("C3", DIRTY), ("A1", CLEAN))
        target = agent.choose_target("A1")
        self.assertEqual((target.room, target.kind, target.distance), ("C3", GOAL_DIRTY, 4))

    def test_nearest_known_dirty_room_is_chosen(self):
        agent = make_goal_agent(3, 3)
        remember(agent, ("C3", DIRTY), ("A3", DIRTY), ("A1", CLEAN))
        self.assertEqual(agent.choose_target("A1").room, "A3")

    def test_unknown_room_beats_old_known_room(self):
        agent = make_goal_agent(1, 4)
        remember(agent, ("A1", CLEAN), *[("A2", CLEAN)] * 20)
        target = agent.choose_target("A2")
        self.assertEqual((target.room, target.kind, target.distance), ("A3", GOAL_UNKNOWN, 1))

    def test_nearest_unknown_room_is_chosen(self):
        agent = make_goal_agent(3, 3)
        remember(agent, ("A1", CLEAN), ("A2", CLEAN), ("B1", CLEAN), ("B2", CLEAN))
        target = agent.choose_target("A1")
        self.assertEqual(target.kind, GOAL_UNKNOWN)
        self.assertIn(target.room, {"A3", "C1"})          # ikisi de 2 adım uzakta
        self.assertEqual(target.distance, 2)

    def test_unknown_tie_uses_seeded_choice_among_nearest_only(self):
        chosen = set()
        for seed in range(40):
            agent = make_goal_agent(3, 3, seed)
            agent.update_model(("B2", CLEAN))
            chosen.add(agent.choose_target("B2").room)
        self.assertEqual(chosen, {"A2", "B1", "B3", "C2"})

    def test_exploration_tie_prefers_shorter_distance(self):
        # 1×3, ajan A1'de. Yaşlar: A2 = 1 (d=1), A3 = 2 (d=2).
        # Puanlar: A2 -> (1+1)/1 = 2, A3 -> (2+2)/2 = 2. Eşit puanda kısa mesafe kazanır.
        for seed in range(20):
            agent = make_goal_agent(1, 3, seed)
            remember(agent, ("A3", CLEAN), ("A2", CLEAN), ("A1", CLEAN))
            target = agent.choose_target("A1")
            self.assertEqual((target.room, target.score), ("A2", Fraction(2)))

    def test_current_room_is_never_a_target(self):
        for rows, cols in [(1, 2), (2, 2), (3, 3)]:
            agent = make_goal_agent(rows, cols)
            for room in agent.grid.rooms:
                agent.update_model((room, CLEAN))
                self.assertNotEqual(agent.choose_target(room).room, room)

    def test_target_uses_only_model_not_environment(self):
        """Hedef seçimi modelin içeriğinden türetilir; modelde olmayan oda 'bilinmiyor'dur."""
        agent = make_goal_agent(2, 2)
        agent.update_model(("A1", CLEAN))
        target = agent.choose_target("A1")
        self.assertEqual(target.kind, GOAL_UNKNOWN)
        self.assertNotIn(target.room, agent.model_snapshot().observations)


if __name__ == "__main__":
    unittest.main()
