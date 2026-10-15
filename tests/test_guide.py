"""Etkileşimli "Nasıl Oynanır?" rehberi testleri."""

import tkinter as tk
import unittest
from unittest import mock

import guide
from guide import GuideTour, fallback_card, intersects, place_card
from gui import GUIDE_DEMO_SEED, GUIDE_DEMO_STEPS, GUIDE_LOCK_TAG, VacuumApp
from simulation import SimulationState
from views import MODEL_STALE, MODEL_UNKNOWN, model_category, stale_threshold
from gui import AppShell
from welcome import GUIDE_STEPS, GuideStep

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


class PlaceCardTests(unittest.TestCase):
    """Açıklama kutusu yerleşimi (arayüzden bağımsız)."""

    def assert_valid(self, result, target, window, card, margin=12):
        self.assertIsNotNone(result)
        x, y, _ = result
        rect = (x, y, x + card[0], y + card[1])
        self.assertFalse(intersects(rect, target))
        self.assertGreaterEqual(x, margin)
        self.assertGreaterEqual(y, margin)
        self.assertLessEqual(rect[2], window[0] - margin)
        self.assertLessEqual(rect[3], window[1] - margin)

    def test_prefers_below_then_above_then_sides(self):
        window, card = (1400, 900), (400, 240)
        self.assertEqual(place_card((100, 100, 300, 160), window, card)[2], "below")
        self.assertEqual(place_card((100, 700, 300, 860), window, card)[2], "above")
        self.assertEqual(place_card((100, 200, 300, 800), window, card)[2], "right")
        self.assertEqual(place_card((900, 200, 1380, 800), window, card)[2], "left")

    def test_result_never_covers_target_and_stays_inside(self):
        window, card = (1000, 760), (360, 220)
        for target in [(10, 10, 200, 60), (400, 300, 600, 420), (700, 600, 990, 750), (20, 200, 980, 260)]:
            with self.subTest(target=target):
                self.assert_valid(place_card(target, window, card), target, window, card)

    def test_no_position_when_target_fills_window(self):
        self.assertIsNone(place_card((0, 0, 680, 700), (680, 720), (300, 200)))

    def test_fallback_minimises_overlap(self):
        target, window, card = (0, 0, 680, 560), (680, 720), (300, 200)
        x, y, side = fallback_card(target, window, card)
        self.assertEqual(side, "overlap")
        overlap = guide.overlap_area((x, y, x + card[0], y + card[1]), target)
        self.assertLessEqual(overlap, card[0] * card[1] * 0.5)
        self.assertGreaterEqual(y, 400)                      # hedeften uzak, alt bölgede


ALL_STEPS = tuple(GuideStep(f"Başlık {key}", f"Açıklama {key}.", key) for key in TARGET_KEYS)


class GuideTourTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.events = []
        self.app = VacuumApp(self.root, on_home=lambda: None)
        self.app.prepare_guide_demo()
        self.root.deiconify()
        self.root.geometry("1300x860+20+20")
        self.root.update()
        self.tour = None
        self.addCleanup(self.cleanup_tour)

    def cleanup_tour(self):
        if self.tour is not None and self.root_alive():
            self.tour.destroy()
            self.app.shutdown()

    def start(self, steps=ALL_STEPS, dim=True):
        self.tour = GuideTour(self.app, steps, on_home=lambda: self.events.append("home"),
                              on_play=lambda: self.events.append("play"), dim=dim)
        self.root.update()
        self.tour.reposition()
        self.root.update()
        return self.tour

    def test_unknown_target_is_rejected(self):
        with self.assertRaises(ValueError):
            GuideTour(self.app, (GuideStep("x", "y", "yok"),))
        self.assertFalse(self.app.interaction_locked)

    def test_every_step_highlights_its_target_without_covering_it(self):
        tour = self.start()
        for index, key in enumerate(TARGET_KEYS):
            with self.subTest(step=key):
                tour.show_step(index)
                self.root.update()
                widget = self.app.guide_targets()[key]
                self.assertTrue(widget.winfo_ismapped())
                hole = tour.hole_rect()
                target = tour.target_rect()
                self.assertTrue(hole[0] <= target[0] and hole[1] <= target[1])
                self.assertTrue(hole[2] >= min(target[2], self.root.winfo_width()))
                self.assertNotEqual(tour.card_side, "overlap")
                self.assertFalse(intersects(tour.card_rect(), hole))
                # Vurgu çerçevesi deliğin kenarında.
                top = tour.ring[0]
                self.assertEqual((top.winfo_x(), top.winfo_y()), (hole[0], hole[1]))

    def test_dim_overlay_matches_window_and_has_a_hole(self):
        tour = self.start()
        if tour.overlay is None:
            self.skipTest("Bu sistemde saydam katman desteklenmiyor")
        overlay = tour.overlay
        self.assertEqual(float(overlay.attributes("-alpha")), guide.DIM_ALPHA)
        self.assertEqual((overlay.winfo_rootx(), overlay.winfo_rooty()),
                         (self.root.winfo_rootx(), self.root.winfo_rooty()))
        self.assertEqual((overlay.winfo_width(), overlay.winfo_height()),
                         (self.root.winfo_width(), self.root.winfo_height()))
        holes = tour.dim_canvas.find_withtag("hole")
        self.assertEqual(len(holes), 1)
        self.assertEqual(tuple(round(v) for v in tour.dim_canvas.coords(holes[0])), tour.hole_rect())

    def test_next_back_and_keyboard(self):
        tour = self.start()
        self.assertEqual(str(tour.back_button["state"]), "disabled")
        tour.next()
        tour.next()
        self.assertEqual(tour.navigator.index, 2)
        tour.back()
        self.assertEqual(tour.navigator.index, 1)
        bindings = self.root.bind()
        for sequence in ("<Key-Right>", "<Key-Return>", "<Key-Left>", "<Key-Escape>"):
            self.assertIn(sequence, bindings)
        self.root.focus_force()                           # tuş olayları odaklı pencereye gider
        self.root.update()
        self.root.event_generate("<Right>")
        self.root.update()
        self.assertEqual(tour.navigator.index, 2)
        self.root.event_generate("<Left>")
        self.root.update()
        self.assertEqual(tour.navigator.index, 1)
        tour.show_step(0)
        tour.back()                                       # sınırda etkisiz
        self.assertEqual(tour.navigator.index, 0)
        self.root.event_generate("<Escape>")
        self.root.update()
        self.assertEqual(self.events, ["home"])

    def test_last_step_offers_home_and_play(self):
        tour = self.start()
        tour.show_step(len(ALL_STEPS) - 1)
        self.root.update()
        self.assertTrue(tour.finish_home_button.winfo_ismapped())
        self.assertTrue(tour.play_button.winfo_ismapped())
        self.assertFalse(tour.next_button.winfo_ismapped())
        self.assertEqual(tour.finish_home_button["text"], "Ana Menü'ye Dön")
        tour.next()                                       # son adımda ileri yok
        self.assertTrue(tour.is_last)
        tour.play_button.invoke()
        tour.finish_home_button.invoke()
        self.assertEqual(self.events, ["play", "home"])

    def test_simulation_does_not_advance_and_controls_are_locked(self):
        tour = self.start()
        steps = self.app.simulation.step_count
        self.assertTrue(self.app.interaction_locked)
        for _ in range(3):
            tour.next()
        self.pump(0.5)
        self.assertEqual(self.app.simulation.step_count, steps)
        self.assertFalse(self.app.step_timer.is_pending)
        self.assertFalse(self.app.dirt_timer.is_pending)

    def test_destroy_removes_everything(self):
        tour = self.start()
        before_children = set(self.root.winfo_children())
        tour._schedule_reposition()                       # bekleyen tetikleme de iptal edilmeli
        tour.destroy()
        self.tour = None
        self.assertFalse(self.app.interaction_locked)
        self.assertEqual([w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)], [])
        self.assertTrue(all(not frame.winfo_exists() for frame in tour.ring))
        self.assertLess(len(self.root.winfo_children()), len(before_children))
        self.assertEqual(self.pending_after_jobs(), ())
        bindings = self.root.bind()
        self.assertNotIn("<Key-Right>", bindings)
        self.assertNotIn("<Key-Left>", bindings)
        self.assertIn("<Key-space>", bindings)           # simülasyon kısayolları geri geldi
        self.app.shutdown()

    def test_follows_window_resize_and_move(self):
        tour = self.start()
        tour.show_step(TARGET_KEYS.index("log"))
        for geometry in ("1000x760+60+40", "760x720+10+10", "1400x900+0+0"):
            with self.subTest(geometry=geometry):
                self.root.geometry(geometry)
                self.root.update()
                self.pump(0.15)                           # gecikmeli yeniden yerleşim
                self.assertFalse(intersects(tour.card_rect(), tour.hole_rect()))
                if tour.overlay is not None:
                    self.assertEqual((tour.overlay.winfo_width(), tour.overlay.winfo_height()),
                                     (self.root.winfo_width(), self.root.winfo_height()))
                    self.assertEqual(tour.overlay.winfo_rootx(), self.root.winfo_rootx())

    def test_minimize_and_restore(self):
        tour = self.start()
        self.root.iconify()
        self.root.update()
        self.pump(0.2)
        self.assertEqual(tour.card.state(), "withdrawn")
        if tour.overlay is not None:
            self.assertEqual(tour.overlay.state(), "withdrawn")
        self.root.deiconify()
        self.root.update()
        self.pump(0.3)
        self.assertEqual(tour.card.state(), "normal")
        if tour.overlay is not None:
            self.assertEqual(tour.overlay.state(), "normal")

    def test_without_transparency_shows_ring_and_card_only(self):
        tour = self.start(dim=False)
        self.assertIsNone(tour.overlay)
        self.assertTrue(tour.ring[0].winfo_ismapped())
        self.assertEqual(tour.card.state(), "normal")
        tour.next()
        tour.destroy()
        self.tour = None
        self.assertEqual([w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)], [])
        self.app.shutdown()

    def test_unsupported_transparency_falls_back_safely(self):
        real = tk.Toplevel.attributes

        def no_transparency(widget, *args):
            if args and args[0] == "-transparentcolor":
                raise tk.TclError("desteklenmiyor")
            return real(widget, *args)

        with mock.patch.object(tk.Toplevel, "attributes", no_transparency):
            tour = self.start()
        self.assertIsNone(tour.overlay)
        self.assertEqual([w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)], [tour.card])

    def test_narrow_window_keeps_card_off_targets(self):
        tour = self.start()
        self.root.geometry("680x720")
        self.root.update()
        for index in range(len(ALL_STEPS)):
            with self.subTest(step=TARGET_KEYS[index]):
                tour.show_step(index)
                self.root.update()
                card = tour.card_rect()
                self.assertFalse(intersects(card, tour.hole_rect()))
                self.assertGreaterEqual(card[0], 0)
                self.assertLessEqual(card[2], self.root.winfo_width())
                self.assertLessEqual(card[3], self.root.winfo_height())


