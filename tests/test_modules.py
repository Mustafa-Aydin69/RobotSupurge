"""Modül yapısı ve import uyumluluğu testleri."""

import importlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def source(module):
    return (ROOT / f"{module}.py").read_text(encoding="utf-8")


class ImportCompatibilityTests(unittest.TestCase):
    def test_gui_still_exports_names_used_before_split(self):
        """Modülerleştirme öncesi gui'den import edilen isimler hâlâ erişilebilir."""
        gui = importlib.import_module("gui")
        for name in (
            "PausableTimer", "VacuumApp", "compute_layout", "format_elapsed", "format_record",
            "parse_grid_size", "parse_seed", "model_category", "stale_threshold", "agent_has_model",
            "format_goal_change", "MODEL_CLEAN", "MODEL_DIRTY", "MODEL_INFERRED", "MODEL_STALE",
            "MODEL_UNKNOWN", "MODEL_PANEL_TITLE", "MAX_LOG_LINES",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(gui, name))

    def test_moved_objects_are_the_same_objects(self):
        import gui
        import timers
        import views
        self.assertIs(gui.PausableTimer, timers.PausableTimer)
        self.assertIs(gui.compute_layout, views.compute_layout)
        self.assertIs(gui.model_category, views.model_category)


class DependencyDirectionTests(unittest.TestCase):
    """Bağımlılık yönü: gui -> simulation -> agents / environment."""

    def test_core_modules_do_not_use_tkinter(self):
        for module in ("environment", "agents", "simulation", "timers", "views"):
            with self.subTest(module=module):
                self.assertNotIn("import tkinter", source(module))
                self.assertNotIn("from tkinter", source(module))

    def test_core_modules_do_not_import_gui(self):
        for module in ("environment", "agents", "simulation", "views", "timers"):
            with self.subTest(module=module):
                self.assertNotIn("import gui", source(module))
                self.assertNotIn("from gui", source(module))


if __name__ == "__main__":
    unittest.main()
