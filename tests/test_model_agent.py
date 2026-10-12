"""Model tabanlı ajan (agents.ModelBasedAgent) testleri."""

import copy
import random
import unittest
from pathlib import Path

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

    def test_successful_move_updates_believed_location_only(self):
        agent = make_agent()
        action = agent.act(("B2", CLEAN))
        self.assertEqual(agent.model_snapshot().location, "B2")
        agent.action_result(action, succeeded=True)
        snap = agent.model_snapshot()
        self.assertEqual(snap.location, agent.grid.neighbor("B2", action))
        self.assertEqual(set(snap.observations), {"B2"})

    def test_failed_move_keeps_believed_location(self):
        agent = make_agent()
        action = agent.act(("B2", CLEAN))
        agent.action_result(action, succeeded=False)
        self.assertEqual(agent.model_snapshot().location, "B2")

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


ALL_GRID_SIZES = [(r, c) for r in range(1, 7) for c in range(1, 7) if r * c >= 2]


class LongRunTests(unittest.TestCase):
    def test_long_runs_stay_in_bounds_with_consistent_model(self):
        """35 grid boyutunda kirlenmeli 2000 adımlık koşular."""
        from simulation import Simulation

        for rows, cols in ALL_GRID_SIZES:
            sim = Simulation(seed=rows * 7 + cols, rows=rows, cols=cols, agent_type="model", clock=lambda: 0.0)
            sim.start()
            rooms = set(sim.environment.rooms)
            for i in range(2000):
                sim.step()  # sınır dışı bir hareket ValueError fırlatırdı
                if i % 4 == 0:
                    sim.dirty_tick()
            snap = sim.agent.model_snapshot()
            with self.subTest(grid=(rows, cols)):
                self.assertIn(sim.environment.location, rooms)
                self.assertLessEqual(set(snap.observations), rooms)
                self.assertEqual(snap.step, 2000)
                self.assertTrue(all(snap.age_of(room) >= 0 for room in snap.observations))

    def test_all_rooms_visited_in_dirt_free_runs(self):
        """Ölçüm: kirlenme kapalıyken bu seed'lerde her oda ziyaret edildi.

        Bu her koşul için kanıtlanmış bir garanti değildir; yalnızca test edilen
        boyut ve seed'ler için gözlenen bir sonuçtur.
        """
        from simulation import Simulation

        for rows, cols in [(1, 6), (3, 3), (4, 4), (6, 6)]:
            for seed in range(10):
                sim = Simulation(seed=seed, rows=rows, cols=cols, agent_type="model",
                                 dirt_probability=0.0, clock=lambda: 0.0)
                sim.start()
                visited = {sim.step().room for _ in range(50 * rows * cols)}
                with self.subTest(grid=(rows, cols), seed=seed):
                    self.assertEqual(visited, set(sim.environment.rooms))


class DifferenceFromReflexTests(unittest.TestCase):
    """Aynı durumda refleks ve model tabanlı ajanların davranış farkı."""

    def test_corridor_middle_after_coming_from_left(self):
        from agents import ReflexAgent

        # Model tabanlı ajan A1'i bilir, A3'ü bilmez: A2'de her zaman sağa gider.
        model = make_agent(1, 3)
        step(model, "A1", CLEAN)
        self.assertEqual({decide(model, "A2", seed) for seed in range(30)}, {R})

        # Refleks ajan geçmişi kullanmaz: aynı algıda iki yönü de seçebilir.
        reflex_choices = {
            ReflexAgent(grid=Grid(1, 3), rng=random.Random(seed)).act(("A2", CLEAN)) for seed in range(30)
        }
        self.assertEqual(reflex_choices, {L, R})

    def test_model_agent_never_skips_an_unknown_neighbor(self):
        """Uzun koşu boyunca: bilinmeyen komşu varken bilinen bir komşuya gidilmez."""
        from simulation import Simulation

        sim = Simulation(seed=4, rows=5, cols=5, agent_type="model", clock=lambda: 0.0)
        sim.start()
        grid = sim.environment.grid
        for i in range(1500):
            known = set(sim.agent.model_snapshot().observations)
            room = sim.environment.location
            record = sim.step()
            if record.action is not Action.CLEAN:
                neighbors = {grid.neighbor(room, m) for m in grid.valid_moves(room)}
                target = grid.neighbor(room, record.action)
                if neighbors - known - {room}:
                    self.assertNotIn(target, known, f"adım {record.step}")
            if i % 4 == 0:
                sim.dirty_tick()


