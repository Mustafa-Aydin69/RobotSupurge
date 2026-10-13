"""Grafik arayüz açmadan çalışan doğrulama testi (``main.py --self-test``).

EXE'nin Python kurulu olmayan bir bilgisayarda doğru paketlendiğini
doğrulamak için birkaç deterministik simülasyon çalıştırır ve sonucu çıkış
koduyla bildirir: 0 = başarılı, 1 = başarısız. Algoritmaları değiştirmez;
yalnızca mevcut sınıfları çağırır.

Pencereli (konsolsuz) EXE'de ekrana yazı basılamadığı için sonuçlar
``--report DOSYA`` ile bir dosyaya da yazılabilir.
"""

import random
import sys

from agents import AGENT_TYPES, ReflexAgent, shortest_path
from comparison import ComparisonJob, ComparisonSettings
from environment import Action, Environment, Grid, Status
from simulation import Simulation, StepRecord


def _check_reflex_table():
    agent = ReflexAgent()
    expected = {("A", Status.DIRTY): Action.CLEAN, ("A", Status.CLEAN): Action.RIGHT,
                ("B", Status.DIRTY): Action.CLEAN, ("B", Status.CLEAN): Action.LEFT}
    for percept, action in expected.items():
        assert agent.act(percept) is action, f"{percept} -> {agent.act(percept)}"
    return "1×2 refleks karar tablosu (4 kural)"


def _check_two_room_simulation():
    def run():
        sim = Simulation(seed=3, clock=lambda: 0.0)
        sim.start()
        for i in range(200):
            record = sim.step()
            if record.status is Status.DIRTY:
                assert record.action is Action.CLEAN
            else:
                assert record.action is (Action.RIGHT if record.room == "A" else Action.LEFT)
            if i % 3 == 0:
                sim.dirty_tick()
        assert sim.step_count == 200 and sim.clean_count + sim.move_count == 200
        return [(r.step, r.room, r.status, r.action) for r in sim.log if isinstance(r, StepRecord)]
    assert run() == run(), "Aynı seed aynı koşuyu vermedi"
    return "1×2 simülasyon: tek eylem, kirlenme ve seed tekrarı"


def _check_agents_on_grid():
    for agent_type in AGENT_TYPES:
        sim = Simulation(seed=11, rows=4, cols=5, agent_type=agent_type, clock=lambda: 0.0)
        sim.start()
        rooms = set(sim.environment.rooms)
        for i in range(1000):
            sim.step()                      # sınır dışı hareket ValueError fırlatır
            assert sim.environment.location in rooms
            if i % 4 == 0:
                sim.dirty_tick()
        assert sim.step_count == 1000
    return f"{len(AGENT_TYPES)} ajan türü, 4×5 grid, 1000'er adım"


def _check_bfs():
    grid = Grid(6, 6)
    for start, goal in [("A1", "F6"), ("C3", "A6"), ("F1", "B4")]:
        (r1, c1), (r2, c2) = grid.position_of(start), grid.position_of(goal)
        assert len(shortest_path(grid, start, goal)) == abs(r1 - r2) + abs(c1 - c2)
    return "BFS en kısa rota"


def _check_environment_bounds():
    env = Environment(rng=random.Random(0), rows=2, cols=2, location="A1",
                      statuses={r: Status.CLEAN for r in ("A1", "A2", "B1", "B2")})
    try:
        env.move(Action.UP)
    except ValueError:
        pass
    else:
        raise AssertionError("Sınır dışı hareket reddedilmedi")
    assert env.location == "A1"
    return "ortam sınır kontrolü"


def _check_comparison():
    job = ComparisonJob(ComparisonSettings(rows=3, cols=3, seed_count=2, steps=200))
    while not job.advance(0.05):
        pass
    assert len(job.summary()) == 3
    return "karşılaştırma çekirdeği (3 ajan × 2 seed)"


def _check_tkinter_available():
    """Tkinter ve Tcl/Tk kitaplıkları paketlenmiş mi? (Pencere açmaz.)"""
    import tkinter
    interpreter = tkinter.Tcl()
    version = interpreter.eval("info patchlevel")
    return f"Tkinter/Tcl {version} kullanılabilir"


def _check_theme():
    """Arayüz teması yüklenebiliyor mu? (Pencere açmaz; kullanılan temayı bildirir.)"""
    import theme
    return f"Arayüz teması: {theme.theme_description()}"


CHECKS = [
    _check_reflex_table,
    _check_two_room_simulation,
    _check_agents_on_grid,
    _check_bfs,
    _check_environment_bounds,
    _check_comparison,
    _check_tkinter_available,
    _check_theme,
]


def run_self_test(report_path=None):
    """Bütün kontrolleri çalıştırır; başarılıysa 0, değilse 1 döndürür."""
    lines, failed = [], 0
    for check in CHECKS:
        try:
            lines.append(f"[TAMAM] {check()}")
        except Exception as exc:  # noqa: BLE001  (her hata raporlanmalı)
            failed += 1
            lines.append(f"[HATA]  {check.__name__}: {type(exc).__name__}: {exc}")
    lines.append(f"Sonuç: {len(CHECKS) - failed}/{len(CHECKS)} kontrol başarılı.")
    text = "\n".join(lines) + "\n"
    if report_path:
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(text)
    if sys.stdout is not None:      # pencereli EXE'de stdout yoktur
        _write_console(text)
    return 0 if failed == 0 else 1


def _write_console(text):
    """Metni konsola yazar; kodlamada olmayan harfler (ör. ğ, ş) "?" olarak yazılır.

    Çıktı Türkçe harfleri desteklemeyen bir kodlamaya yönlendirildiğinde
    sonucun tamamen kaybolmaması içindir.
    """
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        try:
            sys.stdout.write(text.encode(encoding, "replace").decode(encoding))
        except (OSError, LookupError, UnicodeError):
            pass
    except OSError:
        pass
