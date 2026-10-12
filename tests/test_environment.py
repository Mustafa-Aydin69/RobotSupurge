"""Ortam (environment.py) testleri."""

import random
import unittest

from environment import ROOMS, Action, Environment, Status


def make_env(location="A", a=Status.CLEAN, b=Status.CLEAN, seed=0, dirt_probability=0.3):
    return Environment(
        rng=random.Random(seed),
        dirt_probability=dirt_probability,
        location=location,
        statuses={"A": a, "B": b},
    )


class PerceptTests(unittest.TestCase):
    def test_percept_contains_only_current_room(self):
        env = make_env(location="A", a=Status.DIRTY, b=Status.CLEAN)
        self.assertEqual(env.percept(), ("A", Status.DIRTY))

        env = make_env(location="B", a=Status.DIRTY, b=Status.CLEAN)
        self.assertEqual(env.percept(), ("B", Status.CLEAN))


class CleanTests(unittest.TestCase):
    def test_clean_cleans_only_current_room(self):
        env = make_env(location="A", a=Status.DIRTY, b=Status.DIRTY)
        env.execute(Action.CLEAN)
        self.assertEqual(env.status_of("A"), Status.CLEAN)
        self.assertEqual(env.status_of("B"), Status.DIRTY)
        self.assertEqual(env.location, "A", "Temizleme ajanı hareket ettirmemeli")


class MoveTests(unittest.TestCase):
    def test_right_from_a_goes_to_b(self):
        env = make_env(location="A")
        env.execute(Action.RIGHT)
        self.assertEqual(env.location, "B")

    def test_left_from_b_goes_to_a(self):
        env = make_env(location="B")
        env.execute(Action.LEFT)
        self.assertEqual(env.location, "A")

    def test_move_does_not_change_room_statuses(self):
        env = make_env(location="A", a=Status.DIRTY, b=Status.CLEAN)
        env.execute(Action.RIGHT)
        self.assertEqual(env.statuses(), {"A": Status.DIRTY, "B": Status.CLEAN})

    def test_boundary_left_of_a_is_rejected(self):
        env = make_env(location="A")
        self.assertFalse(env.can_move(Action.LEFT))
        with self.assertRaises(ValueError):
            env.execute(Action.LEFT)
        self.assertEqual(env.location, "A")

    def test_boundary_right_of_b_is_rejected(self):
        env = make_env(location="B")
        self.assertFalse(env.can_move(Action.RIGHT))
        with self.assertRaises(ValueError):
            env.execute(Action.RIGHT)
        self.assertEqual(env.location, "B")

    def test_clean_is_not_a_move(self):
        env = make_env()
        self.assertFalse(env.can_move(Action.CLEAN))
        with self.assertRaises(ValueError):
            env.move(Action.CLEAN)


class DirtTests(unittest.TestCase):
    def test_dirty_tick_with_probability_one_dirties_all_clean_rooms(self):
        env = make_env(dirt_probability=1.0)
        self.assertEqual(env.dirty_tick(), ["A", "B"])
        self.assertEqual(env.statuses(), {"A": Status.DIRTY, "B": Status.DIRTY})

    def test_dirty_tick_with_probability_zero_changes_nothing(self):
        env = make_env(dirt_probability=0.0)
        for _ in range(100):
            self.assertEqual(env.dirty_tick(), [])
        self.assertEqual(env.statuses(), {"A": Status.CLEAN, "B": Status.CLEAN})

    def test_already_dirty_rooms_are_not_reported(self):
        env = make_env(a=Status.DIRTY, b=Status.CLEAN, dirt_probability=1.0)
        self.assertEqual(env.dirty_tick(), ["B"])

    def test_dirty_tick_does_not_move_agent(self):
        env = make_env(location="B", dirt_probability=1.0)
        env.dirty_tick()
        self.assertEqual(env.location, "B")

    def test_dirt_rate_is_about_thirty_percent(self):
        # Her tetiklemede temiz odaların her biri bağımsız %30 olasılıkla kirlenmeli.
        rng = random.Random(12345)
        clean = {room: Status.CLEAN for room in ROOMS}
        trials = 20000
        dirtied = 0
        for _ in range(trials):
            env = Environment(rng=rng, dirt_probability=0.3, location="A", statuses=clean)
            dirtied += len(env.dirty_tick())
        rate = dirtied / (trials * len(ROOMS))
        self.assertAlmostEqual(rate, 0.3, delta=0.02)

    def test_invalid_probability_is_rejected(self):
        with self.assertRaises(ValueError):
            Environment(dirt_probability=1.5)


class RandomInitTests(unittest.TestCase):
    def test_same_seed_gives_same_initial_state(self):
        for seed in range(20):
            a = Environment(rng=random.Random(seed))
            b = Environment(rng=random.Random(seed))
            self.assertEqual((a.location, a.statuses()), (b.location, b.statuses()))

    def test_random_init_covers_all_states(self):
        seen = set()
        for seed in range(200):
            env = Environment(rng=random.Random(seed))
            seen.add((env.location, env.status_of("A"), env.status_of("B")))
        self.assertEqual(len(seen), 8, "2 konum x 4 oda durumu kombinasyonunun hepsi görülmeli")


if __name__ == "__main__":
    unittest.main()
