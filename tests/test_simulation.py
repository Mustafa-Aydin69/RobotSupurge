"""Simülasyon (simulation.py) testleri."""

import unittest

from environment import Action, Status
from simulation import DirtRecord, Simulation, SimulationState, StepRecord


class FakeClock:
    """Testlerde zamanı elle ilerletmek için sahte saat."""

    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make_sim(seed=1, dirt_probability=0.3, location=None, statuses=None):
    clock = FakeClock()
    sim = Simulation(
        seed=seed, dirt_probability=dirt_probability,
        location=location, statuses=statuses, clock=clock,
    )
    return sim, clock


ALL_CLEAN = {"A": Status.CLEAN, "B": Status.CLEAN}


class StepTests(unittest.TestCase):
    def test_step_performs_exactly_one_action(self):
        sim, _ = make_sim(location="A", statuses={"A": Status.DIRTY, "B": Status.DIRTY})
        sim.start()

        record = sim.step()
        self.assertEqual(record.action, Action.CLEAN)
        # Temizlendi ama aynı adımda hareket edilmedi.
        self.assertEqual(sim.environment.location, "A")
        self.assertEqual(sim.environment.status_of("A"), Status.CLEAN)
        self.assertEqual(sim.environment.status_of("B"), Status.DIRTY)
        self.assertEqual((sim.step_count, sim.clean_count, sim.move_count), (1, 1, 0))

        record = sim.step()
        self.assertEqual(record.action, Action.RIGHT)
        self.assertEqual(sim.environment.location, "B")
        self.assertEqual((sim.step_count, sim.clean_count, sim.move_count), (2, 1, 1))

    def test_log_record_has_required_fields(self):
        sim, clock = make_sim(location="B", statuses={"A": Status.CLEAN, "B": Status.DIRTY})
        sim.start()
        clock.advance(2.5)
        record = sim.step()
        self.assertEqual(record, StepRecord(1, 2.5, "B", Status.DIRTY, Action.CLEAN))
        self.assertEqual(sim.log, [record])

    def test_records_percept_before_action(self):
        # Kayıttaki algı, eylemden ÖNCEKİ algıdır.
        sim, _ = make_sim(location="A", statuses=ALL_CLEAN)
        sim.start()
        record = sim.step()
        self.assertEqual((record.room, record.status, record.action), ("A", Status.CLEAN, Action.RIGHT))

    def test_clean_environment_does_not_end_simulation(self):
        sim, _ = make_sim(dirt_probability=0.0, location="A", statuses=ALL_CLEAN)
        sim.start()
        actions = [sim.step().action for _ in range(100)]
        self.assertIs(sim.state, SimulationState.RUNNING)
        self.assertEqual(sim.step_count, 100)
        # Ajan iki temiz oda arasında dolaşmaya devam eder.
        self.assertEqual(actions, [Action.RIGHT, Action.LEFT] * 50)

    def test_step_requires_running_state(self):
        sim, _ = make_sim()
        with self.assertRaises(RuntimeError):
            sim.step()


