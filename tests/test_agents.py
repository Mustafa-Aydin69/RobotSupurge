"""Ajan (agents.py) testleri."""

import itertools
import random
import unittest

from agents import ReflexAgent
from environment import Action, Environment, Grid, Status


class ReflexRuleTableTests(unittest.TestCase):
    """Ödev tanımındaki karar tablosunun dört kuralı."""

    def setUp(self):
        self.agent = ReflexAgent()

    def test_a_dirty_cleans(self):
        self.assertIs(self.agent.act(("A", Status.DIRTY)), Action.CLEAN)

    def test_a_clean_goes_right(self):
        self.assertIs(self.agent.act(("A", Status.CLEAN)), Action.RIGHT)

    def test_b_dirty_cleans(self):
        self.assertIs(self.agent.act(("B", Status.DIRTY)), Action.CLEAN)

    def test_b_clean_goes_left(self):
        self.assertIs(self.agent.act(("B", Status.CLEAN)), Action.LEFT)


class ReflexStatelessTests(unittest.TestCase):
    """Ajan geçmişi kullanmamalı: aynı algıya her zaman aynı eylemi vermeli."""

    PERCEPTS = [(room, status) for room in ("A", "B") for status in Status]

    def test_agent_has_no_instance_state(self):
        agent = ReflexAgent()
        self.assertFalse(hasattr(agent, "__dict__"))
        with self.assertRaises(AttributeError):
            agent.history = []

    def test_decision_does_not_depend_on_history(self):
        expected = {p: ReflexAgent().act(p) for p in self.PERCEPTS}
        agent = ReflexAgent()
        rng = random.Random(7)
        # Rastgele bir algı geçmişinden sonra bile kararlar değişmemeli.
        for _ in range(500):
            percept = rng.choice(self.PERCEPTS)
            self.assertIs(agent.act(percept), expected[percept])

    def test_returns_exactly_one_action(self):
        agent = ReflexAgent()
        for percept in self.PERCEPTS:
            self.assertIsInstance(agent.act(percept), Action)


class ReflexInEnvironmentTests(unittest.TestCase):
    """Ajan ortamla birlikte çalıştığında beklenen davranış."""

    def run_steps(self, env, agent, n):
        actions = []
        for _ in range(n):
            action = agent.act(env.percept())
            env.execute(action)
            actions.append(action)
        return actions

    def test_dirty_room_is_cleaned_then_agent_moves(self):
        env = Environment(location="A", statuses={"A": Status.DIRTY, "B": Status.CLEAN})
        actions = self.run_steps(env, ReflexAgent(), 2)
        # Temizleme ve hareket ayrı adımlardır.
        self.assertEqual(actions, [Action.CLEAN, Action.RIGHT])
        self.assertEqual(env.status_of("A"), Status.CLEAN)
        self.assertEqual(env.location, "B")

    def test_clean_room_moves_directly(self):
        env = Environment(location="B", statuses={"A": Status.DIRTY, "B": Status.CLEAN})
        actions = self.run_steps(env, ReflexAgent(), 1)
        self.assertEqual(actions, [Action.LEFT])
        self.assertEqual(env.location, "A")

    def test_agent_never_leaves_environment(self):
        agent = ReflexAgent()
        for location, a, b in itertools.product(("A", "B"), Status, Status):
            env = Environment(
                rng=random.Random(1), dirt_probability=0.5,
                location=location, statuses={"A": a, "B": b},
            )
            for _ in range(200):
                action = agent.act(env.percept())
                if action is not Action.CLEAN:
                    self.assertTrue(env.can_move(action))
                env.execute(action)  # sınır dışı olsaydı ValueError fırlatırdı
                env.dirty_tick()


ALL_GRID_SIZES = [(r, c) for r in range(1, 7) for c in range(1, 7) if r * c >= 2]


