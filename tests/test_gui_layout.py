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

    def relayout(self, geometry, compact_height):
        """Ekran yüksekliğinden bağımsız sınamak için sıkı yerleşim eşiği değiştirilir."""
        with mock.patch("gui.COMPACT_HEIGHT", compact_height):
            self.show(geometry)
            self.app._density = None
            self.app._fields_columns = None
            self.app._stats_layout = None
            self.app._update_density()
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

    def field_rows(self):
        return {int(frame.grid_info()["row"]) for frame, _ in self.app._fields}

    def test_fields_in_one_row_when_wide_and_wrap_when_narrow(self):
        app = self.app
        self.relayout("1400x760", 300)
        self.assertEqual(self.field_rows(), {0}, "Geniş pencerede altı alan tek satırda")
        self.assertEqual(app._fields[0][0].label["text"], "Adım aralığı (ms)")
        self.relayout("700x760", 300)
        self.assertEqual(self.field_rows(), {0, 1}, "Dar ve ferah pencerede alanlar iki satıra iner")
        self.assertTrue(all(frame.winfo_ismapped() for frame, _ in app._fields))

    def test_short_labels_keep_fields_in_one_row_in_low_narrow_window(self):
        app = self.app
        self.relayout("700x620", 900)
        self.assertEqual(self.field_rows(), {0})
        labels = [frame.label["text"] for frame, _ in app._fields]
        self.assertEqual(labels, ["Adım (ms)", "Kirlenme (sn)", "Seed", "Satır", "Sütun", "Ajan türü"])

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


class BoardSizeTests(LayoutTestCase):
    def test_low_board_keeps_panels_side_by_side_and_hides_legends(self):
        app = self.app
        app.agent_var.set("Model Tabanlı Ajan")
        app.rows_var.set("3")
        app.cols_var.set("3")
        self.relayout("700x620", 900)
        self.assertEqual(int(app.model_frame.grid_info()["column"]), 1, "Alçak tahta: yan yana")
        self.assertEqual(app.env_legend.winfo_manager(), "", "Çok alçak kartta açıklama gizli")
        self.assertGreater(app.canvas.winfo_height(), 20)
        self.assertGreater(app.model_canvas.winfo_height(), 20)

    def test_legends_return_when_there_is_room(self):
        app = self.app
        app.agent_var.set("Model Tabanlı Ajan")
        self.relayout("700x620", 900)
        with mock.patch("gui.LEGEND_MIN_PANEL_HEIGHT", 0):
            app._board_layout = None
            app._layout_board()
            self.root.update()
            self.assertEqual(app.env_legend.winfo_manager(), "pack")
            self.assertEqual(app.model_legend.winfo_manager(), "pack")


class StatsTests(LayoutTestCase):
    def visible(self):
        return [key for key, cell in self.app.stat_cells.items() if cell.winfo_manager() == "grid"]

    def test_cards_depend_on_agent_capabilities(self):
        app = self.app
        self.show("1440x800")
        self.assertNotIn("known", self.visible())
        self.assertNotIn("target", self.visible())
        app.agent_var.set("Model Tabanlı Ajan")
        self.root.update()
        self.assertIn("known", self.visible())
        self.assertNotIn("target", self.visible())
        app.agent_var.set("Amaç Tabanlı Ajan")
        self.root.update()
        self.assertIn("target", self.visible())

    def test_values_follow_simulation(self):
        app = self.app
        self.show("1440x800")
        self.assertEqual(app.stat_vars["state"].get(), "Hazır")
        self.assertEqual(app.stat_vars["size"].get(), "1 × 2")
        app.start()
        app.step_timer.cancel()
        app.dirt_timer.cancel()
        for _ in range(5):
            app._on_step_timer()
            app.step_timer.cancel()
        sim = app.simulation
        self.assertEqual(app.stat_vars["state"].get(), "Çalışıyor")
        self.assertEqual(app.stat_vars["steps"].get(), str(sim.step_count))
        self.assertEqual(app.stat_vars["cleans"].get(), str(sim.clean_count))
        self.assertEqual(app.stat_vars["moves"].get(), str(sim.move_count))
        self.assertIn("Durum: Çalışıyor", app.status_summary())
        app.toggle_pause()
        self.assertEqual(app.stat_vars["state"].get(), "Duraklatıldı")
        self.assertEqual(str(app._stat_values["state"].cget("foreground")), theme.COLORS["warning"])
        app.stop()
        self.assertEqual(app.stat_vars["state"].get(), "Durduruldu")

    def test_one_row_when_wide_several_rows_when_narrow(self):
        app = self.app
        app.agent_var.set("Amaç Tabanlı Ajan")
        self.relayout("1440x760", 300)
        rows = {int(app.stat_cells[k].grid_info()["row"]) for k in self.visible()}
        self.assertEqual(rows, {0})
        self.relayout("700x760", 300)
        rows = {int(app.stat_cells[k].grid_info()["row"]) for k in self.visible()}
        self.assertGreater(len(rows), 1)
        for key in self.visible():                       # değerler kesilmeden sığar
            cell = app.stat_cells[key]
            self.assertGreaterEqual(cell.winfo_width() + 2, cell.texts.winfo_reqwidth())

    def test_compact_window_hides_title_and_icons_if_cards_wrap(self):
        app = self.app
        app.agent_var.set("Amaç Tabanlı Ajan")
        self.relayout("700x620", 900)
        self.assertFalse(app.status_title.winfo_ismapped())
        if app._stat_icons:
            self.assertFalse(any(icon.winfo_ismapped() for icon in app._stat_icons.values()))
        self.relayout("1440x760", 300)
        self.assertTrue(app.status_title.winfo_ismapped())


