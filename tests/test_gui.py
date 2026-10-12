"""Arayüz (gui.py) testleri.

Biçimlendirme yardımcıları her ortamda test edilir. Pencere testleri gerçek
bir Tkinter penceresi açar; ekran yoksa atlanır.
"""

import tkinter as tk
from tkinter import ttk
import unittest

from environment import Action, Status
from gui import VacuumApp, format_elapsed, format_record, parse_seed
from simulation import DirtRecord, SimulationState, StepRecord


class FormatTests(unittest.TestCase):
    def test_step_record_format(self):
        line = format_record(StepRecord(12, 8.44, "A", Status.DIRTY, Action.CLEAN))
        self.assertEqual(line, "Adım   12 | Süre: 00:08.4 | Oda: A | Algı: Kirli | Eylem: Temizle")

    def test_move_record_format(self):
        self.assertIn("Eylem: Sağa git", format_record(StepRecord(1, 0, "A", Status.CLEAN, Action.RIGHT)))
        self.assertIn("Eylem: Sola git", format_record(StepRecord(1, 0, "B", Status.CLEAN, Action.LEFT)))

    def test_dirt_record_format(self):
        line = format_record(DirtRecord(65.0, ("A", "B")))
        self.assertEqual(line, "Kirlenme  | Süre: 01:05.0 | A, B odası kirlendi")

    def test_format_elapsed(self):
        self.assertEqual(format_elapsed(0), "00:00.0")
        self.assertEqual(format_elapsed(125.37), "02:05.4")

    def test_parse_seed(self):
        self.assertIsNone(parse_seed("  "))
        self.assertEqual(parse_seed(" 42 "), 42)
        with self.assertRaises(ValueError):
            parse_seed("abc")


class WindowTests(unittest.TestCase):
    """Gerçek pencereyle kullanıcı akışı: başlat, duraklat, devam, durdur, yeniden başlat."""

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Ekran bulunamadı: {exc}")
        self.root.withdraw()
        self.app = VacuumApp(self.root)
        self.app.step_var.set("100")
        self.app.dirt_var.set("0.5")
        self.app.seed_var.set("7")

    def tearDown(self):
        self.app.on_close()

    def pump(self, seconds):
        """Olay döngüsünü belirtilen süre boyunca çalıştırır."""
        self.root.after(int(seconds * 1000), self.root.quit)
        self.root.mainloop()

    def log_lines(self):
        return self.app.log_text.get("1.0", "end").strip().splitlines()

    def test_full_user_flow(self):
        app = self.app
        self.assertEqual(str(app.pause_button["state"]), "disabled")

        app.start()
        self.assertIs(app.simulation.state, SimulationState.RUNNING)
        self.assertEqual(str(app.start_button["state"]), "disabled")
        self.pump(1.2)
        steps = app.simulation.step_count
        self.assertGreater(steps, 3, "Adım zamanlayıcısı çalışmalı")
        self.assertTrue(any(line.startswith("Adım") for line in self.log_lines()))

        # Duraklat: zamanlayıcılar durur, durum korunur.
        app.toggle_pause()
        self.assertIs(app.simulation.state, SimulationState.PAUSED)
        self.assertEqual(app.pause_button["text"], "Devam")
        self.assertIsNone(app._step_job)
        self.assertIsNone(app._dirt_job)
        self.pump(0.5)
        self.assertEqual(app.simulation.step_count, steps)

        # Devam: kaldığı yerden sürer.
        app.toggle_pause()
        self.pump(0.5)
        self.assertGreater(app.simulation.step_count, steps)

        # Durdur: simülasyon biter, günlük kalır.
        app.stop()
        self.assertIs(app.simulation.state, SimulationState.STOPPED)
        lines_after_stop = self.log_lines()
        self.assertIn("durduruldu", lines_after_stop[-1])
        final_steps = app.simulation.step_count
        self.pump(0.4)
        self.assertEqual(app.simulation.step_count, final_steps)
        self.assertEqual(self.log_lines(), lines_after_stop)

        # Yeniden başlat: önceki durum ve günlük sıfırlanır.
        app.start()
        self.assertEqual(app.simulation.step_count, 0)
        self.assertEqual(len(self.log_lines()), 1)
        self.assertIn("başladı", self.log_lines()[0])

    def test_dirt_timer_runs_independently(self):
        app = self.app
        app.step_var.set("5000")   # adım zamanlayıcısı bu sürede hiç tetiklenmez
        app.start()
        self.pump(2.0)
        self.assertEqual(app.simulation.step_count, 0)
        self.assertTrue(
            any(line.startswith("Kirlenme") for line in self.log_lines())
            or all(s is Status.DIRTY for s in app.simulation.environment.statuses().values()),
            "Kirlenme zamanlayıcısı adımlardan bağımsız çalışmalı",
        )

    def test_keyboard_shortcuts(self):
        # Gizli pencereye gerçek tuş olayı gönderilemediği için bağlamalar ve
        # işleyiciler ayrı ayrı doğrulanır.
        bindings = self.root.bind()
        self.assertIn("<Key-space>", bindings)
        self.assertIn("<Key-Escape>", bindings)

        app = self.app
        event = type("Event", (), {"widget": self.root})()
        app.start()
        app._on_space_key(event)
        self.assertIs(app.simulation.state, SimulationState.PAUSED)
        app._on_space_key(event)
        self.assertIs(app.simulation.state, SimulationState.RUNNING)
        app._on_escape_key(event)
        self.assertIs(app.simulation.state, SimulationState.STOPPED)

    def test_space_in_text_field_is_not_a_shortcut(self):
        app = self.app
        app.start()
        entry = [w for w in app.root.winfo_children()[0].winfo_children() if isinstance(w, ttk.Entry)][0]
        app._on_space_key(type("Event", (), {"widget": entry})())
        self.assertIs(app.simulation.state, SimulationState.RUNNING)

    def test_invalid_interval_falls_back_to_last_valid(self):
        self.app.step_var.set("abc")
        self.assertEqual(self.app._read_step_ms(), 700)
        self.app.step_var.set("10")
        self.assertEqual(self.app._read_step_ms(), 100)  # alt sınıra çekilir


if __name__ == "__main__":
    unittest.main()
