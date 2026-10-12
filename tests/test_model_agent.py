"""Model tabanlı ajan (agents.ModelBasedAgent) testleri."""

import copy
import random
import unittest

from agents import SOURCE_INFERENCE, SOURCE_PERCEPT, ModelBasedAgent, Observation
from environment import Action, Grid, Status

CLEAN, DIRTY = Status.CLEAN, Status.DIRTY


def make_agent(rows=3, cols=3, seed=0):
    return ModelBasedAgent(grid=Grid(rows, cols), rng=random.Random(seed))


def decide(agent, room, seed):
    """Ajanın kopyası üzerinde, verilen eşitlik-bozma seed'iyle bir karar alır.

    Ajanın kendisi değişmez; böylece aynı model durumunda farklı seed'lerle
    hangi eylemlerin seçilebildiği gözlemlenebilir.
    """
    clone = copy.deepcopy(agent)
    clone._rng.seed(seed)
    return clone.act((room, CLEAN))


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


L, R, U, D = Action.LEFT, Action.RIGHT, Action.UP, Action.DOWN


class MoveStrategyTests(unittest.TestCase):
    def test_corridor_sweeps_end_to_end(self):
        """Plan örneği 1: 1×3 koridorda düzenli süpürme."""
        agent = make_agent(1, 3)
        actions = [step(agent, room, CLEAN) for room in ("A1", "A2", "A3", "A2", "A1", "A2")]
        # A2'de: önce bilinmeyen A3; sonra daha eski olan A1; sonra yine daha eski olan A3.
        self.assertEqual(actions, [R, R, L, L, R, R])

    def test_unknown_neighbor_has_priority_over_oldest(self):
        """Plan örneği 2: B2'de bilinmeyen B1, yaşı 7 olan A2/C2'ye tercih edilir."""
        agent = make_agent(3, 3)
        for room in ("A2", "C2", "A1", "A3", "C1", "C3", "B3"):
            step(agent, room, CLEAN)
        # B2'ye gelindiğinde yaşlar: A2=7, C2=6, ..., B3=1; B1 bilinmiyor.
        for seed in range(20):
            self.assertIs(decide(agent, "B2", seed), L)

    def test_oldest_neighbor_is_chosen_when_all_known(self):
        agent = make_agent(3, 3)
        for room in ("B1", "A2", "B3", "C2"):   # B1 en eski, C2 en yeni
            step(agent, room, CLEAN)
        for seed in range(20):
            self.assertIs(decide(agent, "B2", seed), L)

    def test_tie_is_broken_among_equal_candidates_only(self):
        agent = make_agent(3, 3)
        # B1 ve B3 biliniyor, A2 ve C2 bilinmiyor: eşit öncelikli adaylar
        # yalnızca A2 (Yukarı) ve C2 (Aşağı) olmalı.
        step(agent, "B1", CLEAN)
        step(agent, "B3", CLEAN)
        chosen = {decide(agent, "B2", seed) for seed in range(50)}
        self.assertEqual(chosen, {U, D})

    def test_tie_break_is_reproducible_with_seed(self):
        def run(seed):
            agent = make_agent(4, 4, seed=seed)
            return [step(agent, room, CLEAN) for room in ("B2", "B2", "B2", "B2")]
        self.assertEqual(run(3), run(3))

    def test_redirtied_old_room_is_revisited_and_cleaned(self):
        """Plan örneği 3: eski bilgi yeniden kontrol edilir, kirli bulunursa temizlenir."""
        agent = make_agent(3, 1)  # dikey koridor: A1, B1, C1
        self.assertIs(step(agent, "A1", CLEAN), D)
        self.assertIs(step(agent, "B1", CLEAN), D)     # C1 bilinmiyor
        self.assertIs(step(agent, "C1", CLEAN), U)
        self.assertIs(step(agent, "B1", CLEAN), U)     # A1 (yaş 3) C1'den (yaş 1) eski
        self.assertIs(step(agent, "A1", DIRTY), Action.CLEAN)  # arada kirlenmiş
        self.assertEqual(agent.model_snapshot().observations["A1"].source, SOURCE_INFERENCE)

    def test_always_chooses_a_valid_move(self):
        for rows, cols in [(1, 2), (2, 1), (1, 6), (3, 3), (6, 6)]:
            agent = make_agent(rows, cols, seed=rows + cols)
            rng = random.Random(1)
            for _ in range(500):
                room = rng.choice(agent.grid.rooms)
                action = step(agent, room, rng.choice([CLEAN, DIRTY]))
                if action is not Action.CLEAN:
                    self.assertIn(action, agent.grid.valid_moves(room))

    def test_past_percepts_change_the_decision(self):
        """Aynı güncel algı, farklı geçmişlerle farklı karara yol açar."""
        came_from_left = make_agent(1, 3)
        step(came_from_left, "A1", CLEAN)
        came_from_right = make_agent(1, 3)
        step(came_from_right, "A3", CLEAN)
        for seed in range(20):
            self.assertIs(decide(came_from_left, "A2", seed), R)
            self.assertIs(decide(came_from_right, "A2", seed), L)

    def test_1x2_moves_match_reflex_table(self):
        agent = make_agent(1, 2)
        self.assertEqual([step(agent, r, CLEAN) for r in ("A", "B", "A", "B")], [R, L, R, L])


if __name__ == "__main__":
    unittest.main()
