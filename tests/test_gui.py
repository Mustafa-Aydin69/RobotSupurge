"""Arayüz (gui.py) testleri.

Biçimlendirme yardımcıları her ortamda test edilir. Pencere testleri gerçek
bir Tkinter penceresi açar; ekran yoksa atlanır.
"""

import tkinter as tk
from tkinter import ttk
import unittest
from unittest import mock

from environment import Action, Status
from types import MappingProxyType

from agents import SOURCE_INFERENCE, SOURCE_PERCEPT, ModelSnapshot, Observation
from environment import Grid
from gui import (
    MODEL_CLEAN, MODEL_DIRTY, MODEL_INFERRED, MODEL_PANEL_TITLE, MODEL_STALE, MODEL_UNKNOWN,
    PausableTimer, VacuumApp, compute_layout, format_elapsed, format_record, model_category,
    parse_grid_size, parse_seed, stale_threshold,
)
from simulation import DirtRecord, SimulationState, StepRecord


class FormatTests(unittest.TestCase):
    def test_step_record_format(self):
        line = format_record(StepRecord(12, 8.44, "A", Status.DIRTY, Action.CLEAN))
        self.assertEqual(line, "Adım   12 | Süre: 00:08.4 | Oda: A | Algı: Kirli | Eylem: Temizle")

    def test_move_record_format(self):
        self.assertIn("Eylem: Sağa git", format_record(StepRecord(1, 0, "A", Status.CLEAN, Action.RIGHT)))
        self.assertIn("Eylem: Sola git", format_record(StepRecord(1, 0, "B", Status.CLEAN, Action.LEFT)))

    def test_vertical_moves_and_grid_room_names(self):
        self.assertEqual(
            format_record(StepRecord(7, 3.0, "B3", Status.CLEAN, Action.UP)),
            "Adım    7 | Süre: 00:03.0 | Oda: B3 | Algı: Temiz | Eylem: Yukarı git",
        )
        self.assertIn("Eylem: Aşağı git", format_record(StepRecord(1, 0, "A1", Status.CLEAN, Action.DOWN)))

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


class GridSettingTests(unittest.TestCase):
    def test_parse_grid_size_accepts_valid_sizes(self):
        self.assertEqual(parse_grid_size("1", "2"), (1, 2))
        self.assertEqual(parse_grid_size(" 6 ", "6"), (6, 6))

    def test_parse_grid_size_rejects_with_turkish_message(self):
        cases = {("1", "1"): "en az iki oda", ("7", "2"): "1 ile 6", ("0", "3"): "1 ile 6",
                 ("a", "2"): "tam sayı", ("", "2"): "tam sayı", ("2.5", "2"): "tam sayı"}
        for (rows, cols), fragment in cases.items():
            with self.subTest(rows=rows, cols=cols):
                with self.assertRaises(ValueError) as ctx:
                    parse_grid_size(rows, cols)
                self.assertIn(fragment, str(ctx.exception))

    def test_layout_fits_canvas_without_overlap(self):
        for width, height in [(560, 240), (800, 400), (660, 230)]:
            for rows in range(1, 7):
                for cols in range(1, 7):
                    if rows * cols < 2:
                        continue
                    left, top, cell_w, cell_h, gap = compute_layout(width, height, rows, cols)
                    with self.subTest(size=(width, height), grid=(rows, cols)):
                        self.assertGreaterEqual(left, 0)
                        self.assertGreaterEqual(top, 0)
                        self.assertLessEqual(left + cols * cell_w + (cols - 1) * gap, width + 1e-6)
                        self.assertLessEqual(top + rows * cell_h + (rows - 1) * gap, height + 1e-6)
                        self.assertGreater(gap, 0)
                        self.assertGreater(min(cell_w, cell_h), 20)

    def test_1x2_layout_matches_phase1_look(self):
        # Faz 1'deki 560×240 tuvalde 20 px boşluk ve 250×200 odalar.
        self.assertEqual(compute_layout(560, 240, 1, 2), (20.0, 20.0, 250.0, 200.0, 20.0))