class DirtTickTests(unittest.TestCase):
    def test_dirty_tick_redirties_clean_rooms(self):
        sim, _ = make_sim(dirt_probability=1.0, location="A", statuses=ALL_CLEAN)
        sim.start()
        record = sim.dirty_tick()
        self.assertEqual(record, DirtRecord(0.0, ("A", "B")))
        self.assertEqual(sim.environment.statuses(), {"A": Status.DIRTY, "B": Status.DIRTY})

    def test_cleaned_room_becomes_dirty_again(self):
        sim, _ = make_sim(dirt_probability=1.0, location="A", statuses={"A": Status.DIRTY, "B": Status.DIRTY})
        sim.start()
        sim.step()  # A temizlenir
        self.assertEqual(sim.environment.status_of("A"), Status.CLEAN)
        sim.dirty_tick()
        self.assertEqual(sim.environment.status_of("A"), Status.DIRTY)

    def test_dirty_tick_without_new_dirt_returns_none_and_logs_nothing(self):
        sim, _ = make_sim(dirt_probability=0.0, statuses=ALL_CLEAN)
        sim.start()
        self.assertIsNone(sim.dirty_tick())
        self.assertEqual(sim.log, [])

    def test_dirty_tick_does_not_count_as_step(self):
        sim, _ = make_sim(dirt_probability=1.0, location="A", statuses=ALL_CLEAN)
        sim.start()
        for _ in range(5):
            sim.dirty_tick()
        self.assertEqual(sim.step_count, 0)
        self.assertEqual(sim.environment.location, "A")

    def test_step_does_not_trigger_dirt(self):
        sim, _ = make_sim(dirt_probability=1.0, location="A", statuses=ALL_CLEAN)
        sim.start()
        for _ in range(20):
            sim.step()
        # Kirlenme olasılığı 1 olsa bile dirty_tick çağrılmadıkça oda kirlenmez.
        self.assertEqual(sim.environment.statuses(), ALL_CLEAN)
        self.assertTrue(all(isinstance(r, StepRecord) for r in sim.log))

    def test_dirt_and_steps_interleave_in_any_order(self):
        sim, _ = make_sim(dirt_probability=1.0, location="A", statuses=ALL_CLEAN)
        sim.start()
        sim.dirty_tick()        # A ve B kirlenir
        sim.dirty_tick()        # zaten kirli, yeni kayıt yok
        a = sim.step()          # A temizlenir
        b = sim.step()          # B'ye geçilir
        self.assertEqual([type(r) for r in sim.log], [DirtRecord, StepRecord, StepRecord])
        self.assertEqual((a.action, b.action), (Action.CLEAN, Action.RIGHT))
        self.assertEqual([a.step, b.step], [1, 2])


class LifecycleTests(unittest.TestCase):
    def test_initial_state_is_ready(self):
        sim, _ = make_sim()
        self.assertIs(sim.state, SimulationState.READY)
        self.assertEqual(sim.elapsed, 0.0)

    def test_pause_blocks_steps_and_dirt(self):
        sim, _ = make_sim()
        sim.start()
        sim.pause()
        with self.assertRaises(RuntimeError):
            sim.step()
        with self.assertRaises(RuntimeError):
            sim.dirty_tick()

    def test_pause_preserves_state_and_resume_continues(self):
        sim, _ = make_sim(dirt_probability=0.0, location="A", statuses={"A": Status.DIRTY, "B": Status.DIRTY})
        sim.start()
        sim.step()  # A temizlendi
        snapshot = (sim.environment.location, sim.environment.statuses(), sim.step_count, list(sim.log))

        sim.pause()
        self.assertEqual(
            (sim.environment.location, sim.environment.statuses(), sim.step_count, list(sim.log)),
            snapshot,
        )
        sim.resume()
        self.assertIs(sim.state, SimulationState.RUNNING)
        record = sim.step()
        self.assertEqual((record.step, record.room, record.action), (2, "A", Action.RIGHT))

    def test_elapsed_excludes_paused_time(self):
        sim, clock = make_sim()
        sim.start()
        clock.advance(3)
        sim.pause()
        clock.advance(100)          # duraklama süresi sayılmamalı
        self.assertEqual(sim.elapsed, 3)
        sim.resume()
        clock.advance(2)
        self.assertEqual(sim.elapsed, 5)

    def test_stop_keeps_log_and_freezes_elapsed(self):
        sim, clock = make_sim()
        sim.start()
        sim.step()
        clock.advance(4)
        sim.stop()
        clock.advance(50)
        self.assertIs(sim.state, SimulationState.STOPPED)
        self.assertEqual(len(sim.log), 1)
        self.assertEqual(sim.elapsed, 4)
        with self.assertRaises(RuntimeError):
            sim.step()

    def test_stop_while_paused(self):
        sim, clock = make_sim()
        sim.start()
        clock.advance(1)
        sim.pause()
        clock.advance(10)
        sim.stop()
        self.assertEqual(sim.elapsed, 1)

    def test_invalid_transitions_are_rejected(self):
        sim, _ = make_sim()
        with self.assertRaises(RuntimeError):
            sim.pause()
        with self.assertRaises(RuntimeError):
            sim.resume()
        sim.start()
        with self.assertRaises(RuntimeError):
            sim.start()
        with self.assertRaises(RuntimeError):
            sim.resume()

    def test_new_simulation_starts_fresh(self):
        old, _ = make_sim(seed=3)
        old.start()
        for _ in range(10):
            old.step()
        old.stop()
        new, _ = make_sim(seed=3)
        self.assertEqual((new.step_count, new.log, new.state), (0, [], SimulationState.READY))


