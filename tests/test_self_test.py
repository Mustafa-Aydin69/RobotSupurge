"""--self-test doğrulaması ve main.py komut satırı testleri."""

import io
import os
import tempfile
import unittest
from unittest import mock

import main
import self_test


class SelfTestTests(unittest.TestCase):
    def test_all_checks_pass_and_exit_code_is_zero(self):
        with mock.patch("sys.stdout", None):          # pencereli EXE gibi: stdout yok
            self.assertEqual(self_test.run_self_test(), 0)

    def test_failure_gives_exit_code_one(self):
        def broken():
            raise AssertionError("bilerek bozuldu")

        with mock.patch.object(self_test, "CHECKS", self_test.CHECKS + [broken]), \
                mock.patch("sys.stdout", None):
            self.assertEqual(self_test.run_self_test(), 1)

    def test_report_file_is_written(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "rapor.txt")
            with mock.patch("sys.stdout", None):
                self_test.run_self_test(path)
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        self.assertIn("Sonuç: 9/9 kontrol başarılı.", text)
        self.assertEqual(text.count("[TAMAM]"), 9)


    def test_result_is_printed_even_if_console_lacks_turkish_letters(self):
        """Çıktı kodlaması Türkçe harfleri desteklemese de sonuç satırı yazılır."""
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="cp1252")
        with mock.patch("sys.stdout", stream):
            self.assertEqual(self_test.run_self_test(), 0)
        stream.flush()
        output = buffer.getvalue().decode("cp1252")
        self.assertIn("9/9 kontrol ba?ar?l?.", output)


class MainArgumentTests(unittest.TestCase):
    def test_self_test_does_not_open_gui(self):
        with mock.patch("gui.run") as gui_run, mock.patch("sys.stdout", None):
            self.assertEqual(main.main(["--self-test"]), 0)
        gui_run.assert_not_called()

    def test_without_arguments_gui_is_started(self):
        with mock.patch("gui.run") as gui_run:
            self.assertEqual(main.main([]), 0)
        gui_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
