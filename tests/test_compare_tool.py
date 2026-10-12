"""Ölçüm aracı (tools/compare_agents.py) testleri."""

import random
import unittest

from environment import Environment, Status
from simulation import Simulation
from tools.compare_agents import (
    apply_common_dirt, common_dirt_rng, coverage_steps, mean_clean_ratio, same_initial_state,
)


class CoverageMeasurementTests(unittest.TestCase):
    def test_coverage_step_matches_manual_count(self):
        for agent_type in ("reflex", "model", "goal"):
            for seed in range(5):
                sim = Simulation(seed=seed, rows=3, cols=3, agent_type=agent_type,
                                 dirt_probability=0.0, clock=lambda: 0.0)
                sim.start()
                perceived, expected = set(), None
                while expected is None:
                    record = sim.step()
                    perceived.add(record.room)
                    if len(perceived) == 9:
                        expected = record.step
                with self.subTest(agent=agent_type, seed=seed):
                    self.assertEqual(coverage_steps(agent_type, 3, 3, seed), expected)

    def test_starting_room_counts_at_step_one(self):
        """1×2: başlangıç odası 1. adımda algılanır; kirliyse önce temizlenir."""
        for seed in range(10):
            env = Simulation(seed=seed).environment
            expected = 3 if env.status_of(env.location) is Status.DIRTY else 2
            for agent_type in ("reflex", "model", "goal"):
                with self.subTest(seed=seed, agent=agent_type):
                    self.assertEqual(coverage_steps(agent_type, 1, 2, seed), expected)

    def test_measurements_are_reproducible(self):
        self.assertEqual(coverage_steps("reflex", 4, 4, 3), coverage_steps("reflex", 4, 4, 3))
        for mode in ("independent", "common"):
            self.assertEqual(
                mean_clean_ratio("model", 3, 3, 2, steps=300, mode=mode),
                mean_clean_ratio("model", 3, 3, 2, steps=300, mode=mode),
            )

    def test_all_three_agents_are_compared(self):
        from tools.compare_agents import AGENT_KEYS
        self.assertEqual(AGENT_KEYS, ("reflex", "model", "goal"))
        self.assertEqual(mean_clean_ratio("goal", 3, 3, 1, steps=200, mode="common"),
                         mean_clean_ratio("goal", 3, 3, 1, steps=200, mode="common"))

    def test_same_seed_gives_both_agents_same_start(self):
        for seed in range(20):
            self.assertTrue(same_initial_state(4, 5, seed))


class CommonDirtTests(unittest.TestCase):
    def test_draw_sequence_does_not_depend_on_room_states(self):
        """Ortak biçimde her oda için sayı çekilir; dizi ajanın davranışından bağımsızdır."""
        clean = Environment(rng=random.Random(0), rows=2, cols=2, location="A1",
                            statuses={r: Status.CLEAN for r in ("A1", "A2", "B1", "B2")})
        dirty = Environment(rng=random.Random(0), rows=2, cols=2, location="A1",
                            statuses={r: Status.DIRTY for r in ("A1", "A2", "B1", "B2")})
        rng_a, rng_b = common_dirt_rng(5), common_dirt_rng(5)
        for _ in range(10):
            apply_common_dirt(clean, rng_a, 0.3)
            apply_common_dirt(dirty, rng_b, 0.3)
        self.assertEqual(rng_a.random(), rng_b.random())

    def test_only_clean_rooms_become_dirty(self):
        env = Environment(rng=random.Random(0), rows=1, cols=3, location="A1",
                          statuses={"A1": Status.DIRTY, "A2": Status.CLEAN, "A3": Status.CLEAN})
        self.assertEqual(apply_common_dirt(env, common_dirt_rng(0), 1.0), ["A2", "A3"])
        self.assertTrue(all(s is Status.DIRTY for s in env.statuses().values()))

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            mean_clean_ratio("reflex", 1, 2, 0, steps=10, mode="other")


if __name__ == "__main__":
    unittest.main()