class SeedTests(unittest.TestCase):
    def run_scenario(self, seed):
        sim, clock = make_sim(seed=seed)
        initial = (sim.environment.location, sim.environment.statuses())
        sim.start()
        for i in range(200):
            clock.advance(0.7)
            sim.step()
            if i % 4 == 0:
                sim.dirty_tick()
        return initial, sim.log

    def test_same_seed_reproduces_run(self):
        self.assertEqual(self.run_scenario(42), self.run_scenario(42))

    def test_different_seeds_differ(self):
        runs = {repr(self.run_scenario(seed)) for seed in range(5)}
        self.assertGreater(len(runs), 1)


class GridSimulationTests(unittest.TestCase):
    def test_default_is_1x2(self):
        sim = Simulation(seed=0)
        self.assertEqual(sim.environment.rooms, ("A", "B"))
        self.assertIs(sim.agent.grid, sim.environment.grid)

    def test_grid_simulation_runs_within_bounds(self):
        for rows, cols in [(1, 3), (2, 1), (3, 4), (6, 6)]:
            sim = Simulation(seed=rows * cols, rows=rows, cols=cols, clock=FakeClock())
            sim.start()
            rooms = set(sim.environment.rooms)
            for i in range(500):
                before = sim.environment.location
                record = sim.step()
                self.assertEqual(record.room, before)
                self.assertIn(sim.environment.location, rooms)
                if record.action is Action.CLEAN:
                    self.assertEqual(sim.environment.location, before)  # tek eylem
                else:
                    self.assertNotEqual(sim.environment.location, before)
                if i % 4 == 0:
                    sim.dirty_tick()
            self.assertEqual(sim.step_count, 500)
            self.assertEqual(sim.clean_count + sim.move_count, 500)

    def test_grid_simulation_is_reproducible_with_seed(self):
        def run(seed):
            sim = Simulation(seed=seed, rows=4, cols=5, clock=FakeClock())
            initial = (sim.environment.location, sim.environment.statuses())
            sim.start()
            for i in range(300):
                sim.step()
                if i % 3 == 0:
                    sim.dirty_tick()
            return initial, sim.log
        self.assertEqual(run(11), run(11))
        self.assertNotEqual(run(11), run(12))

    def test_grid_agent_visits_many_rooms(self):
        sim = Simulation(seed=4, rows=3, cols=3, dirt_probability=0.0, clock=FakeClock())
        sim.start()
        visited = {sim.step().room for _ in range(400)}
        self.assertEqual(visited, set(sim.environment.rooms))

    def test_invalid_grid_is_rejected(self):
        with self.assertRaises(ValueError):
            Simulation(rows=1, cols=1)


class SpyAgent:
    """Simülasyonun ajanla nasıl konuştuğunu kaydeden test ajanı."""

    def __init__(self, action):
        self.action = action
        self.calls = []

    def act(self, percept):
        self.calls.append(("act", percept))
        return self.action

    def action_result(self, action, succeeded):
        self.calls.append(("result", action, succeeded))


