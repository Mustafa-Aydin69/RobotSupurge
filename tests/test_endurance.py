"""Uzun süreli dayanıklılık testleri (50.000 adım).

Normal test paketini yavaşlatmamak için yalnızca ``ROBOT_LONG_TESTS=1`` ortam
değişkeni verildiğinde çalışır:

    set ROBOT_LONG_TESTS=1            (Windows cmd)
    $env:ROBOT_LONG_TESTS = "1"       (PowerShell)
    python -m unittest tests.test_endurance -v
"""

import os
import unittest

from agents import route_rooms
from simulation import DirtRecord, Simulation, StepRecord

LONG_STEPS = 50_000
ENABLED = os.environ.get("ROBOT_LONG_TESTS") == "1"


@unittest.skipUnless(ENABLED, "Uzun testler için ROBOT_LONG_TESTS=1 verin")
class EnduranceTests(unittest.TestCase):
    def run_long(self, agent_type, rows=6, cols=6, seed=2024):
        sim = Simulation(seed=seed, rows=rows, cols=cols, agent_type=agent_type, clock=lambda: 0.0)
        sim.start()
        rooms = set(sim.environment.rooms)
        dirt_records = 0
        for i in range(LONG_STEPS):
            sim.step()                        # sınır dışı bir hareket ValueError fırlatırdı
            if i % 4 == 0 and sim.dirty_tick() is not None:
                dirt_records += 1
            if i % 997 == 0:                  # ara kontroller
                self.assertIn(sim.environment.location, rooms)
                if hasattr(sim.agent, "model_snapshot"):
                    snap = sim.agent.model_snapshot()
                    self.assertLessEqual(set(snap.observations), rooms)
                    self.assertEqual(snap.location, sim.environment.location)
                    self.assertTrue(all(snap.age_of(r) >= 0 for r in snap.observations))
                if hasattr(sim.agent, "plan_snapshot"):
                    plan = sim.agent.plan_snapshot()
                    if plan.route:
                        self.assertEqual(route_rooms(sim.environment.grid, plan.origin, plan.route)[-1],
                                         plan.target.room)
        return sim, dirt_records

    def check_log(self, sim, dirt_records):
        steps = [r for r in sim.log if isinstance(r, StepRecord)]
        dirt = [r for r in sim.log if isinstance(r, DirtRecord)]
        self.assertEqual(sim.step_count, LONG_STEPS)
        self.assertEqual(len(steps), LONG_STEPS)
        self.assertEqual([r.step for r in steps], list(range(1, LONG_STEPS + 1)))
        self.assertEqual(len(dirt), dirt_records)
        self.assertEqual(sim.clean_count + sim.move_count, LONG_STEPS)

    def test_reflex_agent_50000_steps(self):
        self.check_log(*self.run_long("reflex"))

    def test_model_agent_50000_steps(self):
        self.check_log(*self.run_long("model"))

    def test_goal_agent_50000_steps(self):
        self.check_log(*self.run_long("goal"))

    def test_mandatory_1x2_reflex_50000_steps(self):
        sim, dirt_records = self.run_long("reflex", rows=1, cols=2)
        self.check_log(sim, dirt_records)
        # Faz 1 tablosu: temiz odada A -> Sağa, B -> Sola; kirli odada Temizle.
        for record in (r for r in sim.log if isinstance(r, StepRecord)):
            if record.status.value == "Dirty":
                self.assertEqual(record.action.value, "Clean")
            else:
                self.assertEqual(record.action.value, "Right" if record.room == "A" else "Left")


if __name__ == "__main__":
    unittest.main()
