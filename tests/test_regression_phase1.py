"""Faz 1 (1×2) davranışı için regresyon testi.

``tests/data/phase1_reference.json`` dosyası, grid geliştirmesine başlamadan
önce Faz 1 koduyla üretilmiştir. Aynı seed ile çalışan 1×2 simülasyonunun
sonraki sürümlerde de birebir aynı davranışı göstermesi beklenir.

Karşılaştırılanlar: başlangıç odası, başlangıç oda durumları, adım numarası,
algılanan oda ve durum, seçilen eylem, eylem sonrası ortam durumu ve kirlenme
olayları. Gerçek zaman damgaları karşılaştırılmaz.

Referansı yeniden üretmek (yalnızca bilinçli bir davranış değişikliğinde):
    python -m tests.test_regression_phase1 --regenerate
"""

import json
import sys
import unittest
from pathlib import Path

from simulation import DirtRecord, Simulation

REFERENCE_FILE = Path(__file__).parent / "data" / "phase1_reference.json"
SEEDS = list(range(10))
STEPS = 40
DIRT_EVERY = 3  # her 3 adımda bir kirlenme tetiklenir


def snapshot(env):
    return {
        "location": env.location,
        "statuses": {room: status.value for room, status in sorted(env.statuses().items())},
    }


def record_run(seed):
    """Seed'li bir 1×2 koşusunu zaman damgası içermeyen bir sözlüğe çevirir."""
    sim = Simulation(seed=seed, clock=lambda: 0.0)
    run = {"seed": seed, "initial": snapshot(sim.environment), "events": []}
    sim.start()
    for i in range(1, STEPS + 1):
        rec = sim.step()
        run["events"].append({
            "type": "step",
            "step": rec.step,
            "room": rec.room,
            "status": rec.status.value,
            "action": rec.action.value,
            "after": snapshot(sim.environment),
        })
        if i % DIRT_EVERY == 0:
            dirt = sim.dirty_tick()
            if isinstance(dirt, DirtRecord):
                run["events"].append({
                    "type": "dirt",
                    "rooms": list(dirt.rooms),
                    "after": snapshot(sim.environment),
                })
    return run


class Phase1RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads(REFERENCE_FILE.read_text(encoding="utf-8"))

    def test_reference_covers_expected_seeds(self):
        self.assertEqual([run["seed"] for run in self.reference], SEEDS)

    def test_seeded_runs_match_phase1_reference(self):
        for expected in self.reference:
            with self.subTest(seed=expected["seed"]):
                self.assertEqual(record_run(expected["seed"]), expected)


def regenerate():
    sys.stdout.reconfigure(encoding="utf-8")  # Windows konsolunda Türkçe karakterler için
    REFERENCE_FILE.parent.mkdir(exist_ok=True)
    data = [record_run(seed) for seed in SEEDS]
    REFERENCE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{REFERENCE_FILE} yazıldı ({len(data)} koşu).")


if __name__ == "__main__":
    if "--regenerate" in sys.argv:
        regenerate()
    else:
        unittest.main()