class ActionResultTests(unittest.TestCase):
    def test_success_is_reported_after_execution(self):
        sim, _ = make_sim(location="A", statuses={"A": Status.DIRTY, "B": Status.CLEAN})
        spy = SpyAgent(Action.CLEAN)
        sim.agent = spy
        sim.start()
        sim.step()
        self.assertEqual(spy.calls, [("act", ("A", Status.DIRTY)), ("result", Action.CLEAN, True)])
        self.assertEqual(sim.environment.status_of("A"), Status.CLEAN)

    def test_failure_is_reported_and_raised(self):
        sim, _ = make_sim(location="A", statuses=ALL_CLEAN)
        spy = SpyAgent(Action.LEFT)  # A'dan sola gitmek sınır dışıdır
        sim.agent = spy
        sim.start()
        with self.assertRaises(ValueError):
            sim.step()
        self.assertEqual(spy.calls[-1], ("result", Action.LEFT, False))
        self.assertEqual((sim.step_count, sim.log, sim.environment.location), (0, [], "A"))

    def test_reflex_agent_ignores_result(self):
        sim, _ = make_sim(location="A", statuses={"A": Status.DIRTY, "B": Status.DIRTY})
        sim.start()
        self.assertIsNone(sim.agent.action_result(Action.CLEAN, True))
        self.assertEqual([sim.step().action for _ in range(3)], [Action.CLEAN, Action.RIGHT, Action.CLEAN])


class AgentTypeTests(unittest.TestCase):
    def test_default_agent_is_reflex(self):
        from agents import ReflexAgent
        sim = Simulation(seed=0)
        self.assertEqual(sim.agent_type, "reflex")
        self.assertIsInstance(sim.agent, ReflexAgent)

    def test_model_agent_can_be_selected(self):
        from agents import ModelBasedAgent
        sim = Simulation(seed=0, rows=3, cols=3, agent_type="model")
        self.assertIsInstance(sim.agent, ModelBasedAgent)
        self.assertIs(sim.agent.grid, sim.environment.grid)

    def test_unknown_agent_type_is_rejected(self):
        with self.assertRaises(ValueError):
            Simulation(agent_type="goal")

    def test_same_seed_gives_same_environment_for_both_agent_types(self):
        a = Simulation(seed=21, rows=4, cols=4, agent_type="reflex")
        b = Simulation(seed=21, rows=4, cols=4, agent_type="model")
        self.assertEqual(
            (a.environment.location, a.environment.statuses()),
            (b.environment.location, b.environment.statuses()),
        )


def run_model_sim(seed, rows=4, cols=5, steps=300, read_snapshots=False):
    sim = Simulation(seed=seed, rows=rows, cols=cols, agent_type="model", clock=FakeClock())
    sim.start()
    for i in range(steps):
        sim.step()
        if read_snapshots:
            sim.agent.model_snapshot()
        if i % 3 == 0:
            sim.dirty_tick()
    return sim


class ModelSimulationTests(unittest.TestCase):
    def test_model_simulation_is_reproducible_with_seed(self):
        self.assertEqual(run_model_sim(8).log, run_model_sim(8).log)
        self.assertNotEqual(run_model_sim(8).log, run_model_sim(9).log)

    def test_reading_snapshots_does_not_change_behavior(self):
        self.assertEqual(run_model_sim(5).log, run_model_sim(5, read_snapshots=True).log)

    def test_model_contains_only_perceived_rooms(self):
        """Ortam bilgisi sızmaz: model yalnızca günlükte algılanan odaları içerir."""
        sim = Simulation(seed=2, rows=6, cols=6, agent_type="model", clock=FakeClock())
        sim.start()
        for _ in range(15):
            sim.step()
        perceived = {record.room for record in sim.log if isinstance(record, StepRecord)}
        snapshot = sim.agent.model_snapshot()
        self.assertEqual(set(snapshot.observations), perceived)
        self.assertLess(len(perceived), 36, "15 adımda 36 odanın hepsi bilinemez")

    def test_model_matches_last_percept_of_each_room(self):
        sim = run_model_sim(3, steps=200)
        snapshot = sim.agent.model_snapshot()
        last = {}
        for record in (r for r in sim.log if isinstance(r, StepRecord)):
            # Kirli algıdan sonra başarılı Temizle: model odayı temiz (çıkarım) bilir.
            last[record.room] = Status.CLEAN if record.action is Action.CLEAN else record.status
        self.assertEqual({room: obs.status for room, obs in snapshot.observations.items()}, last)


if __name__ == "__main__":
    unittest.main()
