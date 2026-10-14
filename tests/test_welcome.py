"""Açılış ekranı, rehber ve ekran geçişleri (AppShell) testleri."""

import base64
import struct
import tkinter as tk
import unittest
from pathlib import Path

import theme
import welcome_assets
from gui import AppShell, VacuumApp
from simulation import SimulationState
from welcome import (FEATURES, GUIDE_STEPS, GuideNavigator, GuideScreen, GuideStep, WELCOME_SUBTITLE,
                     WELCOME_TITLE, WelcomeScreen)

ROOT = Path(__file__).resolve().parent.parent
PNG_SIGNATURE = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


class AssetTests(unittest.TestCase):
    def test_embedded_pngs_are_valid_and_sized(self):
        for name, (width, height) in welcome_assets.SIZES.items():
            with self.subTest(name=name):
                data = base64.b64decode(welcome_assets.PNG[name])
                self.assertEqual(data[:8], PNG_SIGNATURE)
                self.assertEqual(struct.unpack(">II", data[16:24]), (width, height))

    def test_every_feature_has_an_icon(self):
        for image_name, text in FEATURES:
            self.assertIn(image_name, welcome_assets.PNG)
            self.assertTrue(text.strip())
        self.assertIn("illustration", welcome_assets.PNG)
        self.assertIn("logo", welcome_assets.PNG)

    def test_module_matches_the_crop_tool(self):
        """welcome_assets.py, kaynak görselden betikle yeniden üretilince birebir aynı çıkar."""
        try:
            from tools import make_welcome_assets
        except ImportError as exc:                  # Pillow yoksa betik çalışamaz
            self.skipTest(f"Pillow yok: {exc}")
        if not make_welcome_assets.SOURCE.exists():
            self.skipTest("Kaynak görsel yok")
        expected = make_welcome_assets.render_module(make_welcome_assets.crop_assets())
        self.assertEqual((ROOT / "welcome_assets.py").read_text(encoding="utf-8"), expected)

    def test_custom_style_names_avoid_ttkbootstrap_keywords(self):
        """ttkbootstrap stil adlarında renk/tür/sınıf anahtar kelimesi arar; özel adlar çakışmamalı."""
        if not theme.bootstrap_available():
            self.skipTest("ttkbootstrap yok")
        import re
        from ttkbootstrap.style import Keywords
        source = (ROOT / "theme.py").read_text(encoding="utf-8")
        names = set(re.findall(r'"([A-Za-z]+)\.T(?:Button|Label|Frame)"', source))
        self.assertIn("HeroAlt", names)
        for name in names:
            for pattern in (Keywords.COLOR_PATTERN, Keywords.TYPE_PATTERN, Keywords.CLASS_PATTERN):
                with self.subTest(name=name, pattern=pattern.pattern[:20]):
                    self.assertIsNone(re.search(pattern, name.lower()))


class GuideNavigatorTests(unittest.TestCase):
    def test_next_and_back_stay_in_range(self):
        nav = GuideNavigator((GuideStep("a", "1"), GuideStep("b", "2"), GuideStep("c", "3")))
        self.assertFalse(nav.can_back)
        self.assertEqual(nav.position_text(), "1 / 3")
        nav.next()
        nav.next()
        self.assertEqual(nav.current.title, "c")
        self.assertFalse(nav.can_next)
        nav.next()                                   # sınırda etkisiz
        self.assertEqual(nav.index, 2)
        nav.back()
        self.assertEqual(nav.current.title, "b")

    def test_empty_guide_is_rejected(self):
        with self.assertRaises(ValueError):
            GuideNavigator(())

    def test_guide_content_is_short_and_real(self):
        self.assertTrue(1 <= len(GUIDE_STEPS) <= 3)
        for step in GUIDE_STEPS:
            self.assertLess(len(step.body), 300)


class ShellTestCase(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Ekran bulunamadı: {exc}")
        self.root.withdraw()
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.shell = AppShell(self.root)
        self.closed = False

    def tearDown(self):
        if not self.closed:
            self.shell.close()
        self.assertEqual(self.errors, [], "Tkinter geri çağırmasında hata oluştu")

    def pending_after_jobs(self):
        return self.root.tk.splitlist(self.root.tk.call("after", "info"))

    def pump(self, seconds):
        self.root.after(int(seconds * 1000), self.root.quit)
        self.root.mainloop()

    def show(self, geometry):
        self.root.deiconify()
        self.root.geometry(geometry)
        self.root.update()
        self.root.update()
        if isinstance(self.shell.screen, WelcomeScreen):
            self.shell.screen.relayout()
            self.root.update()

    def toplevels(self):
        return [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)]


