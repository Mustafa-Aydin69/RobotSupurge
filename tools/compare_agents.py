"""Refleks, model tabanlı ve amaç tabanlı ajanların ölçümle karşılaştırılması.

Çalıştırma (proje kök dizininden):
    python -m tools.compare_agents
    python -m tools.compare_agents --seeds 20

Bu betik arayüz içermez ve uygulamanın parçası değildir; yalnızca ölçüm
içindir. Ölçümler seed'lidir ve her çalıştırmada aynı sonucu üretir.

Ölçüm 1 — Kapsama adımı (kirlenme kapalı)
    Simülasyonun her adımında ajan bulunduğu odayı algılar; başlangıç odası
    1. adımda algılanır. Kapsama adımı, bütün odaların en az bir kez
    algılandığı adımın numarasıdır. Kirlenme kapalı olduğu için aynı seed iki
    ajana birebir aynı başlangıç durumunu verir.

Ölçüm 2 — Ortalama temiz oda oranı (kirlenme açık)
    Her adımdan sonra temiz oda oranı ölçülür ve bütün adımların ortalaması
    alınır. Kirlenme her ``dirt_every`` adımda bir tetiklenir. İki üretim
    biçimi vardır:


    * ``independent``: Simülasyonun kendi ``dirty_tick`` mekanizması. Ortam,
      yalnızca temiz odalar için rastgele sayı çeker. Ajanlar farklı hareket
      ettiği için temiz oda kümeleri ayrışır; aynı seed kullanılsa bile
      ajanların karşılaştığı kirlenme olayları aynı olmaz.
    * ``common`` (ortak rastgele sayılar): Her tetiklemede her oda için ajandan
      bağımsız bir sayı çekilir; oda temizse ve sayı olasılıktan küçükse
      kirlenir. Böylece bütün ajanlar aynı "kirlenme denemeleri" dizisiyle
      karşılaşır. Bir oda zaten kirliyse deneme etkisiz kalır; yani ortaya
      çıkan kirlenme olayları yine ajanın davranışına bağlıdır, ama rastgelelik
      kaynağı ortaktır.
"""

import argparse
import random
import statistics
import sys

from environment import Status
from simulation import Simulation

AGENT_KEYS = ("reflex", "model", "goal")
AGENT_LABELS = {"reflex": "refleks", "model": "model", "goal": "amaç"}
COVERAGE_GRIDS = [(1, 6), (3, 3), (4, 4), (3, 5), (6, 6)]
CLEAN_RATIO_GRIDS = [(1, 2), (3, 3), (4, 4), (6, 6)]


def coverage_steps(agent_type, rows, cols, seed, cap=50000):
    """Kirlenme kapalıyken bütün odaların ilk kez algılandığı adım (yoksa None)."""
    sim = Simulation(seed=seed, rows=rows, cols=cols, agent_type=agent_type,
                     dirt_probability=0.0, clock=lambda: 0.0)
    sim.start()
    perceived = set()
    total = rows * cols
    for _ in range(cap):
        record = sim.step()
        perceived.add(record.room)
        if len(perceived) == total:
            return record.step
    return None


def common_dirt_rng(seed):
    """Ortak kirlenme denemeleri için ajandan bağımsız üreteç."""
    return random.Random(f"common-dirt-{seed}")


def apply_common_dirt(environment, rng, probability):
    """Her oda için bir sayı çeker; temiz odayı olasılıkla kirletir.

    Not: Ortamın herkese açık bir "odayı kirlet" metodu yoktur; bu ölçüm aracı
    ortak rastgele sayıları uygulayabilmek için ortamın iç durumuna yazar.
    Uygulamanın kendisi bu fonksiyonu kullanmaz.
    """
    newly_dirty = []
    for room in environment.rooms:
        draw = rng.random()  # oda kirli olsa da çekilir: dizi ajandan bağımsız kalır
        if environment.status_of(room) is Status.CLEAN and draw < probability:
            environment._statuses[room] = Status.DIRTY
            newly_dirty.append(room)
    return newly_dirty


def mean_clean_ratio(agent_type, rows, cols, seed, steps=3000, dirt_every=4,
                     probability=0.3, mode="independent"):
    """Her adımdan sonra ölçülen temiz oda oranlarının ortalaması."""
    if mode not in ("independent", "common"):
        raise ValueError(f"Bilinmeyen kirlenme biçimi: {mode!r}")
    sim = Simulation(seed=seed, rows=rows, cols=cols, agent_type=agent_type,
                     dirt_probability=probability, clock=lambda: 0.0)
    sim.start()
    dirt_rng = common_dirt_rng(seed)
    total_rooms = rows * cols
    clean_sum = 0
    for i in range(steps):
        sim.step()
        if i % dirt_every == 0:
            if mode == "independent":
                sim.dirty_tick()
            else:
                apply_common_dirt(sim.environment, dirt_rng, probability)
        clean_sum += sum(status is Status.CLEAN for status in sim.environment.statuses().values())
    return clean_sum / (steps * total_rooms)


def same_initial_state(rows, cols, seed):
    """Aynı seed'in bütün ajanlara aynı başlangıç durumunu verip vermediği."""
    states = []
    for agent_type in AGENT_KEYS:
        env = Simulation(seed=seed, rows=rows, cols=cols, agent_type=agent_type).environment
        states.append((env.location, env.statuses()))
    return all(state == states[0] for state in states)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ajan türlerinin ölçümle karşılaştırılması")
    parser.add_argument("--seeds", type=int, default=50, help="kapsama ölçümü için seed sayısı")
    parser.add_argument("--ratio-seeds", type=int, default=20, help="temiz oran ölçümü için seed sayısı")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # Windows konsolunda Türkçe karakterler için

    seeds = range(args.seeds)
    print(f"Kapsama adımı: ortalama / medyan / en kötü (kirlenme kapalı, seed 0..{args.seeds - 1})")
    print(f"{'grid':6}" + "".join(f" | {AGENT_LABELS[key]:>20}" for key in AGENT_KEYS))
    for rows, cols in COVERAGE_GRIDS:
        assert all(same_initial_state(rows, cols, s) for s in seeds)
        cells = []
        for agent_type in AGENT_KEYS:
            values = [coverage_steps(agent_type, rows, cols, s) for s in seeds]
            if None in values:
                cells.append("sınıra ulaşıldı")
                continue
            cells.append(f"{statistics.mean(values):.1f} / {statistics.median(values):.1f} / {max(values)}")
        print(f"{rows}x{cols:<4}" + "".join(f" | {cell:>20}" for cell in cells))

    ratio_seeds = range(args.ratio_seeds)
    print()
    print(f"Ortalama temiz oda oranı (3000 adım, her 4 adımda %30 kirlenme, seed 0..{args.ratio_seeds - 1})")
    header = "".join(f" {AGENT_LABELS[key]:>8}" for key in AGENT_KEYS)
    print(f"{'grid':6} | bağımsız:{header} | ortak:{header}")
    for rows, cols in CLEAN_RATIO_GRIDS:
        cells = {}
        for mode in ("independent", "common"):
            cells[mode] = "".join(
                f" {statistics.mean(mean_clean_ratio(t, rows, cols, s, mode=mode) for s in ratio_seeds):8.3f}"
                for t in AGENT_KEYS
            )
        print(f"{rows}x{cols:<4} | {'':9}{cells['independent']} | {'':6}{cells['common']}")


if __name__ == "__main__":
    main()