class GuideContentTests(unittest.TestCase):
    def test_sixteen_steps_in_order(self):
        self.assertEqual(len(GUIDE_STEPS), 16)
        self.assertEqual(tuple(step.section for step in GUIDE_STEPS), TARGET_KEYS)
        titles = [step.title for step in GUIDE_STEPS]
        self.assertEqual(titles[0], "Adım aralığı")
        self.assertEqual(titles[-1], "Ana Menü'ye dönüş")
        self.assertEqual(len(set(titles)), 16)

    def test_texts_describe_agents_correctly(self):
        text = " ".join(step.body for step in GUIDE_STEPS)
        self.assertIn("makine öğrenmesi yapmaz", text)
        self.assertIn("geçmiş gözlemlerini", text)
        self.assertIn("BFS", text)
        self.assertNotIn("öğrenir", text)
        agent = next(step for step in GUIDE_STEPS if step.section == "agent").body
        for word in ("refleks", "Model tabanlı", "Amaç tabanlı"):
            self.assertIn(word, agent)

    def test_texts_match_application_values(self):
        from gui import DEFAULT_STEP_MS, MAX_STEP_MS, MIN_STEP_MS
        bodies = {step.section: step.body for step in GUIDE_STEPS}
        self.assertIn(str(DEFAULT_STEP_MS), bodies["step"])
        self.assertTrue(MIN_STEP_MS < DEFAULT_STEP_MS < MAX_STEP_MS)
        self.assertIn("%30", bodies["dirt"])
        self.assertIn("1–6", bodies["rows"])
        self.assertIn("Ekranı", bodies["log"])
        self.assertIn("Boşluk", bodies["pause"])
        self.assertIn("Esc", bodies["stop"])


