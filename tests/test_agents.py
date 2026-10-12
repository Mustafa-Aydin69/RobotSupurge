"""Ajan (agents.py) testleri."""

import itertools
import random
import unittest

from agents import ReflexAgent
from environment import Action, Environment, Status


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


if __name__ == "__main__":
    unittest.main()