class StartupAndPlayTests(ShellTestCase):
    def test_application_starts_with_welcome_screen(self):
        self.assertEqual(self.shell.current, "welcome")
        self.assertIsNone(self.shell.app)
        self.assertIsInstance(self.shell.screen, WelcomeScreen)
        self.assertEqual(self.root.title(), "Robot Süpürge Ajanı")
        self.show("1400x900")
        canvas = self.shell.screen.canvas
        texts = [canvas.itemcget(i, "text") for i in canvas.find_withtag("title")]
        texts += [canvas.itemcget(i, "text") for i in canvas.find_withtag("subtitle")]
        self.assertEqual(texts, [WELCOME_TITLE, WELCOME_SUBTITLE])
        self.assertEqual(len(canvas.find_withtag("feature-text")), 4)
        self.assertEqual(len(canvas.find_withtag("illustration")), 1)

    def test_run_uses_shell(self):
        from unittest import mock

        import gui
        with mock.patch.object(gui.tk, "Tk", return_value=self.root), \
                mock.patch.object(self.root, "mainloop"), mock.patch.object(gui, "AppShell") as shell:
            gui.run()
        shell.assert_called_once_with(self.root)

    def test_play_opens_simulation_in_same_window(self):
        welcome_canvas = self.shell.screen.canvas
        self.shell.screen.play_button.invoke()
        self.assertEqual(self.shell.current, "simulation")
        self.assertIsInstance(self.shell.app, VacuumApp)
        self.assertFalse(welcome_canvas.winfo_exists())
        self.assertIs(self.shell.app.root, self.root)            # aynı kök pencere
        self.assertEqual(self.toplevels(), [])
        self.assertIsNotNone(self.shell.app.home_button)
        self.assertNotIn("<Key-Return>", self.root.bind())       # açılış kısayolu kaldırıldı

    def test_simulation_behaviour_unchanged_inside_shell(self):
        self.shell.show_simulation()
        app = self.shell.app
        app.step_var.set("100")
        app.seed_var.set("3")
        app.start()
        self.pump(0.6)
        self.assertGreater(app.simulation.step_count, 2)
        app.toggle_pause()
        self.assertIs(app.simulation.state, SimulationState.PAUSED)
        app.stop()
        self.assertIs(app.simulation.state, SimulationState.STOPPED)

    def test_standalone_vacuum_app_has_no_home_button(self):
        self.shell.close()
        self.closed = True
        root = tk.Tk()
        root.withdraw()
        try:
            app = VacuumApp(root)
            self.assertIsNone(app.home_button)
        finally:
            root.destroy()


class HomeTests(ShellTestCase):
    def test_home_stops_running_simulation_and_cleans_up(self):
        self.shell.show_simulation()
        app = self.shell.app
        app.step_var.set("100")
        app.start()
        self.pump(0.3)
        window = app.open_comparison()
        app.home_button.invoke()
        self.assertEqual(self.shell.current, "welcome")
        self.assertIsNone(self.shell.app)
        self.assertIs(app.simulation.state, SimulationState.STOPPED)
        self.assertFalse(app.step_timer.is_pending)
        self.assertFalse(app.dirt_timer.is_pending)
        self.assertIsNone(app._clock_job)
        self.assertTrue(window.closed)
        self.assertEqual(self.toplevels(), [])
        for sequence in ("<Key-space>", "<Key-Escape>"):
            self.assertNotIn(sequence, self.root.bind())
        # Yalnızca açılış ekranının yerleşim tetiklemesi bekleyebilir; simülasyonunkiler kalmaz.
        self.shell.screen.destroy()
        self.shell.screen = None
        self.assertEqual(self.pending_after_jobs(), ())

    def test_home_from_paused_simulation(self):
        self.shell.show_simulation()
        app = self.shell.app
        app.start()
        app.toggle_pause()
        app.go_home()
        self.assertIs(app.simulation.state, SimulationState.STOPPED)
        self.assertFalse(app.step_timer.is_paused)
        self.assertEqual(self.shell.current, "welcome")

    def test_play_again_starts_a_fresh_session(self):
        self.shell.show_simulation()
        first = self.shell.app
        first.step_var.set("100")
        first.start()
        self.pump(0.3)
        first.go_home()
        self.shell.screen.play_button.invoke()
        second = self.shell.app
        self.assertIsNot(second, first)
        self.assertIsNone(second.simulation)
        self.assertEqual(second.log_entries(), [])
        second.step_var.set("100")
        second.start()
        self.pump(0.4)
        self.assertGreater(second.simulation.step_count, 0)
        self.assertIs(first.simulation.state, SimulationState.STOPPED)   # eski oturum çalışmıyor


class GuideScreenTests(ShellTestCase):
    def test_guide_open_navigate_and_return(self):
        self.shell.screen.guide_button.invoke()
        self.assertEqual(self.shell.current, "guide")
        guide = self.shell.screen
        self.assertIsInstance(guide, GuideScreen)
        self.assertEqual(str(guide.back_button["state"]), "disabled")
        self.assertEqual(guide.step_title["text"], GUIDE_STEPS[0].title)
        if len(GUIDE_STEPS) > 1:
            guide.next_button.invoke()
            self.assertEqual(guide.step_title["text"], GUIDE_STEPS[1].title)
            self.assertEqual(str(guide.back_button["state"]), "normal")
        guide.home_button.invoke()
        self.assertEqual(self.shell.current, "welcome")
        self.assertNotIn("<Key-Escape>", self.root.bind())

    def test_play_from_guide(self):
        self.shell.show_guide()
        self.shell.screen.play_button.invoke()
        self.assertEqual(self.shell.current, "simulation")