class GuideFlowTests(AppTestCase):
    """Açılış ekranı → Nasıl Oynanır? → 16 adım → Ana Menü / Oyna."""

    def setUp(self):
        super().setUp()
        self.shell = AppShell(self.root)
        self.root.deiconify()
        self.root.geometry("1300x860+20+20")
        self.root.update()
        self.addCleanup(lambda: self.shell.close() if self.root_alive() else None)

    def open_guide(self):
        self.shell.screen.guide_button.invoke()
        self.root.update()
        return self.shell.tour

    def toplevels(self):
        return [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)]

    def test_all_sixteen_steps_work(self):
        tour = self.open_guide()
        self.assertEqual(self.shell.current, "guide")
        self.assertTrue(self.shell.app.interaction_locked)
        steps_before = self.shell.app.simulation.step_count
        for index, step in enumerate(GUIDE_STEPS):
            with self.subTest(step=step.section):
                self.assertEqual(tour.navigator.index, index)
                self.assertEqual(tour.title_label["text"], step.title)
                self.assertEqual(tour.position_label["text"], f"Adım {index + 1} / 16")
                self.root.update()
                self.assertTrue(tour.target_widget().winfo_ismapped())
                self.assertFalse(intersects(tour.card_rect(), tour.hole_rect()))
                if index < len(GUIDE_STEPS) - 1:
                    tour.next_button.invoke()
        self.assertTrue(tour.is_last)
        self.assertTrue(tour.play_button.winfo_ismapped())
        self.assertTrue(tour.finish_home_button.winfo_ismapped())
        self.assertEqual(self.shell.app.simulation.step_count, steps_before)

    def test_home_from_any_step_cleans_up(self):
        for index in (0, 7, 15):
            with self.subTest(step=index):
                tour = self.open_guide()
                app = self.shell.app
                tour.show_step(index)
                tour._schedule_reposition()
                (tour.finish_home_button if tour.is_last else tour.home_button).invoke()
                self.assertEqual(self.shell.current, "welcome")
                self.assertIsNone(self.shell.tour)
                self.assertIsNone(self.shell.app)
                self.assertEqual(self.toplevels(), [])
                self.assertFalse(app.interaction_locked)
                self.assertIs(app.simulation.state, SimulationState.STOPPED)
                self.shell.screen.destroy()           # açılış ekranının kendi tetiklemesi hariç
                self.shell.screen = None
                self.assertEqual(self.pending_after_jobs(), ())
                self.shell.show_welcome()
                self.root.update()

    def test_escape_returns_home(self):
        self.open_guide()
        self.root.focus_force()
        self.root.update()
        self.root.event_generate("<Escape>")
        self.root.update()
        self.assertEqual(self.shell.current, "welcome")

    def test_play_from_last_step_starts_clean_simulation(self):
        tour = self.open_guide()
        guide_app = self.shell.app
        tour.show_step(15)
        tour.play_button.invoke()
        self.root.update()
        app = self.shell.app
        self.assertEqual(self.shell.current, "simulation")
        self.assertIsNot(app, guide_app)
        self.assertIsNone(self.shell.tour)
        self.assertEqual(self.toplevels(), [])
        self.assertFalse(app.interaction_locked)
        self.assertIsNone(app.simulation)                 # rehber örneği taşınmaz
        self.assertEqual(app.log_entries(), [])
        self.assertIn("<Key-space>", self.root.bind())
        app.step_var.set("100")
        app.start()
        self.pump(0.4)
        self.assertGreater(app.simulation.step_count, 0)

    def test_close_window_during_guide(self):
        tour = self.open_guide()
        tour.show_step(5)
        self.shell._clear()
        self.assertEqual(self.pending_after_jobs(), ())
        self.assertEqual(self.toplevels(), [])
        self.shell.close()


if __name__ == "__main__":
    unittest.main()