class ReflexGridTests(unittest.TestCase):
    """1×2 dışındaki grid'lerde refleks ajan.

    Not: Ajanın bir rastgele sayı üreteci (rng) vardır. Bu, geçmiş algı belleği
    değildir: rng hangi odaların görüldüğünü saklamaz, yalnızca geçerli
    hareketler arasından seçimi rastgele yapar. Testlerde sabit seed kullanılarak
    rastgele seçimler deterministik hale getirilir.
    """

    def make_agent(self, rows, cols, seed=0):
        return ReflexAgent(grid=Grid(rows, cols), rng=random.Random(seed))

    def test_dirty_room_is_always_cleaned(self):
        for rows, cols in ALL_GRID_SIZES:
            agent = self.make_agent(rows, cols)
            for room in agent.grid.rooms:
                self.assertIs(agent.act((room, Status.DIRTY)), Action.CLEAN)

    def test_clean_room_chooses_only_valid_moves_and_all_of_them(self):
        """Her grid boyutunda her oda için: seçimler = geçerli hareketler kümesi."""
        for rows, cols in ALL_GRID_SIZES:
            agent = self.make_agent(rows, cols, seed=rows * 10 + cols)
            for room in agent.grid.rooms:
                chosen = {agent.act((room, Status.CLEAN)) for _ in range(60)}
                with self.subTest(grid=(rows, cols), room=room):
                    self.assertEqual(chosen, set(agent.grid.valid_moves(room)))

    def test_1x2_still_uses_rule_table_without_randomness(self):
        agent = ReflexAgent(grid=Grid(1, 2), rng=random.Random(0))
        rng_state = agent._rng.getstate()
        for _ in range(50):
            self.assertIs(agent.act(("A", Status.CLEAN)), Action.RIGHT)
            self.assertIs(agent.act(("B", Status.CLEAN)), Action.LEFT)
        self.assertEqual(agent._rng.getstate(), rng_state, "1×2'de rastgelelik kullanılmamalı")

    def test_vertical_2x1_moves_only_up_and_down(self):
        agent = self.make_agent(2, 1)
        for _ in range(20):
            self.assertIs(agent.act(("A1", Status.CLEAN)), Action.DOWN)
            self.assertIs(agent.act(("B1", Status.CLEAN)), Action.UP)

    def test_same_seed_gives_same_choices(self):
        percepts = [(room, Status.CLEAN) for room in Grid(4, 4).rooms] * 10
        a = [self.make_agent(4, 4, seed=5).act(p) for p in percepts]
        b = [self.make_agent(4, 4, seed=5).act(p) for p in percepts]
        self.assertEqual(a, b)

    def test_no_memory_of_past_percepts(self):
        """Ajanın tuttuğu alanlar yalnızca grid ve rng; adımlar boyunca grid değişmez."""
        agent = self.make_agent(3, 3)
        self.assertEqual(ReflexAgent.__slots__, ("_grid", "_rng"))
        self.assertFalse(hasattr(agent, "__dict__"))
        grid_before = agent.grid
        rng = random.Random(1)
        for _ in range(300):
            agent.act((rng.choice(agent.grid.rooms), rng.choice(list(Status))))
        self.assertIs(agent.grid, grid_before)
        with self.assertRaises(AttributeError):
            agent.visited = set()

    def test_history_does_not_change_possible_choices(self):
        """Geçmiş ne olursa olsun, bir algı için olası eylemler kümesi aynıdır."""
        percept = ("B2", Status.CLEAN)
        fresh = {self.make_agent(3, 3, seed=s).act(percept) for s in range(200)}

        agent = self.make_agent(3, 3, seed=99)
        rng = random.Random(2)
        for _ in range(500):  # uzun ve rastgele bir algı geçmişi
            agent.act((rng.choice(agent.grid.rooms), rng.choice(list(Status))))
        after_history = {agent.act(percept) for _ in range(200)}
        self.assertEqual(after_history, fresh)

    def test_agent_never_leaves_any_grid(self):
        """Bütün grid boyutlarında, kirlenmeli uzun koşularda sınır ihlali olmaz."""
        for rows, cols in ALL_GRID_SIZES:
            env = Environment(rng=random.Random(rows), dirt_probability=0.3, rows=rows, cols=cols)
            agent = ReflexAgent(grid=env.grid, rng=random.Random(cols))
            for i in range(300):
                action = agent.act(env.percept())
                if action is not Action.CLEAN:
                    self.assertTrue(env.can_move(action))
                env.execute(action)  # sınır dışı olsaydı ValueError fırlatırdı
                if i % 5 == 0:
                    env.dirty_tick()


if __name__ == "__main__":
    unittest.main()
