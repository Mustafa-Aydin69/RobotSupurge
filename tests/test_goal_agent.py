"""Amaç tabanlı ajan ve BFS rota planlama testleri."""

import itertools
import random
import unittest
from fractions import Fraction

from agents import (
    GOAL_DIRTY, GOAL_EXPLORE, GOAL_UNKNOWN, REPLAN_FAILED, REPLAN_FIRST, REPLAN_INCONSISTENT,
    REPLAN_INVALID, REPLAN_PRIORITY, REPLAN_REACHED, SOURCE_PERCEPT, GoalBasedAgent, ModelBasedAgent,
    Observation, bfs_distances, route_rooms, shortest_path,
)
from environment import Action, Environment, Grid, Status

L, R, U, D = Action.LEFT, Action.RIGHT, Action.UP, Action.DOWN
CLEAN, DIRTY = Status.CLEAN, Status.DIRTY


def make_goal_agent(rows, cols, seed=0):
    return GoalBasedAgent(grid=Grid(rows, cols), rng=random.Random(seed))


def remember(agent, *percepts):
    """İç modeli algı dizisiyle kurar (yalnızca update_model; eylem yok)."""
    for percept in percepts:
        agent.update_model(percept)


def step(agent, room, status, succeeded=True):
    """Simülasyonun yaptığı gibi: algı -> karar -> eylem sonucu bildirimi."""
    action = agent.act((room, status))
    agent.action_result(action, succeeded)
    return action


def corridor_agent(cls=GoalBasedAgent, seed=0):
    """1×5 koridor; A3'teki ilk kararda yaşlar A1=10, A2=1, A4=2, A5=3 olur."""
    agent = cls(grid=Grid(1, 5), rng=random.Random(seed))
    remember(agent, ("A1", CLEAN), *[("A3", CLEAN)] * 6, ("A5", CLEAN), ("A4", CLEAN), ("A2", CLEAN))
    return agent


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