class CloseTests(ShellTestCase):
    def close_cleanly(self):
        self.shell._clear()                      # kapatmanın ilk adımı: ekran kaldırılır
        self.assertEqual(self.pending_after_jobs(), (), "Kapanışta bekleyen tetikleme kalmamalı")
        self.root.destroy()
        self.closed = True

    def test_close_on_welcome(self):
        self.show("1200x800")
        self.shell.screen._schedule_relayout()   # bekleyen yerleşim tetiklemesi de iptal edilmeli
        self.close_cleanly()

    def test_direct_relayout_leaves_no_orphan_job(self):
        self.show("1200x800")
        screen = self.shell.screen
        for _ in range(3):
            screen._schedule_relayout()
            screen.relayout()
        self.assertEqual(self.pending_after_jobs(), ())
        screen._schedule_relayout()
        self.pump(0.2)                           # tetikleme kendiliğinden çalışır ve biter
        self.assertIsNone(screen._job)
        self.assertEqual(self.pending_after_jobs(), ())

    def test_close_on_guide(self):
        self.shell.show_guide()
        self.close_cleanly()

    def test_close_on_running_simulation(self):
        self.shell.show_simulation()
        self.shell.app.start()
        self.shell.app.open_comparison().start()
        self.close_cleanly()

    def test_window_close_button_uses_shell(self):
        protocol = self.root.protocol("WM_DELETE_WINDOW")
        self.assertIn("close", str(protocol))
        self.shell.close()
        self.closed = True
        with self.assertRaises(tk.TclError):
            self.root.winfo_exists()


class ResizeTests(ShellTestCase):
    def assert_inside(self, canvas, item_or_tag, label):
        x0, y0, x1, y1 = canvas.bbox(item_or_tag)
        width, height = canvas.winfo_width(), canvas.winfo_height()
        self.assertGreaterEqual(x0, -2, label)
        self.assertGreaterEqual(y0, -2, label)
        self.assertLessEqual(x1, width + 2, label)
        self.assertLessEqual(y1, height + 2, label)

    def test_buttons_visible_and_inside_at_all_sizes(self):
        for geometry in ("1536x982", "1100x760", "760x760", "680x720", "1400x600"):
            with self.subTest(geometry=geometry):
                self.show(geometry)
                screen = self.shell.screen
                canvas = screen.canvas
                for button in (screen.play_button, screen.guide_button):
                    self.assertTrue(button.winfo_ismapped())
                    x, y = button.winfo_x(), button.winfo_y()
                    self.assertGreaterEqual(x, 0)
                    self.assertLessEqual(x + button.winfo_width(), canvas.winfo_width() + 2)
                    self.assertLessEqual(y + button.winfo_height(), canvas.winfo_height() + 2)
                for tag in ("title", "subtitle"):
                    self.assert_inside(canvas, tag, tag)
                # Başlık, açıklama ve düğmeler üst üste binmez (yukarıdan aşağıya sıralı).
                title_bottom = canvas.bbox("title")[3]
                subtitle_top, subtitle_bottom = canvas.bbox("subtitle")[1], canvas.bbox("subtitle")[3]
                self.assertLessEqual(title_bottom, subtitle_top + 1)
                self.assertLessEqual(subtitle_bottom, screen.play_button.winfo_y() + 1)
                self.assertLessEqual(screen.play_button.winfo_y() + screen.play_button.winfo_height(),
                                     screen.guide_button.winfo_y() + 1)

    def test_illustration_left_when_wide_and_scaled_down_when_narrow(self):
        self.show("1536x982")
        canvas = self.shell.screen.canvas
        x0, _, x1, _ = canvas.bbox("illustration")
        self.assertLess(x1, canvas.winfo_width() * 0.55)
        self.assertEqual(len(canvas.find_withtag("logo")), 1)
        self.show("760x900")
        self.assertEqual(len(canvas.find_withtag("logo")), 0)       # dar: robot simgesi tekrarlanmaz
        if canvas.find_withtag("illustration"):
            self.assert_inside(canvas, "illustration", "illustration")

    def test_features_wrap_to_two_rows_when_narrow(self):
        self.show("700x900")
        canvas = self.shell.screen.canvas
        rows = {round(canvas.coords(i)[1]) for i in canvas.find_withtag("feature-icon")}
        self.assertEqual(len(rows), 2)

    def test_pillow_free_loader_shows_images(self):
        self.shell._clear()
        screen = WelcomeScreen(self.root, on_play=lambda: None, use_pil=False)
        self.shell.screen = screen
        self.show("1400x900")
        self.assertEqual(len(screen.canvas.find_withtag("illustration")), 1)
        image = screen.images.get("illustration", 300, 300)
        self.assertLessEqual(image.width(), welcome_assets.SIZES["illustration"][0])


if __name__ == "__main__":
    unittest.main()