class LogTableTests(LayoutTestCase):
    def run_steps(self, count, agent="Basit Refleks Ajan", rows="1", cols="2", seed="3"):
        app = self.app
        app.agent_var.set(agent)
        app.rows_var.set(rows)
        app.cols_var.set(cols)
        app.seed_var.set(seed)
        app.start()
        app.step_timer.cancel()
        app.dirt_timer.cancel()
        for _ in range(count):
            app._on_step_timer()
            app.step_timer.cancel()
        return app

    def test_columns(self):
        table = self.app.log_table
        headings = [table.heading(column, "text") for column in table["columns"]]
        self.assertEqual(headings, ["Adım", "Süre", "Oda", "Algı", "Eylem", "Açıklama"])

    def test_step_dirt_goal_and_info_rows(self):
        app = self.run_steps(6, agent="Amaç Tabanlı Ajan", rows="3", cols="3", seed="8")
        record = app.simulation.dirty_tick()
        if record is not None:
            app._log_record(record)
        entries = app.log_entries()
        kinds = {kind for kind, _ in entries}
        self.assertEqual(entries[0][0], "info")                      # "Simülasyon başladı …"
        self.assertIn("step", kinds)
        self.assertIn("goal", kinds)
        steps = [values for kind, values in entries if kind == "step"]
        self.assertEqual([int(v[0]) for v in steps], list(range(1, len(steps) + 1)))
        last = [r for r in app.simulation.log if hasattr(r, "action")][-1]
        self.assertEqual(steps[-1][2], last.room)
        self.assertIn(steps[-1][3], ("Temiz", "Kirli"))
        if record is not None:
            kind, values = entries[-1]
            self.assertEqual(kind, "dirt")
            self.assertIn("Kirlenme", values[5])
        goal = next(values for kind, values in entries if kind == "goal")
        self.assertTrue(goal[5].startswith("Hedef: "))
        self.assertEqual(goal[0], "–", "Hedef satırı adım sayılmaz")

    def test_row_kinds_have_distinct_looks(self):
        table = self.app.log_table
        looks = {kind: (str(table.tag_configure(kind, "foreground")), str(table.tag_configure(kind, "background")))
                 for kind in ("dirt", "goal", "info")}
        self.assertEqual(len(set(looks.values())), 3)
        self.assertEqual(str(looks["dirt"][0]), theme.COLORS["row_dirt_fg"])

    def test_clear_view_keeps_simulation_log(self):
        app = self.run_steps(8)
        log_before = list(app.simulation.log)
        steps = app.simulation.step_count
        app.clear_log_view()
        entries = app.log_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("temizlendi", entries[0][1][5])
        self.assertEqual(app.simulation.log, log_before)            # simülasyonun kaydı aynen duruyor
        self.assertEqual(app.simulation.step_count, steps)
        app._on_step_timer()                                         # yeni adımlar eklenmeye devam eder
        app.step_timer.cancel()
        self.assertEqual(app.log_entries()[-1][0], "step")
        self.assertEqual(app.log_entries()[-1][1][0], str(steps + 1))

    def test_clear_button_is_wired(self):
        app = self.run_steps(3)
        app.clear_log_button.invoke()
        self.assertEqual(len(app.log_entries()), 1)
        self.assertTrue(str(app.clear_log_button["text"]).endswith("Ekranı Temizle"))

    def test_real_cap_of_ten_thousand_rows(self):
        from gui import MAX_LOG_LINES
        app = self.app
        app.start()
        app.step_timer.cancel()
        app.dirt_timer.cancel()
        for i in range(MAX_LOG_LINES + 20):
            app._append_log(f"satır {i}")
        entries = app.log_entries()
        self.assertEqual(len(entries), MAX_LOG_LINES + 1)            # kayıtlar + kaldırma bilgisi
        self.assertIn("21 satır", entries[0][1][5])                  # başlangıç satırı + 20
        self.assertEqual(entries[-1][1][5], f"satır {MAX_LOG_LINES + 19}")


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