class RouteFollowingTests(unittest.TestCase):
    def test_follows_route_and_advances_only_after_success(self):
        agent = corridor_agent()
        self.assertIs(agent.act(("A3", CLEAN)), L)
        plan = agent.plan_snapshot()
        self.assertEqual((plan.target.room, plan.route, plan.version, plan.reason), ("A1", (L, L), 1, REPLAN_FIRST))
        # Sonuç bildirilmeden rota ilerlemez.
        self.assertEqual(agent.plan_snapshot().route, (L, L))
        agent.action_result(L, succeeded=True)
        plan = agent.plan_snapshot()
        self.assertEqual((plan.origin, plan.route, plan.route_rooms), ("A2", (L,), ("A1",)))

    def test_commitment_keeps_target_until_reached(self):
        agent = corridor_agent()
        step(agent, "A3", CLEAN)
        self.assertIs(step(agent, "A2", CLEAN), L)
        self.assertEqual(agent.plan_snapshot().version, 1, "Yolda hedef yeniden seçilmemeli")
        step(agent, "A1", CLEAN)
        plan = agent.plan_snapshot()
        self.assertEqual((plan.version, plan.reason), (2, REPLAN_REACHED))
        self.assertNotEqual(plan.target.room, "A1")

    def test_dirty_room_on_route_is_cleaned_without_changing_route(self):
        agent = corridor_agent()
        step(agent, "A3", CLEAN)
        self.assertIs(step(agent, "A2", DIRTY), Action.CLEAN)
        plan = agent.plan_snapshot()
        self.assertEqual((plan.target.room, plan.route, plan.version), ("A1", (L,), 1))
        self.assertIs(step(agent, "A2", CLEAN), L)          # temizlikten sonra hedefe devam
        self.assertEqual(agent.plan_snapshot().version, 1)

    def test_dirty_target_is_cleaned_then_new_target_chosen(self):
        agent = corridor_agent()
        step(agent, "A3", CLEAN)
        step(agent, "A2", CLEAN)
        self.assertIs(step(agent, "A1", DIRTY), Action.CLEAN)
        self.assertEqual(agent.plan_snapshot().version, 1)
        self.assertIs(step(agent, "A1", CLEAN), R)
        self.assertEqual(agent.plan_snapshot().reason, REPLAN_REACHED)

    def test_failed_move_invalidates_plan_and_replans(self):
        agent = corridor_agent()
        action = agent.act(("A3", CLEAN))
        agent.action_result(action, succeeded=False)
        plan = agent.plan_snapshot()
        self.assertEqual((plan.target, plan.route), (None, ()))
        self.assertEqual(agent.model_snapshot().location, "A3", "Başarısız harekette konum değişmez")
        agent.act(("A3", CLEAN))
        plan = agent.plan_snapshot()
        self.assertEqual((plan.reason, plan.version, plan.origin), (REPLAN_FAILED, 2, "A3"))

    def test_higher_priority_goal_replaces_current_target(self):
        agent = corridor_agent()
        step(agent, "A3", CLEAN)                     # hedef A1 (keşif)
        # Test amaçlı: ajanın modeline uzak bir odanın kirli bilgisi eklenir.
        agent._memory["A5"] = Observation(DIRTY, agent._step, SOURCE_PERCEPT)
        self.assertIs(step(agent, "A2", CLEAN), R)
        plan = agent.plan_snapshot()
        self.assertEqual((plan.target.room, plan.target.kind, plan.reason), ("A5", GOAL_DIRTY, REPLAN_PRIORITY))

    def test_invalid_target_triggers_replan(self):
        agent = make_goal_agent(1, 4)
        step(agent, "A1", CLEAN)                     # hedef A2 (bilinmeyen)
        self.assertEqual(agent.plan_snapshot().target.kind, GOAL_UNKNOWN)
        target = agent.plan_snapshot().target.room
        agent._memory[target] = Observation(CLEAN, agent._step, SOURCE_PERCEPT)  # test amaçlı
        agent.act(("A1", CLEAN))
        self.assertEqual(agent.plan_snapshot().reason, REPLAN_INVALID)

    def test_route_inconsistent_with_location_triggers_replan(self):
        agent = corridor_agent()
        step(agent, "A3", CLEAN)                     # rota A3 -> A1; ajan A2'de olmayı bekliyor
        agent.act(("A5", CLEAN))                     # algı başka bir odayı gösteriyor
        plan = agent.plan_snapshot()
        self.assertEqual((plan.reason, plan.origin), (REPLAN_INCONSISTENT, "A5"))
        self.assertEqual(route_rooms(agent.grid, "A5", plan.route)[-1], plan.target.room)

    def test_same_percept_different_targets_give_different_moves(self):
        left_old = corridor_agent()                  # A1 en eski -> sola
        right_old = GoalBasedAgent(grid=Grid(1, 5), rng=random.Random(0))
        remember(right_old, ("A5", CLEAN), *[("A3", CLEAN)] * 6, ("A1", CLEAN), ("A2", CLEAN), ("A4", CLEAN))
        self.assertIs(left_old.act(("A3", CLEAN)), L)
        self.assertIs(right_old.act(("A3", CLEAN)), R)

    def test_goal_and_model_agents_differ_in_plan_example(self):
        self.assertIs(corridor_agent(GoalBasedAgent).act(("A3", CLEAN)), L)
        self.assertIs(corridor_agent(ModelBasedAgent).act(("A3", CLEAN)), R)

    def test_plan_snapshot_is_read_only(self):
        agent = corridor_agent()
        step(agent, "A3", CLEAN)
        plan = agent.plan_snapshot()
        with self.assertRaises(AttributeError):
            plan.route = ()
        with self.assertRaises(AttributeError):
            plan.target.room = "A5"
        self.assertIsInstance(plan.route, tuple)
        self.assertEqual(agent.plan_snapshot(), plan)

    def test_no_oscillation_target_changes_only_on_arrival(self):
        """Kirlenmesiz koşularda hedef yalnızca hedefe varınca değişir."""
        for rows, cols in [(1, 6), (3, 3), (4, 5), (6, 6)]:
            for seed in range(5):
                env = Environment(rng=random.Random(seed), rows=rows, cols=cols)
                agent = GoalBasedAgent(grid=env.grid, rng=random.Random(seed + 100))
                previous = agent.plan_snapshot()
                for _ in range(400):
                    room = env.location
                    action = agent.act(env.percept())
                    plan = agent.plan_snapshot()
                    if plan.version != previous.version:
                        with self.subTest(grid=(rows, cols), seed=seed, version=plan.version):
                            self.assertIn(plan.reason, {REPLAN_FIRST, REPLAN_REACHED})
                            if plan.reason == REPLAN_REACHED:
                                self.assertEqual(room, previous.target.room)
                    env.execute(action)
                    agent.action_result(action, succeeded=True)
                    previous = agent.plan_snapshot()


if __name__ == "__main__":
    unittest.main()