class ModelCategoryTests(unittest.TestCase):
    def test_stale_threshold_depends_on_room_count(self):
        self.assertEqual(stale_threshold(Grid(1, 2)), 4)
        self.assertEqual(stale_threshold(Grid(2, 2)), 4)
        self.assertEqual(stale_threshold(Grid(3, 4)), 12)
        self.assertEqual(stale_threshold(Grid(6, 6)), 36)

    def test_categories(self):
        clean = Observation(Status.CLEAN, 10, SOURCE_PERCEPT)
        inferred = Observation(Status.CLEAN, 10, SOURCE_INFERENCE)
        dirty = Observation(Status.DIRTY, 10, SOURCE_PERCEPT)
        self.assertEqual(model_category(None, None, 4), MODEL_UNKNOWN)
        self.assertEqual(model_category(clean, 3, 4), MODEL_CLEAN)
        self.assertEqual(model_category(inferred, 0, 4), MODEL_INFERRED)
        self.assertEqual(model_category(clean, 4, 4), MODEL_STALE)
        self.assertEqual(model_category(inferred, 9, 4), MODEL_STALE)
        self.assertEqual(model_category(dirty, 50, 4), MODEL_DIRTY)


class FakeScheduler:
    """Tkinter'ın after/after_cancel arayüzünü sahte bir saatle taklit eder."""

    def __init__(self):
        self.now = 0.0
        self._jobs = {}
        self._next_id = 0

    def clock(self):
        return self.now

    def after(self, delay_ms, callback):
        self._next_id += 1
        self._jobs[self._next_id] = (self.now + delay_ms / 1000, callback)
        return self._next_id

    def after_cancel(self, job_id):
        self._jobs.pop(job_id, None)

    def advance(self, seconds):
        """Saati ilerletir ve süresi dolan işleri sırayla çalıştırır."""
        target = self.now + seconds
        while True:
            due = [(t, i) for i, (t, _) in self._jobs.items() if t <= target]
            if not due:
                break
            t, job_id = min(due)
            self.now = t
            _, callback = self._jobs.pop(job_id)
            callback()
        self.now = target


class PausableTimerTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = FakeScheduler()
        self.fired = []
        self.timer = PausableTimer(
            self.scheduler, lambda: self.fired.append(self.scheduler.now), clock=self.scheduler.clock,
        )

    def test_fires_after_full_interval(self):
        self.timer.start(1000)
        self.scheduler.advance(0.999)
        self.assertEqual(self.fired, [])
        self.scheduler.advance(0.001)
        self.assertEqual(self.fired, [1.0])
        self.assertFalse(self.timer.is_pending)

    def test_pause_keeps_remaining_time(self):
        self.timer.start(1000)
        self.scheduler.advance(0.3)
        self.timer.pause()
        self.assertTrue(self.timer.is_paused)
        self.assertFalse(self.timer.is_pending)
        self.assertAlmostEqual(self.timer.remaining_ms, 700)

    def test_no_fire_while_paused(self):
        self.timer.start(1000)
        self.scheduler.advance(0.3)
        self.timer.pause()
        self.scheduler.advance(60)
        self.assertEqual(self.fired, [])

    def test_resume_continues_from_remaining_time(self):
        self.timer.start(1000)
        self.scheduler.advance(0.3)
        self.timer.pause()
        self.scheduler.advance(5)            # duraklama: t = 5.3
        self.timer.resume()
        self.scheduler.advance(0.699)
        self.assertEqual(self.fired, [], "Tam aralık değil, kalan 700 ms beklenmeli")
        self.scheduler.advance(0.001)
        self.assertEqual(self.fired, [6.0])  # 5.3 + 0.7

    def test_multiple_pauses_accumulate_correctly(self):
        self.timer.start(1000)
        for _ in range(4):                   # 4 x 0.2 sn çalış, her seferinde 10 sn duraklat
            self.scheduler.advance(0.2)
            self.timer.pause()
            self.scheduler.advance(10)
            self.timer.resume()
        self.assertEqual(self.fired, [])
        self.assertAlmostEqual(self.timer.remaining_ms, 200)
        self.scheduler.advance(0.2)
        self.assertEqual(len(self.fired), 1)

    def test_cancel_discards_pending_and_paused(self):
        self.timer.start(1000)
        self.timer.cancel()
        self.scheduler.advance(5)
        self.assertEqual(self.fired, [])

        self.timer.start(1000)
        self.scheduler.advance(0.5)
        self.timer.pause()
        self.timer.cancel()
        self.timer.resume()                  # iptal sonrası devam hiçbir şey yapmamalı
        self.scheduler.advance(5)
        self.assertEqual(self.fired, [])
        self.assertIsNone(self.timer.remaining_ms)

    def test_start_resets_to_full_interval(self):
        self.timer.start(1000)
        self.scheduler.advance(0.6)
        self.timer.pause()
        self.timer.start(1000)               # yeni başlatma kalan süreyi unutur
        self.assertFalse(self.timer.is_paused)
        self.assertAlmostEqual(self.timer.remaining_ms, 1000)

    def test_two_timers_are_independent(self):
        other_fired = []
        other = PausableTimer(self.scheduler, lambda: other_fired.append(self.scheduler.now),
                              clock=self.scheduler.clock)
        self.timer.start(700)
        other.start(3000)
        self.scheduler.advance(0.5)
        self.timer.pause()
        other.pause()
        self.scheduler.advance(2)
        self.timer.resume()
        other.resume()
        self.assertAlmostEqual(self.timer.remaining_ms, 200)
        self.assertAlmostEqual(other.remaining_ms, 2500)


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
        self.assertFalse(app.step_timer.is_pending)
        self.assertFalse(app.dirt_timer.is_pending)
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

    def test_pause_resume_keeps_remaining_time_in_window(self):
        app = self.app
        app.step_var.set("1000")
        app.dirt_var.set("2")
        app.start()
        self.pump(0.4)
        app.toggle_pause()
        step_left = app.step_timer.remaining_ms
        dirt_left = app.dirt_timer.remaining_ms
        self.assertLess(step_left, 900)
        self.assertLess(dirt_left, 1900)
        log_before = self.log_lines()

        # Duraklama, adım aralığından uzun sürse bile hiçbir şey olmamalı.
        self.pump(1.5)
        self.assertEqual(app.simulation.step_count, 0)
        self.assertEqual(self.log_lines(), log_before)
        self.assertAlmostEqual(app.step_timer.remaining_ms, step_left)
        self.assertAlmostEqual(app.dirt_timer.remaining_ms, dirt_left)

        # Devam: ilk adım tam 1000 ms değil, kalan süre sonunda gelmeli.
        app.toggle_pause()
        self.assertLessEqual(app.step_timer.remaining_ms, step_left + 1)
        self.pump(step_left / 1000 + 0.25)
        self.assertEqual(app.simulation.step_count, 1)

    def test_stop_cancels_pending_timers(self):
        app = self.app
        app.start()
        app.stop()
        self.assertFalse(app.step_timer.is_pending)
        self.assertFalse(app.dirt_timer.is_pending)

        app.start()
        app.toggle_pause()
        app.stop()                           # duraklatılmışken durdurma
        self.assertFalse(app.step_timer.is_paused)
        self.assertFalse(app.dirt_timer.is_paused)
        app.toggle_pause()                   # durdurulmuş simülasyonda etkisiz
        self.assertFalse(app.step_timer.is_pending)

    def test_new_simulation_starts_timers_at_full_interval(self):
        app = self.app
        app.step_var.set("1000")
        app.dirt_var.set("3")
        app.start()
        self.pump(0.5)
        app.toggle_pause()
        app.stop()
        app.start()
        self.assertGreater(app.step_timer.remaining_ms, 950)
        self.assertGreater(app.dirt_timer.remaining_ms, 2950)

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

    def room_items(self):
        return self.app.canvas.find_withtag("room")

    def test_grid_is_drawn_with_all_rooms_and_one_robot(self):
        app = self.app
        for rows, cols in [(1, 2), (3, 4), (6, 6)]:
            app.rows_var.set(str(rows))
            app.cols_var.set(str(cols))
            app.start()
            self.root.update()
            with self.subTest(grid=(rows, cols)):
                self.assertEqual(len(self.room_items()), rows * cols)
                self.assertEqual(len(app.canvas.find_withtag(f"room:{app.simulation.environment.location}")), 1)
                self.assertGreater(len(app.canvas.find_withtag("robot")), 0)
                self.assertIn(f"({rows}×{cols}", self.log_lines()[0])
            app.stop()

    def test_grid_moves_are_logged_in_turkish(self):
        app = self.app
        app.rows_var.set("3")
        app.cols_var.set("3")
        app.start()
        self.pump(1.5)
        lines = [line for line in self.log_lines() if line.startswith("Adım")]
        self.assertTrue(lines)
        self.assertTrue(all(any(w in line for w in ("Temizle", "Sağa", "Sola", "Yukarı", "Aşağı")) for line in lines))
        self.assertTrue(all("Oda: " in line and line.split("Oda: ")[1][:2] in app.simulation.environment.rooms
                            for line in lines))

    def test_grid_size_locked_while_running_and_paused(self):
        app = self.app
        self.assertEqual(str(app.rows_spin["state"]), "normal")
        app.start()
        self.assertEqual(str(app.rows_spin["state"]), "disabled")
        self.assertEqual(str(app.cols_spin["state"]), "disabled")
        app.toggle_pause()
        self.assertEqual(str(app.rows_spin["state"]), "disabled")
        app.stop()
        self.assertEqual(str(app.rows_spin["state"]), "normal")
        self.assertEqual(str(app.cols_spin["state"]), "normal")

    def test_invalid_grid_size_shows_turkish_error(self):
        app = self.app
        for rows, cols in [("1", "1"), ("7", "3"), ("x", "2")]:
            app.rows_var.set(rows)
            app.cols_var.set(cols)
            with mock.patch("gui.messagebox.showerror") as showerror:
                app.start()
            with self.subTest(rows=rows, cols=cols):
                showerror.assert_called_once()
                self.assertEqual(showerror.call_args[0][0], "Geçersiz ortam boyutu")
                self.assertIsNone(app.simulation)

    def test_preview_follows_settings_when_idle(self):
        app = self.app
        app.rows_var.set("2")
        app.cols_var.set("5")
        self.root.update()
        self.assertEqual(len(self.room_items()), 10)

    def test_redraw_on_resize_keeps_grid_inside_canvas(self):
        app = self.app
        self.root.deiconify()
        app.rows_var.set("6")
        app.cols_var.set("6")
        app.start()
        for geometry in ("680x620", "1000x900"):
            self.root.geometry(geometry)
            self.root.update()
            width, height = app.canvas.winfo_width(), app.canvas.winfo_height()
            with self.subTest(geometry=geometry):
                self.assertEqual(len(self.room_items()), 36)
                x0, y0, x1, y1 = app.canvas.bbox("room")
                self.assertGreaterEqual(x0, -2)
                self.assertGreaterEqual(y0, -2)
                self.assertLessEqual(x1, width + 2)
                self.assertLessEqual(y1, height + 2)
                # Kontroller ve günlük görünür kalmalı.
                self.assertTrue(app.start_button.winfo_ismapped())
                self.assertTrue(app.log_text.winfo_ismapped())

    def test_agent_type_selection_creates_matching_agent(self):
        from agents import ModelBasedAgent, ReflexAgent
        app = self.app
        self.assertEqual(app.selected_agent_type(), "reflex")
        app.start()
        self.assertIsInstance(app.simulation.agent, ReflexAgent)
        self.assertIn("Basit Refleks Ajan", self.log_lines()[0])
        app.stop()

        app.agent_var.set("Model Tabanlı Ajan")
        app.rows_var.set("3")
        app.cols_var.set("3")
        app.start()
        self.assertEqual(app.simulation.agent_type, "model")
        self.assertIsInstance(app.simulation.agent, ModelBasedAgent)
        self.assertIn("Model Tabanlı Ajan", self.log_lines()[0])

    def test_agent_type_locked_while_running_and_paused(self):
        app = self.app
        self.assertEqual(str(app.agent_combo["state"]), "readonly")
        app.start()
        self.assertEqual(str(app.agent_combo["state"]), "disabled")
        app.toggle_pause()
        self.assertEqual(str(app.agent_combo["state"]), "disabled")
        app.stop()
        self.assertEqual(str(app.agent_combo["state"]), "readonly")

    def model_categories(self):
        result = {}
        for item in self.app.model_canvas.find_withtag("model-room"):
            tags = self.app.model_canvas.gettags(item)
            room = next(t for t in tags if t.startswith("model:"))[6:]
            result[room] = next(t for t in tags if t.startswith("category:"))[9:]
        return result

    def test_model_panel_only_for_model_agent(self):
        app = self.app
        self.root.update()
        self.assertEqual(app.model_frame.winfo_manager(), "")       # refleks: gizli
        app.agent_var.set("Model Tabanlı Ajan")
        self.root.update()
        self.assertEqual(app.model_frame.winfo_manager(), "grid")   # önizlemede görünür
        self.assertEqual(app.model_frame["text"], MODEL_PANEL_TITLE)
        app.agent_var.set("Basit Refleks Ajan")
        self.root.update()
        self.assertEqual(app.model_frame.winfo_manager(), "")

    def test_model_panel_depends_on_agent_capability(self):
        from gui import agent_has_model
        self.assertEqual(
            {key: agent_has_model(key) for key in ("reflex", "model", "goal")},
            {"reflex": False, "model": True, "goal": True},
        )
        app = self.app
        app.agent_var.set("Amaç Tabanlı Ajan")
        self.root.update()
        self.assertEqual(app.model_frame.winfo_manager(), "grid")
        app.rows_var.set("3")
        app.cols_var.set("3")
        app.start()
        self.pump(0.5)
        self.assertEqual(app.simulation.agent_type, "goal")
        self.assertIn("Bilinen oda", app.status_var.get())

    def test_model_panel_starts_unknown_and_follows_snapshot(self):
        app = self.app
        app.agent_var.set("Model Tabanlı Ajan")
        app.rows_var.set("4")
        app.cols_var.set("4")
        self.root.update()
        self.assertEqual(set(self.model_categories().values()), {MODEL_UNKNOWN})
        self.assertEqual(len(self.model_categories()), 16)

        app.start()
        self.pump(1.0)
        app.toggle_pause()
        app._draw()
        snapshot = app.simulation.agent.model_snapshot()
        categories = self.model_categories()
        unknown = {room for room, cat in categories.items() if cat == MODEL_UNKNOWN}
        self.assertEqual(unknown, set(app.simulation.environment.rooms) - set(snapshot.observations))
        self.assertTrue(unknown, "1 saniyede 16 odanın hepsi bilinmemeli")
        location_items = app.model_canvas.find_withtag("model-agent")
        self.assertEqual(len(location_items), 1)

    def test_model_panel_draws_only_from_snapshot(self):
        """Panel ortamı okumaz: ortamdan bağımsız sahte bir model kopyası çizilebilir."""
        app = self.app
        grid = Grid(2, 2)
        snapshot = ModelSnapshot(10, "A1", MappingProxyType({
            "A1": Observation(Status.CLEAN, 10, SOURCE_INFERENCE),
            "A2": Observation(Status.CLEAN, 2, SOURCE_PERCEPT),
            "B1": Observation(Status.DIRTY, 9, SOURCE_PERCEPT),
        }))
        app._draw_model(grid, snapshot)
        self.assertEqual(self.model_categories(), {
            "A1": MODEL_INFERRED, "A2": MODEL_STALE, "B1": MODEL_DIRTY, "B2": MODEL_UNKNOWN,
        })

    def test_gui_cannot_modify_agent_memory(self):
        app = self.app
        app.agent_var.set("Model Tabanlı Ajan")
        app.rows_var.set("3")
        app.cols_var.set("3")
        app.start()
        self.pump(0.5)
        app.toggle_pause()
        agent = app.simulation.agent
        before = dict(agent.model_snapshot().observations)
        snapshot = app._displayed_snapshot(app.simulation.environment)
        self.assertIsNot(snapshot.observations, agent._memory)
        with self.assertRaises(TypeError):
            snapshot.observations["A1"] = None
        app._draw()
        self.assertEqual(dict(agent.model_snapshot().observations), before)

    def test_two_room_note_only_for_model_in_1x2(self):
        app = self.app
        app.agent_var.set("Model Tabanlı Ajan")
        self.root.update()
        self.assertEqual(app.model_note.winfo_manager(), "pack")
        app.rows_var.set("2")
        self.root.update()
        self.assertEqual(app.model_note.winfo_manager(), "")

    def test_panels_side_by_side_or_stacked(self):
        app = self.app
        self.root.deiconify()
        app.agent_var.set("Model Tabanlı Ajan")
        app.rows_var.set("3")
        app.cols_var.set("3")
        app.start()
        self.root.geometry("1100x760")
        self.root.update()
        self.assertEqual(int(app.model_frame.grid_info()["column"]), 1)
        self.root.geometry("700x1000")
        self.root.update()
        self.assertEqual(int(app.model_frame.grid_info()["row"]), 1)
        self.assertEqual(int(app.model_frame.grid_info()["column"]), 0)
        self.assertTrue(app.start_button.winfo_ismapped())
        self.assertTrue(app.log_text.winfo_ismapped())

    def test_status_line_is_shown_at_startup(self):
        self.assertIn("Hazır", self.app.status_var.get())

    def test_real_panel_uses_full_width_without_model(self):
        app = self.app
        self.root.deiconify()
        self.root.geometry("900x760")
        self.root.update()
        board_width = app.board.winfo_width()
        self.assertGreater(app.env_frame.winfo_width(), board_width * 0.95)
        app.agent_var.set("Model Tabanlı Ajan")
        self.root.update()
        self.assertLess(app.env_frame.winfo_width(), board_width * 0.8)
        app.agent_var.set("Basit Refleks Ajan")
        self.root.update()
        self.assertGreater(app.env_frame.winfo_width(), board_width * 0.95)

    def test_stale_threshold_does_not_change_agent_decisions(self):
        """Görsel eskime eşiği yalnızca çizimi etkiler, ajanın kararlarını değil."""
        def run(threshold):
            with mock.patch("gui.stale_threshold", return_value=threshold):
                app = self.app
                app.agent_var.set("Model Tabanlı Ajan")
                app.rows_var.set("4")
                app.cols_var.set("4")
                app.seed_var.set("13")
                app.start()
                app.step_timer.cancel()
                app.dirt_timer.cancel()
                for i in range(150):
                    app.simulation.step()
                    if i % 4 == 0:
                        app.simulation.dirty_tick()
                    app._draw()
                # Gerçek saate bağlı zaman damgaları karşılaştırmaya alınmaz.
                log = [r.rooms if isinstance(r, DirtRecord) else (r.step, r.room, r.status, r.action)
                       for r in app.simulation.log]
                categories = self.model_categories()
                app.stop()
                return log, categories

        log_low, cats_low = run(1)
        log_high, cats_high = run(10 ** 6)
        self.assertEqual(log_low, log_high)
        self.assertIn(MODEL_STALE, cats_low.values())
        self.assertNotIn(MODEL_STALE, cats_high.values())

    def test_age_is_not_presented_as_time_or_probability(self):
        app = self.app
        app.agent_var.set("Model Tabanlı Ajan")
        self.root.update()
        legend = app.model_legend_var.get()
        self.assertIn("ajan adımı", legend)
        self.assertIn("gerçek süre değildir", legend)
        self.assertNotIn("olasılık", legend)
        texts = [app.model_canvas.itemcget(i, "text") for i in app.model_canvas.find_all()
                 if app.model_canvas.type(i) == "text"]
        self.assertFalse(any(t.endswith(("sn", "s", "%")) for t in texts if t.startswith("yaş")))

    def test_invalid_interval_falls_back_to_last_valid(self):
        self.app.step_var.set("abc")
        self.assertEqual(self.app._read_step_ms(), 700)
        self.app.step_var.set("10")
        self.assertEqual(self.app._read_step_ms(), 100)  # alt sınıra çekilir


if __name__ == "__main__":
    unittest.main()
