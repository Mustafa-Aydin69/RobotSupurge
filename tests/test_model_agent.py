"""Model tabanlı ajan (agents.ModelBasedAgent) testleri."""

import random
import unittest

from agents import SOURCE_INFERENCE, SOURCE_PERCEPT, ModelBasedAgent, Observation
from environment import Action, Grid, Status

CLEAN, DIRTY = Status.CLEAN, Status.DIRTY


def make_agent(rows=3, cols=3, seed=0):
    return ModelBasedAgent(grid=Grid(rows, cols), rng=random.Random(seed))


def step(agent, room, status, succeeded=True):
    """Simülasyonun yaptığı gibi: algı -> karar -> eylem sonucu bildirimi."""
    action = agent.act((room, status))
    agent.action_result(action, succeeded)
    return action


class ModelUpdateTests(unittest.TestCase):
    def test_model_is_empty_at_start(self):
        snap = make_agent().model_snapshot()
        self.assertEqual((snap.step, snap.location, dict(snap.observations)), (0, None, {}))

    def test_percept_is_written_to_model(self):
        agent = make_agent()
        agent.act(("B2", CLEAN))
        snap = agent.model_snapshot()
        self.assertEqual(snap.step, 1)
        self.assertEqual(snap.location, "B2")
        self.assertEqual(dict(snap.observations), {"B2": Observation(CLEAN, 1, SOURCE_PERCEPT)})

    def test_only_perceived_rooms_are_known(self):
        agent = make_agent()
        for room in ("A1", "A2", "B2"):
            step(agent, room, CLEAN)
        self.assertEqual(set(agent.model_snapshot().observations), {"A1", "A2", "B2"})

    def test_current_percept_overrides_old_knowledge(self):
        agent = make_agent()
        step(agent, "A1", CLEAN)
        step(agent, "A2", CLEAN)
        agent.act(("A1", DIRTY))  # A1 arada kirlenmiş
        obs = agent.model_snapshot().observations["A1"]
        self.assertEqual(obs, Observation(DIRTY, 3, SOURCE_PERCEPT))

    def test_age_is_measured_in_agent_steps(self):
        agent = make_agent()
        step(agent, "A1", CLEAN)
        step(agent, "A2", CLEAN)
        step(agent, "A3", CLEAN)
        snap = agent.model_snapshot()
        self.assertEqual([snap.age_of(r) for r in ("A1", "A2", "A3", "C3")], [2, 1, 0, None])

    def test_unknown_room_name_is_rejected(self):
        with self.assertRaises(ValueError):
            make_agent().act(("Z9", CLEAN))


class InferenceTests(unittest.TestCase):
    def test_successful_clean_records_inference(self):
        agent = make_agent()
        action = agent.act(("B2", DIRTY))
        self.assertIs(action, Action.CLEAN)
        # Karar verildi ama sonuç henüz bildirilmedi: model yalnızca algıyı bilir.
        self.assertEqual(agent.model_snapshot().observations["B2"].status, DIRTY)
        agent.action_result(Action.CLEAN, succeeded=True)
        self.assertEqual(agent.model_snapshot().observations["B2"], Observation(CLEAN, 1, SOURCE_INFERENCE))

    def test_failed_clean_makes_no_inference(self):
        agent = make_agent()
        agent.act(("B2", DIRTY))
        agent.action_result(Action.CLEAN, succeeded=False)
        self.assertEqual(agent.model_snapshot().observations["B2"], Observation(DIRTY, 1, SOURCE_PERCEPT))

    def test_result_for_a_different_action_is_ignored(self):
        agent = make_agent()
        agent.act(("B2", DIRTY))
        agent.action_result(Action.LEFT, succeeded=True)   # karar verilen eylem değil
        self.assertEqual(agent.model_snapshot().observations["B2"].status, DIRTY)

    def test_result_without_pending_action_is_ignored(self):
        agent = make_agent()
        agent.action_result(Action.CLEAN, succeeded=True)
        self.assertEqual(dict(agent.model_snapshot().observations), {})

    def test_move_result_adds_no_knowledge_about_target(self):
        agent = make_agent()
        action = step(agent, "B2", CLEAN)
        target = agent.grid.neighbor("B2", action)
        self.assertNotIn(target, agent.model_snapshot().observations)

    def test_next_percept_confirms_inference(self):
        agent = make_agent()
        step(agent, "B2", DIRTY)
        agent.act(("B2", CLEAN))
        self.assertEqual(agent.model_snapshot().observations["B2"], Observation(CLEAN, 2, SOURCE_PERCEPT))

    def test_next_percept_corrects_inference(self):
        agent = make_agent()
        step(agent, "B2", DIRTY)
        action = agent.act(("B2", DIRTY))  # arada yeniden kirlenmiş
        self.assertIs(action, Action.CLEAN)
        self.assertEqual(agent.model_snapshot().observations["B2"], Observation(DIRTY, 2, SOURCE_PERCEPT))


class SnapshotSafetyTests(unittest.TestCase):
    def test_snapshot_cannot_modify_agent_memory(self):
        agent = make_agent()
        step(agent, "A1", CLEAN)
        snap = agent.model_snapshot()
        with self.assertRaises(TypeError):
            snap.observations["A1"] = Observation(DIRTY, 99, SOURCE_PERCEPT)
        with self.assertRaises(TypeError):
            del snap.observations["A1"]
        with self.assertRaises(AttributeError):
            snap.observations["A1"].status = DIRTY
        with self.assertRaises(AttributeError):
            snap.step = 50
        self.assertEqual(agent.model_snapshot().observations["A1"], Observation(CLEAN, 1, SOURCE_PERCEPT))

    def test_snapshot_is_a_copy_not_a_live_view(self):
        agent = make_agent()
        step(agent, "A1", CLEAN)
        old = agent.model_snapshot()
        step(agent, "A2", CLEAN)
        self.assertEqual(set(old.observations), {"A1"})
        self.assertEqual(old.step, 1)

    def test_agent_has_no_environment_access(self):
        agent = make_agent()
        self.assertEqual(
            set(ModelBasedAgent.__slots__),
            {"_grid", "_rng", "_memory", "_step", "_location", "_pending"},
        )
        self.assertFalse(hasattr(agent, "__dict__"))
        with self.assertRaises(AttributeError):
            agent.environment = object()


if __name__ == "__main__":
    unittest.main()
