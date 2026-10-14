"""Tema modülü testleri: renkler, simge/metin seçenekleri ve ttk stilleri."""

import os
import re
import subprocess
import sys
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

import theme

ROOT = Path(__file__).resolve().parent.parent


class ThemeConstantTests(unittest.TestCase):
    def test_colors_are_hex_codes(self):
        for name, value in {**theme.COLORS, **theme.CANVAS_COLORS}.items():
            with self.subTest(color=name):
                self.assertRegex(value, r"^#[0-9a-f]{6}$")

    def test_module_does_not_load_tkinter_on_import(self):
        """Sabitler Tkinter'dan bağımsızdır; Tkinter yalnızca tema uygulanırken yüklenir."""
        code = "import sys, theme; print('tkinter' in sys.modules)"
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                                timeout=60)
        self.assertEqual(result.stdout.strip(), "False", result.stderr)

    def test_theme_description_names_the_theme(self):
        text = theme.theme_description()
        if theme.bootstrap_available():
            self.assertRegex(text, r"^ttkbootstrap \d+\.\d+")
        else:
            self.assertIn("standart ttk", text)

    def test_requirements_pin_the_same_version_as_main_header(self):
        requirement = re.search(r"^ttkbootstrap==([\d.]+)$",
                                (ROOT / "requirements.txt").read_text(encoding="utf-8"), re.M).group(1)
        header = (ROOT / "main.py").read_text(encoding="utf-8").split('"""', 1)[0]
        self.assertIn(f"ttkbootstrap=={requirement}", header)
        self.assertIn("pip install -r requirements.txt", header)


class TextAlternativeTests(unittest.TestCase):
    def test_button_text_always_contains_the_word(self):
        for key in theme.BUTTON_SYMBOLS:
            with self.subTest(key=key):
                self.assertTrue(theme.button_text(key, "Başlat").endswith("Başlat"))

    def test_text_only_mode_drops_symbols(self):
        with mock.patch.dict(os.environ, {theme.PLAIN_TEXT_ENV: "1"}):
            self.assertEqual(theme.button_text("start", "Başlat"), "Başlat")
            self.assertIsNone(theme.icon_font_family(None))

    def test_button_options_in_both_modes(self):
        with mock.patch.object(theme, "bootstrap_available", return_value=True):
            self.assertEqual(theme.button_options("primary"), {"bootstyle": "primary"})
            self.assertEqual(theme.button_options("danger"), {"style": "Stop.TButton"})
        with mock.patch.object(theme, "bootstrap_available", return_value=False):
            self.assertEqual(theme.button_options("primary"), {"style": "Start.TButton"})
            self.assertEqual(theme.widget_options("info"), {})


class ThemeSetupTests(unittest.TestCase):
    def make_root(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Ekran bulunamadı: {exc}")
        root.withdraw()
        self.addCleanup(root.destroy)
        return root

    def test_setup_applies_page_and_card_colors(self):
        root = self.make_root()
        style = theme.setup(root)
        self.assertEqual(str(root.cget("background")), theme.COLORS["page"])
        self.assertEqual(style.lookup("Card.TFrame", "background"), theme.COLORS["card"])
        self.assertEqual(style.lookup("Stop.TButton", "foreground"), theme.COLORS["danger"])
        self.assertTrue(style.lookup("Log.Treeview", "rowheight"))

    def test_default_fonts_match_body_font(self):
        """Düğme ve giriş alanları etiketlerle aynı gövde yazı tipini kullanır."""
        from tkinter import font as tkfont
        root = self.make_root()
        theme.setup(root)
        default = tkfont.Font(root=root, name="TkDefaultFont", exists=True)
        self.assertEqual(default.actual("family"), theme.FONT_FAMILY)
        self.assertEqual(int(default.cget("size")), theme.FONT_SIZES["body"])

    def test_setup_works_for_successive_windows(self):
        """Pencere kapatılıp yenisi açıldığında tema yeniden uygulanabilmeli (testler ve yeniden açılış)."""
        from tkinter import ttk
        for _ in range(2):
            try:
                root = tk.Tk()
            except tk.TclError as exc:
                self.skipTest(f"Ekran bulunamadı: {exc}")
            root.withdraw()
            style = theme.setup(root)
            button = ttk.Button(root, text="Başlat", **theme.button_options("primary"))
            root.update_idletasks()
            self.assertTrue(button.cget("style"))
            self.assertEqual(style.lookup("Page.TFrame", "background"), theme.COLORS["page"])
            root.destroy()

    def test_plain_ttk_fallback(self):
        """ttkbootstrap yokmuş gibi: standart ttk 'clam' teması aynı renklerle kullanılır."""
        root = self.make_root()
        with mock.patch.object(theme, "bootstrap_available", return_value=False):
            style = theme.setup(root)
            self.assertEqual(style.theme_use(), "clam")
            self.assertEqual(style.lookup("Start.TButton", "background"), theme.COLORS["primary"])
            self.assertEqual(theme.button_options("primary"), {"style": "Start.TButton"})


if __name__ == "__main__":
    unittest.main()