class KnowledgeFreshnessTests(unittest.TestCase):
    """Otomatik kirlenme altında iç modelin güncelliği (simülasyon düzeyinde)."""

    def make_sim(self, seed=1, rows=3, cols=3):
        from simulation import Simulation

        sim = Simulation(seed=seed, rows=rows, cols=cols, agent_type="model",
                         dirt_probability=1.0, clock=lambda: 0.0)
        sim.start()
        return sim

    def test_remote_redirtying_is_not_learned(self):
        sim = self.make_sim()
        for _ in range(12):
            sim.step()
        before = sim.agent.model_snapshot()
        sim.dirty_tick()  # olasılık 1: bütün temiz odalar kirlenir
        after = sim.agent.model_snapshot()
        self.assertEqual(dict(after.observations), dict(before.observations))
        self.assertEqual((after.step, after.location), (before.step, before.location))

    def test_old_clean_belief_is_not_synchronized_with_reality(self):
        sim = self.make_sim()
        for _ in range(12):
            sim.step()
        sim.dirty_tick()
        snapshot = sim.agent.model_snapshot()
        believed_clean_but_dirty = {
            room for room, obs in snapshot.observations.items()
            if obs.status is CLEAN and sim.environment.status_of(room) is DIRTY
        }
        # Model gerçeği kendiliğinden öğrenmez: eski "temiz" bilgisi kalır.
        self.assertTrue(believed_clean_but_dirty)

    def test_revisit_corrects_old_knowledge(self):
        sim = self.make_sim()
        for _ in range(12):
            sim.step()
        sim.dirty_tick()
        snapshot = sim.agent.model_snapshot()
        outdated = {
            room for room, obs in snapshot.observations.items()
            if obs.status is CLEAN and sim.environment.status_of(room) is DIRTY
            and room != sim.environment.location
        }
        corrected = None
        for _ in range(200):
            record = sim.step()
            if record.room in outdated:
                corrected = record
                break
        self.assertIsNotNone(corrected, "Eski bilgili odalardan biri yeniden ziyaret edilmeli")
        self.assertIs(corrected.status, DIRTY)          # güncel algı eski "temiz" bilgisini ezdi
        self.assertIs(corrected.action, Action.CLEAN)
        obs = sim.agent.model_snapshot().observations[corrected.room]
        self.assertEqual((obs.status, obs.source), (CLEAN, SOURCE_INFERENCE))

    def test_failed_action_in_simulation_leaves_no_wrong_inference(self):
        sim = self.make_sim()
        sim.step()
        location = sim.environment.location
        steps_before = sim.step_count

        def failing_execute(action):
            raise ValueError("test: ortam eylemi reddetti")

        sim.environment.execute = failing_execute
        with self.assertRaises(ValueError):
            sim.step()
        snapshot = sim.agent.model_snapshot()
        obs = snapshot.observations[location]
        self.assertEqual(obs.source, SOURCE_PERCEPT, "Başarısız eylemden çıkarım yapılmamalı")
        self.assertEqual(snapshot.location, location, "Başarısız harekette konum değişmemeli")
        self.assertEqual(sim.step_count, steps_before)

    def test_agent_does_not_depend_on_gui_or_stale_threshold(self):
        import agents

        source = Path(agents.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import gui", source)
        self.assertNotIn("stale", source.lower())
        self.assertFalse(any("stale" in name or "threshold" in name for name in dir(ModelBasedAgent)))


if __name__ == "__main__":
    unittest.main()
