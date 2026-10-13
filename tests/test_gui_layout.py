"""Faz 6 arayüz yerleşimi: başlık, ayarlar kartı, kontrol düğmeleri ve duyarlı yerleşim.

Bu testler yalnızca görünümü denetler; simülasyon davranışı test_gui.py'de sınanır.
"""

import os
import tkinter as tk
import unittest
from unittest import mock

import theme
from gui import APP_SUBTITLE, APP_TITLE, SEED_PLACEHOLDER, SHORTCUTS_TEXT, VacuumApp


class LayoutTestCase(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Ekran bulunamadı: {exc}")
        self.root.withdraw()
        self.app = VacuumApp(self.root)

    def tearDown(self):
        self.app.on_close()

    def show(self, geometry):
        self.root.deiconify()
        self.root.geometry(geometry)
        self.root.update()
        self.root.update()


class HeaderAndSettingsTests(LayoutTestCase):
    def test_header_texts(self):
        texts = {str(w.cget("text")) for w in self.root.winfo_children()[0].winfo_children()
                 if w.winfo_class() == "TLabel"}
        self.assertIn(APP_TITLE, texts)
        self.assertIn(APP_SUBTITLE, texts)
        self.assertEqual(APP_SUBTITLE,
                         "Yapay zekâ ajanlarının ortamı algılama ve temizlik davranışlarını simüle edin.")
        self.assertNotIn("öğren", APP_SUBTITLE)
        self.assertEqual(self.root.title(), APP_TITLE)

    def test_fields_in_one_row_when_wide_and_wrap_when_narrow(self):
        app = self.app
        self.show("1400x800")
        rows = {int(frame.grid_info()["row"]) for frame, _ in app._fields}
        self.assertEqual(rows, {0}, "Geniş pencerede altı alan tek satırda")
        self.show("700x800")
        rows = {int(frame.grid_info()["row"]) for frame, _ in app._fields}
        self.assertEqual(rows, {0, 1}, "Dar pencerede alanlar iki satıra iner")
        self.assertTrue(all(frame.winfo_ismapped() for frame, _ in app._fields))

    def test_seed_placeholder_is_not_a_value(self):
        app = self.app
        self.show("1200x800")
        self.assertEqual(app.seed_var.get(), "")
        self.assertEqual(app.seed_placeholder.cget("text"), SEED_PLACEHOLDER)
        self.assertTrue(app.seed_placeholder.winfo_ismapped())
        app.seed_var.set("42")
        self.root.update()
        self.assertFalse(app.seed_placeholder.winfo_ismapped())
        app.seed_var.set("")
        self.root.update()
        self.assertTrue(app.seed_placeholder.winfo_ismapped())
        app.start()                                    # örnek metin seed olarak kullanılmaz
        self.assertIsNone(app.simulation.seed)


class BoardTests(LayoutTestCase):
    def test_panel_cards_show_titles_and_room_count(self):
        app = self.app
        app.agent_var.set("Model Tabanlı Ajan")
        app.rows_var.set("3")
        app.cols_var.set("4")
        self.root.update()
        self.assertEqual(app.env_count["text"], "3 × 4 oda")
        self.assertEqual(app.model_count["text"], "3 × 4 oda")
        self.assertEqual(app.model_title.title_label["text"], "Ajanın iç modeli")
        self.assertEqual(app.model_title.note_label["text"], "(gerçek durum değil)")

    def test_side_by_side_cards_have_equal_width(self):
        app = self.app
        app.agent_var.set("Amaç Tabanlı Ajan")
        self.show("1400x760")
        self.assertEqual(int(app.model_frame.grid_info()["column"]), 1)
        self.assertLessEqual(abs(app.env_frame.winfo_width() - app.model_frame.winfo_width()), 2)

    def test_legend_lists_items_with_color_swatches(self):
        app = self.app
        app.agent_var.set("Model Tabanlı Ajan")
        self.show("1400x760")
        swatches = [tag for tag in app.model_legend.tag_names() if tag.startswith("swatch-")]
        self.assertGreaterEqual(len(swatches), 4)
        self.assertGreaterEqual(int(app.model_legend["height"]), 2)      # öğeler + yaş notu

    def test_legend_grows_when_narrow(self):
        app = self.app
        app.agent_var.set("Amaç Tabanlı Ajan")
        self.show("1400x760")
        wide = int(app.model_legend["height"])
        self.show("900x760")                        # yan yana, daha dar kartlar
        self.assertGreater(int(app.model_legend["height"]), wide)

    def test_plain_tk_widgets_keep_theme_colors(self):
        """ttkbootstrap düz Tk bileşenlerinin rengini değiştirmemeli."""
        app = self.app
        self.assertEqual(str(app.env_legend["background"]), theme.COLORS["card"])
        self.assertEqual(int(app.env_legend["highlightthickness"]), 0)
        self.assertEqual(str(app.shortcut_badge["background"]), theme.COLORS["badge_bg"])
        self.assertEqual(str(app.canvas["background"]), theme.COLORS["card"])


class ControlTests(LayoutTestCase):
    def test_buttons_keep_their_words(self):
        app = self.app
        for button, word in ((app.start_button, "Başlat"), (app.pause_button, "Duraklat"),
                             (app.stop_button, "Durdur"), (app.compare_button, "Ajanları Karşılaştır")):
            with self.subTest(word=word):
                self.assertTrue(str(button["text"]).endswith(word))

    def test_text_only_mode_has_no_symbols(self):
        self.app.on_close()
        with mock.patch.dict(os.environ, {theme.PLAIN_TEXT_ENV: "1"}):
            self.root = tk.Tk()
            self.root.withdraw()
            self.app = VacuumApp(self.root)
            self.assertEqual(self.app.start_button["text"], "Başlat")
            self.assertEqual(self.app.compare_button["text"], "Ajanları Karşılaştır")
            self.assertEqual(self.app.shortcut_badge["text"], SHORTCUTS_TEXT)
            self.app.start()
            self.app.toggle_pause()
            self.assertEqual(self.app.pause_button["text"], "Devam")

    def test_button_styles(self):
        app = self.app
        if theme.bootstrap_available():
            self.assertEqual(str(app.start_button.cget("style")), "primary.TButton")
        else:
            self.assertEqual(str(app.start_button.cget("style")), "Start.TButton")
        self.assertEqual(str(app.stop_button.cget("style")), "Stop.TButton")

    def relayout(self, geometry, compact_height):
        """Ekran yüksekliğinden bağımsız sınamak için sıkı yerleşim eşiği değiştirilir."""
        with mock.patch("gui.COMPACT_HEIGHT", compact_height):
            self.show(geometry)
            self.app._density = None
            self.app._update_density()
            self.root.update()

    def test_shortcut_badge_moves_or_folds_into_note(self):
        app = self.app
        self.relayout("1440x760", 300)
        self.assertEqual(int(app.shortcut_badge.grid_info()["row"]), 0, "Geniş: düğmelerle aynı satırda")
        self.relayout("700x760", 300)
        self.assertEqual(int(app.shortcut_badge.grid_info()["row"]), 1, "Dar ve uzun: düğmelerin altında")
        self.relayout("700x620", 900)
        self.assertEqual(app.shortcut_badge.winfo_manager(), "", "Dar ve alçak: rozet gizli")
        self.assertIn(SHORTCUTS_TEXT, str(app.settings_note["text"]))
        self.assertTrue(app.start_button.winfo_ismapped())

    def test_subtitle_moves_next_to_title_in_low_window(self):
        app = self.app
        self.relayout("1200x760", 300)
        self.assertEqual(int(app.subtitle.grid_info()["row"]), 1, "Ferah: başlığın altında")
        self.relayout("1200x640", 900)
        self.assertEqual(int(app.subtitle.grid_info()["row"]), 0, "Sıkı: başlığın yanında")
        self.assertTrue(app.subtitle.winfo_ismapped())
        self.assertLess(int(app.logo["height"]), app._px(52))


if __name__ == "__main__":
    unittest.main()
