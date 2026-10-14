"""Karşılaştırma penceresi (compare_window.py) testleri."""

import time
import tkinter as tk
import unittest
from unittest import mock

import theme
from comparison import AgentSummary, summarize_coverage
from compare_window import format_clean_ratio, format_coverage, format_moves_per_clean, parse_settings
from gui import VacuumApp
from simulation import SimulationState


def summary(**overrides):
    values = dict(agent_type="reflex", runs=3, coverage=summarize_coverage([10, 20, 30], 100),
                  clean_ratio_mean=0.5, clean_ratio_stdev=0.01, moves_per_clean_mean=2.5,
                  moves_per_clean_undefined=0)
    values.update(overrides)
    return AgentSummary(**values)


class FormattingTests(unittest.TestCase):
    def test_complete_coverage(self):
        self.assertEqual(format_coverage(summarize_coverage([10, 20, 30], 100)), ("20,0", "20,0", "30", "3/3"))

    def test_incomplete_coverage_is_marked(self):
        mean, median, worst, completed = format_coverage(summarize_coverage([10, None, None], 100))
        self.assertTrue(mean.startswith("≥ "))
        self.assertEqual((median, worst, completed), ("> 100", "> 100", "1/3"))

    def test_clean_ratio_with_and_without_stdev(self):
        self.assertEqual(format_clean_ratio(summary()), "0,500 ± 0,010")
        self.assertEqual(format_clean_ratio(summary(clean_ratio_stdev=None)), "0,500")

    def test_moves_per_clean_undefined(self):
        self.assertEqual(format_moves_per_clean(summary(moves_per_clean_mean=None, moves_per_clean_undefined=3)),
                         "tanımsız")
        self.assertEqual(format_moves_per_clean(summary(moves_per_clean_undefined=1)), "2,50 (1 koşuda tanımsız)")

    def test_parse_settings_errors_are_turkish(self):
        base = dict(rows="3", cols="3", seed_start="0", seed_count="2", steps="100", dirt_every="4",
                    dirt_mode="common")
        self.assertEqual(parse_settings(base).rows, 3)
        for key, value, fragment in [("rows", "x", "Satır"), ("seed_count", "0", "Seed sayısı"),
                                     ("steps", "-5", "Adım"), ("dirt_every", "a", "Kirlenme"),
                                     ("rows", "7", "1 ile 6")]:
            with self.subTest(key=key, value=value):
                with self.assertRaises(ValueError) as ctx:
                    parse_settings(dict(base, **{key: value}))
                self.assertIn(fragment, str(ctx.exception))


class CompareWindowTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Ekran bulunamadı: {exc}")
        self.root.withdraw()
        self.app = VacuumApp(self.root)

    def tearDown(self):
        self.app.on_close()

    def open_small(self, **values):
        window = self.app.open_comparison()
        defaults = dict(rows="3", cols="3", seed_start="0", seed_count="3", steps="300", dirt_every="4")
        defaults.update(values)
        for key, value in defaults.items():
            window.vars[key].set(value)
        return window

    def run_until_done(self, window, timeout=30.0):
        deadline = time.monotonic() + timeout
        while window.running and time.monotonic() < deadline:
            self.root.update()
        self.assertFalse(window.running, "Karşılaştırma zamanında bitmeli")

    def test_button_opens_single_window(self):
        first = self.app.open_comparison()
        second = self.app.open_comparison()
        self.assertIs(first, second)
        self.assertTrue(str(self.app.compare_button["text"]).endswith("Ajanları Karşılaştır"))

    def test_full_comparison_fills_table_and_chart(self):
        window = self.open_small()
        window.start()
        self.assertTrue(window.running)
        self.assertEqual(str(window.start_button["state"]), "disabled")
        self.run_until_done(window)
        self.assertEqual(window.table.get_children(), ("reflex", "model", "goal"))
        self.assertEqual(len(window.chart.find_withtag("bar")), 6)       # 2 grafik x 3 ajan
        self.assertIn("Tamamlandı", window.status_var.get())
        self.assertLess(window.job.longest_slice, 0.1, "Tek bir hesaplama dilimi arayüzü kilitlememeli")

    def test_chart_texts_stay_inside_canvas_and_theme_is_applied(self):
        window = self.open_small()
        window.window.deiconify()
        window.start()
        self.run_until_done(window)
        self.root.update()
        chart = window.chart
        height = chart.winfo_height()
        names = [chart.itemcget(i, "text") for i in chart.find_all() if chart.type(i) == "text"]
        self.assertIn("Amaç Tabanlı Ajan", names)
        for item in chart.find_all():
            if chart.type(item) == "text":
                self.assertLessEqual(chart.bbox(item)[3], height + 2, chart.itemcget(item, "text"))
        self.assertEqual(str(window.window.cget("background")), theme.COLORS["page"])
        self.assertTrue(str(window.start_button["text"]).endswith("Başlat"))
        self.assertTrue(str(window.cancel_button["text"]).endswith("İptal"))

    def test_cancel_shows_no_partial_results_and_restart_works(self):
        window = self.open_small(seed_count="10", steps="3000", rows="6", cols="6")
        window.start()
        for _ in range(5):
            self.root.update()
        window.cancel()
        self.assertFalse(window.running)
        self.assertEqual(window.table.get_children(), ())
        self.assertIn("İptal", window.status_var.get())
        done = window.job.done
        for _ in range(20):
            self.root.update()
        self.assertEqual(window.job.done, done, "İptalden sonra yeni dilim çalışmamalı")
        for key, value in dict(rows="3", cols="3", seed_count="2", steps="200").items():
            window.vars[key].set(value)
        window.start()
        self.run_until_done(window)
        self.assertEqual(len(window.table.get_children()), 3)

    def test_main_simulation_keeps_running_and_close_does_not_affect_it(self):
        app = self.app
        app.step_var.set("100")
        app.start()
        window = self.open_small(seed_count="20", steps="3000", rows="6", cols="6")
        window.start()
        steps_before = app.simulation.step_count
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            self.root.update()
        self.assertGreater(app.simulation.step_count, steps_before + 3, "Ana simülasyon donmamalı")
        window.close()
        self.assertTrue(window.closed)
        self.assertIs(app.simulation.state, SimulationState.RUNNING)
        steps_after_close = app.simulation.step_count
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            self.root.update()
        self.assertGreater(app.simulation.step_count, steps_after_close)
        self.assertIsNot(app.open_comparison(), window, "Kapanan pencere yerine yenisi açılmalı")

    def test_invalid_settings_show_error(self):
        window = self.open_small(rows="1", cols="1")
        with mock.patch("compare_window.messagebox.showerror") as showerror:
            window.start()
        showerror.assert_called_once()
        self.assertIsNone(window.job)

    def test_settings_locked_while_running(self):
        window = self.open_small(seed_count="10", steps="3000", rows="6", cols="6")
        window.start()
        self.assertTrue(all(str(e["state"]) == "disabled" for e in window.entries))
        window.cancel()
        self.assertTrue(all(str(e["state"]) == "normal" for e in window.entries))

    def test_independent_mode_and_other_grids(self):
        window = self.open_small(rows="2", cols="5", seed_count="2", steps="200")
        window.vars["dirt_mode"].set("independent")
        window.start()
        self.run_until_done(window)
        self.assertEqual(window.job.settings.dirt_mode, "independent")
        self.assertEqual(len(window.table.get_children()), 3)

    def test_unfinished_coverage_shown_as_incomplete(self):
        window = self.open_small(rows="6", cols="6", seed_count="2", steps="20")
        window.start()
        self.run_until_done(window)
        values = window.table.item("reflex", "values")
        self.assertEqual(values[1], "0/2")
        self.assertTrue(str(values[3]).startswith("> "))


if __name__ == "__main__":
    unittest.main()
