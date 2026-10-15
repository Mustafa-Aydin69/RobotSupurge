"""Etkileşimli "Nasıl Oynanır?" rehberi testleri."""

import tkinter as tk
import unittest

from gui import GUIDE_DEMO_SEED, GUIDE_DEMO_STEPS, GUIDE_LOCK_TAG, VacuumApp
from simulation import SimulationState
from views import MODEL_STALE, MODEL_UNKNOWN, model_category, stale_threshold

TARGET_KEYS = ("step", "dirt", "seed", "rows", "cols", "agent", "start", "pause", "stop", "compare",
               "environment", "model", "plan", "status", "log", "home")


class AppTestCase(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Ekran bulunamadı: {exc}")
        self.root.withdraw()
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.addCleanup(self.close_root)          # ilk eklenen temizlik en son çalışır

    def close_root(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass                                  # test pencereyi zaten kapattı
        self.assertEqual(self.errors, [], "Tkinter geri çağırmasında hata oluştu")

    def root_alive(self):
        try:
            return bool(self.root.winfo_exists())
        except tk.TclError:
            return False

    def pending_after_jobs(self):
        return self.root.tk.splitlist(self.root.tk.call("after", "info"))

    def pump(self, seconds):
        self.root.after(int(seconds * 1000), self.root.quit)
        self.root.mainloop()


class GuideHookTests(AppTestCase):
    def make_app(self):
        app = VacuumApp(self.root, on_home=lambda: None)
        self.addCleanup(lambda: app.shutdown() if self.root_alive() else None)
        return app

    def test_all_guide_targets_exist(self):
        app = self.make_app()
        targets = app.guide_targets()
        self.assertEqual(set(targets), set(TARGET_KEYS))
        for key, widget in targets.items():
            with self.subTest(key=key):
                self.assertTrue(widget.winfo_exists())

    def test_demo_uses_real_simulation_without_timers(self):
        app = self.make_app()
        app.prepare_guide_demo()
        sim = app.simulation
        self.assertIs(sim.state, SimulationState.PAUSED)
        self.assertEqual(sim.step_count, GUIDE_DEMO_STEPS)
        self.assertEqual(sim.seed, GUIDE_DEMO_SEED)
        self.assertEqual((sim.environment.grid.rows, sim.environment.grid.cols), (3, 3))
        self.assertEqual(sim.agent_type, "goal")
        self.assertFalse(app.step_timer.is_pending or app.step_timer.is_paused)
        self.assertFalse(app.dirt_timer.is_pending or app.dirt_timer.is_paused)
        self.assertIsNone(app._clock_job)
        self.assertEqual(self.pending_after_jobs(), ())
        self.pump(0.5)                                # kendiliğinden ilerlemez
        self.assertEqual(sim.step_count, GUIDE_DEMO_STEPS)

    def test_demo_shows_known_unknown_stale_rooms_and_a_route(self):
        """Hedef, rota ve iç model gerçek simülasyondan gelir; sahte veri yoktur."""
        app = self.make_app()
        app.prepare_guide_demo()
        sim = app.simulation
        snapshot = sim.agent.model_snapshot()
        threshold = stale_threshold(sim.environment.grid)
        categories = [model_category(snapshot.observations.get(r), snapshot.age_of(r), threshold)
                      for r in sim.environment.rooms]
        self.assertIn(MODEL_UNKNOWN, categories)
        self.assertIn(MODEL_STALE, categories)
        self.assertGreaterEqual(len(snapshot.observations), 5)
        plan = sim.agent.plan_snapshot()
        self.assertIsNotNone(plan.target)
        self.assertGreaterEqual(len(plan.route), 1)
        self.root.update()
        app._draw()
        self.assertEqual(len(app.model_canvas.find_withtag("plan-target")), 1)
        self.assertEqual(len(app.model_canvas.find_withtag("plan-route")), 1)
        self.assertEqual(len(app.canvas.find_withtag("env-target")), 1)
        kinds = {kind for kind, _ in app.log_entries()}
        self.assertTrue({"step", "goal"} <= kinds)

    def test_demo_is_reproducible(self):
        def run():
            app = self.make_app()
            app.prepare_guide_demo()
            log = [(r.step, r.room, r.status, r.action) if hasattr(r, "action") else r.rooms
                   for r in app.simulation.log]
            app.shutdown()
            return log
        self.assertEqual(run(), run())

    def test_lock_blocks_events_and_restores_bindtags(self):
        app = self.make_app()
        original = {w: w.bindtags() for w in app._interactive_widgets()}
        app.set_interaction_locked(True)
        self.assertTrue(app.interaction_locked)
        for widget in (app.start_button, app.rows_spin, app.agent_combo, app.seed_entry, app.log_table,
                       app.home_button, app.compare_button):
            self.assertEqual(widget.bindtags()[0], GUIDE_LOCK_TAG)
        for sequence in ("<Button>", "<Key>", "<MouseWheel>"):
            script = self.root.bind_class(GUIDE_LOCK_TAG, sequence)
            self.assertTrue(script, sequence)
        bindings = self.root.bind()
        self.assertNotIn("<Key-space>", bindings)
        self.assertNotIn("<Key-Escape>", bindings)
        app.set_interaction_locked(False)
        self.assertFalse(app.interaction_locked)
        self.assertEqual({w: w.bindtags() for w in original}, original)
        self.assertIn("<Key-space>", self.root.bind())

    def test_locked_widgets_ignore_real_input(self):
        """Kilitliyken gerçek fare ve klavye olayları ayarları değiştirmez, simülasyonu başlatmaz."""
        app = self.make_app()
        self.root.deiconify()
        self.root.geometry("1300x860")
        self.root.update()
        app.prepare_guide_demo()
        app.set_interaction_locked(True)
        before = (app.step_var.get(), app.seed_var.get(), app.rows_var.get(), app.agent_var.get())
        steps = app.simulation.step_count
        for widget in (app.seed_entry, app.rows_spin, app.start_button, app.pause_button, app.stop_button):
            x, y = widget.winfo_width() // 2, widget.winfo_height() // 2
            widget.event_generate("<Button-1>", x=x, y=y)
            widget.event_generate("<ButtonRelease-1>", x=x, y=y)
            widget.event_generate("<Key>", keysym="5")
            widget.event_generate("<Up>")
        self.root.event_generate("<space>")
        self.root.event_generate("<Escape>")
        self.root.update()
        self.assertEqual((app.step_var.get(), app.seed_var.get(), app.rows_var.get(), app.agent_var.get()), before)
        self.assertIs(app.simulation.state, SimulationState.PAUSED)
        self.assertEqual(app.simulation.step_count, steps)
        self.assertIsNone(app.compare_window)

    def test_shutdown_removes_lock_and_timers(self):
        app = self.make_app()
        app.prepare_guide_demo()
        app.set_interaction_locked(True)
        app.shutdown()
        self.assertFalse(app.interaction_locked)
        self.assertIs(app.simulation.state, SimulationState.STOPPED)
        self.assertEqual(self.pending_after_jobs(), ())


if __name__ == "__main__":
    unittest.main()
