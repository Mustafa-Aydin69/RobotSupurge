"""LMS teslim listesinin eksiksizliği.

LMS'ye yalnızca kaynak kod dosyaları yüklenir. Bu testler, listelenen
dosyaların programın ihtiyaç duyduğu bütün proje modüllerini içerdiğini ve
yalnızca bu dosyalarla programın çalıştığını doğrular.
"""

import ast
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SUBMISSION_FILES = [
    "main.py", "environment.py", "agents.py", "simulation.py", "comparison.py",
    "gui.py", "views.py", "theme.py", "timers.py", "compare_window.py", "self_test.py",
    "welcome_assets.py",
]


def local_imports(path):
    """Bir kaynak dosyanın import ettiği proje modülleri (iç içe import'lar dahil)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return {name for name in names if (ROOT / f"{name}.py").exists()}


class SubmissionTests(unittest.TestCase):
    def test_all_listed_files_exist(self):
        for name in SUBMISSION_FILES:
            self.assertTrue((ROOT / name).is_file(), name)

    def test_list_is_closed_under_imports(self):
        """main.py'den ulaşılabilen bütün proje modülleri listede."""
        needed, queue = set(), ["main"]
        while queue:
            module = queue.pop()
            if module in needed:
                continue
            needed.add(module)
            queue.extend(local_imports(ROOT / f"{module}.py"))
        self.assertEqual({f"{m}.py" for m in needed}, set(SUBMISSION_FILES))

    def test_readme_lists_the_same_files(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        section = readme.split("## LMS teslimi", 1)[1].split("##", 1)[0]
        for name in SUBMISSION_FILES:
            self.assertIn(name, section)

    def test_main_header_lists_the_same_files(self):
        header = (ROOT / "main.py").read_text(encoding="utf-8").split('"""', 1)[0]
        for name in SUBMISSION_FILES:
            self.assertIn(name, header)
        self.assertIn("python main.py", header)

    def test_program_runs_from_submission_files_only(self):
        """Yalnızca teslim dosyalarının bulunduğu boş bir klasörde --self-test başarılı."""
        with tempfile.TemporaryDirectory() as folder:
            for name in SUBMISSION_FILES:
                shutil.copy(ROOT / name, folder)
            # Proje klasörü erişilemez olsun: PYTHONPATH temizlenir, yalnızca geçici klasör kullanılır.
            env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
            result = subprocess.run([sys.executable, "main.py", "--self-test"], cwd=folder, env=env,
                                    capture_output=True, timeout=120)
        output = (result.stdout + result.stderr).decode("utf-8", "replace")
        self.assertEqual(result.returncode, 0, output)


if __name__ == "__main__":
    unittest.main()
