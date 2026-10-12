"""Ajan karşılaştırmasının ölçüm çekirdeği (arayüzden bağımsız).

Hem komut satırı aracı (``tools/compare_agents.py``) hem de karşılaştırma
penceresi (``compare_window.py``) bu modülü kullanır. Ölçüm yöntemi Faz 4'teki
araçla aynıdır; aynı seed'ler aynı sayıları üretir.

Ölçütler
--------
* **Kapsama adımı:** Kirlenme kapalıyken bütün odaların en az bir kez
  algılandığı adımın numarası. Başlangıç odası 1. adımda algılanır. Adım
  sınırı içinde tamamlanmayan koşu "tamamlanmadı" sayılır; değeri bilinmez,
  yalnızca sınırdan büyük olduğu bilinir (sağdan sansürlü veri).
* **Ortalama temiz oda oranı:** Kirlenme açıkken her adımdan sonra ölçülen
  temiz oda oranlarının ortalaması.
* **Hareket / temizleme oranı:** Aynı koşuda yapılan hareket sayısının
  temizleme sayısına oranı (bir temizlik için kaç hareket yapıldığı). Hiç
  temizlik yapılmayan koşuda tanımsızdır.

Kirlenme biçimleri
------------------
* ``independent`` (bağımsız): Simülasyonun kendi ``dirty_tick``
  mekanizması. Ortam yalnızca temiz odalar için rastgele sayı çektiğinden
  ajanlar farklı hareket edince karşılaştıkları kirlenme olayları ayrışır.
* ``common`` (ortak): Her tetiklemede her oda için ajandan bağımsız bir sayı
  çekilir ve ``Environment.apply_dirt_draws`` ile uygulanır. Bütün ajanlar
  aynı kirlenme denemeleri dizisini görür; ancak kirli bir odaya deneme
  etkisiz kaldığı için gerçekleşen kirlenmeler yine ajanın temizliklerine
  göre farklılaşabilir.
"""

import math
import random
import statistics
from dataclasses import dataclass

from environment import Status
from simulation import Simulation

AGENT_KEYS = ("reflex", "model", "goal")
DIRT_MODES = ("common", "independent")
DEFAULT_PROBABILITY = 0.3
STEP_YIELD_INTERVAL = 50   # parçalı çalışmada her bu kadar adımda bir kontrol geri verilir


# ----------------------------------------------------------------------
# Temel ölçümler (Faz 4 aracıyla aynı imza ve sonuç)
# ----------------------------------------------------------------------
def _quiet_simulation(agent_type, rows, cols, seed, probability):
    sim = Simulation(seed=seed, rows=rows, cols=cols, agent_type=agent_type,
                     dirt_probability=probability, clock=lambda: 0.0)
    sim.start()
    return sim


def common_dirt_rng(seed):
    """Ortak kirlenme denemeleri için ajandan bağımsız üreteç."""
    return random.Random(f"common-dirt-{seed}")


def common_dirt_draws(rng, room_count):
    """Bir tetikleme için her oda adına bir deneme (oda kirli olsa da çekilir)."""
    return [rng.random() for _ in range(room_count)]


def _coverage_run(agent_type, rows, cols, seed, cap):
    """Kapsama koşusu; parçalı çalışma için ara ara None üretir, sonucu döndürür."""
    sim = _quiet_simulation(agent_type, rows, cols, seed, 0.0)
    perceived = set()
    total = rows * cols
    for i in range(cap):
        record = sim.step()
        perceived.add(record.room)
        if len(perceived) == total:
            return record.step
        if i % STEP_YIELD_INTERVAL == STEP_YIELD_INTERVAL - 1:
            yield None
    return None


def _dirt_run(agent_type, rows, cols, seed, steps, dirt_every, probability, mode):
    """Kirlenmeli koşu: (ortalama temiz oran, hareket, temizleme)."""
    if mode not in DIRT_MODES:
        raise ValueError(f"Bilinmeyen kirlenme biçimi: {mode!r}")
    sim = _quiet_simulation(agent_type, rows, cols, seed, probability)
    dirt_rng = common_dirt_rng(seed)
    room_count = rows * cols
    clean_sum = 0
    for i in range(steps):
        sim.step()
        if i % dirt_every == 0:
            if mode == "independent":
                sim.dirty_tick()
            else:
                sim.environment.apply_dirt_draws(common_dirt_draws(dirt_rng, room_count))
        clean_sum += sum(status is Status.CLEAN for status in sim.environment.statuses().values())
        if i % STEP_YIELD_INTERVAL == STEP_YIELD_INTERVAL - 1:
            yield None
    return clean_sum / (steps * room_count), sim.move_count, sim.clean_count


def _run_to_end(generator):
    while True:
        try:
            next(generator)
        except StopIteration as stop:
            return stop.value


def coverage_steps(agent_type, rows, cols, seed, cap=50000):
    """Kirlenme kapalıyken bütün odaların ilk kez algılandığı adım (yoksa None)."""
    return _run_to_end(_coverage_run(agent_type, rows, cols, seed, cap))


def mean_clean_ratio(agent_type, rows, cols, seed, steps=3000, dirt_every=4,
                     probability=DEFAULT_PROBABILITY, mode="independent"):
    """Her adımdan sonra ölçülen temiz oda oranlarının ortalaması."""
    ratio, _moves, _cleans = _run_to_end(
        _dirt_run(agent_type, rows, cols, seed, steps, dirt_every, probability, mode))
    return ratio


def same_initial_state(rows, cols, seed, agent_types=AGENT_KEYS):
    """Aynı seed'in bütün ajanlara aynı başlangıç durumunu verip vermediği."""
    states = []
    for agent_type in agent_types:
        env = Simulation(seed=seed, rows=rows, cols=cols, agent_type=agent_type).environment
        states.append((env.location, env.statuses()))
    return all(state == states[0] for state in states)


# ----------------------------------------------------------------------
# Karşılaştırma ayarları, koşu sonuçları ve özet
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ComparisonSettings:
    rows: int = 4
    cols: int = 4
    seed_start: int = 0
    seed_count: int = 20
    steps: int = 3000           # kirlenmeli koşunun adım sayısı ve kapsama koşusunun adım sınırı
    dirt_every: int = 4         # kirlenme her bu kadar adımda bir tetiklenir
    dirt_mode: str = "common"
    probability: float = DEFAULT_PROBABILITY

    def validate(self):
        """Ayarları denetler; geçersizse Türkçe mesajla ValueError fırlatır."""
        from environment import Grid
        Grid(self.rows, self.cols)
        if self.seed_count < 1:
            raise ValueError("Seed sayısı en az 1 olmalıdır.")
        if self.steps < 1:
            raise ValueError("Adım sayısı en az 1 olmalıdır.")
        if self.dirt_every < 1:
            raise ValueError("Kirlenme sıklığı en az 1 adım olmalıdır.")
        if self.dirt_mode not in DIRT_MODES:
            raise ValueError("Kirlenme biçimi 'ortak' ya da 'bağımsız' olmalıdır.")
        return self

    @property
    def seeds(self):
        return range(self.seed_start, self.seed_start + self.seed_count)


@dataclass(frozen=True)
class RunResult:
    agent_type: str
    seed: int
    coverage_step: object    # int ya da None (sınır içinde tamamlanmadı)
    clean_ratio: float
    moves: int
    cleans: int

    @property
    def moves_per_clean(self):
        """Hareket / temizleme; hiç temizlik yoksa None (tanımsız)."""
        return None if self.cleans == 0 else self.moves / self.cleans


def run_pair(agent_type, seed, settings):
    """Bir (ajan, seed) için kapsama ve kirlenmeli koşu; parçalı çalışma üreteci."""
    coverage = yield from _coverage_run(agent_type, settings.rows, settings.cols, seed, settings.steps)
    ratio, moves, cleans = yield from _dirt_run(
        agent_type, settings.rows, settings.cols, seed, settings.steps,
        settings.dirt_every, settings.probability, settings.dirt_mode)
    return RunResult(agent_type, seed, coverage, ratio, moves, cleans)


@dataclass(frozen=True)
class CoverageSummary:
    """Kapsama adımlarının özeti.

    Tamamlanmayan koşuların değeri bilinmez (sınırdan büyüktür). Bu yüzden:

    * ``mean`` yalnızca bütün koşular tamamlandıysa verilir; aksi halde
      ``mean_lower_bound`` (tamamlanmayanlar sınır kabul edilerek) bir alt
      sınırdır.
    * ``median`` tamamlanmayanlar sonsuz kabul edilerek hesaplanır; ortanca
      tamamlanmayan bölgeye düşerse ``None`` olur ("sınırdan büyük").
    * ``worst`` herhangi bir koşu tamamlanmadıysa ``None`` olur.
    """

    completed: int
    incomplete: int
    cap: int
    mean: object
    mean_lower_bound: object
    median: object
    worst: object


@dataclass(frozen=True)
class AgentSummary:
    agent_type: str
    runs: int
    coverage: CoverageSummary
    clean_ratio_mean: float
    clean_ratio_stdev: object        # tek koşuda None
    moves_per_clean_mean: object     # hiçbir koşuda tanımlı değilse None
    moves_per_clean_undefined: int   # sıfır temizlikli koşu sayısı


def summarize_coverage(values, cap):
    completed = sorted(v for v in values if v is not None)
    incomplete = len(values) - len(completed)
    capped = completed + [cap] * incomplete
    with_infinity = completed + [math.inf] * incomplete
    median = statistics.median(with_infinity)
    return CoverageSummary(
        completed=len(completed),
        incomplete=incomplete,
        cap=cap,
        mean=statistics.mean(completed) if incomplete == 0 else None,
        mean_lower_bound=statistics.mean(capped) if incomplete else None,
        median=None if math.isinf(median) else median,
        worst=max(completed) if incomplete == 0 else None,
    )


def summarize(results, settings):
    """Koşu sonuçlarını ajan başına özetler (AGENT_KEYS sırasıyla)."""
    summaries = []
    for agent_type in AGENT_KEYS:
        runs = [r for r in results if r.agent_type == agent_type]
        if not runs:
            continue
        ratios = [r.clean_ratio for r in runs]
        per_clean = [r.moves_per_clean for r in runs if r.moves_per_clean is not None]
        summaries.append(AgentSummary(
            agent_type=agent_type,
            runs=len(runs),
            coverage=summarize_coverage([r.coverage_step for r in runs], settings.steps),
            clean_ratio_mean=statistics.mean(ratios),
            clean_ratio_stdev=statistics.stdev(ratios) if len(ratios) > 1 else None,
            moves_per_clean_mean=statistics.mean(per_clean) if per_clean else None,
            moves_per_clean_undefined=len(runs) - len(per_clean),
        ))
    return summaries


class ComparisonJob:
    """Üç ajanın karşılaştırmasını parça parça yürüten iş (arayüzden bağımsız).

    ``advance(budget_seconds)`` bütçe dolana kadar ilerler ve iş bittiyse True
    döndürür. İptal edilen iş özet üretmez; kısmi sonuçlar tamamlanmış sonuç
    olarak sunulmaz.
    """

    def __init__(self, settings, agent_types=AGENT_KEYS, clock=None):
        import time
        self.settings = settings.validate()
        self.agent_types = tuple(agent_types)
        self._clock = clock or time.perf_counter
        self._pairs = [(a, s) for s in settings.seeds for a in self.agent_types]
        self._index = 0
        self._current = None
        self.results = []
        self.cancelled = False
        self.longest_slice = 0.0     # en uzun advance çağrısının süresi (saniye)
        if not all(same_initial_state(settings.rows, settings.cols, s, self.agent_types)
                   for s in settings.seeds):
            raise RuntimeError("Ajanlar aynı başlangıç durumunu almıyor.")

    @property
    def total(self):
        return len(self._pairs)

    @property
    def done(self):
        return len(self.results)

    @property
    def finished(self):
        return not self.cancelled and self.done == self.total

    def cancel(self):
        self.cancelled = True
        self._current = None

    def advance(self, budget_seconds=0.015):
        if self.cancelled:
            return False
        start = self._clock()
        while self._index < len(self._pairs) or self._current is not None:
            if self._current is None:
                agent_type, seed = self._pairs[self._index]
                self._index += 1
                self._current = run_pair(agent_type, seed, self.settings)
            try:
                next(self._current)
            except StopIteration as stop:
                self.results.append(stop.value)
                self._current = None
            if self._clock() - start >= budget_seconds:
                break
        self.longest_slice = max(self.longest_slice, self._clock() - start)
        return self.finished

    def summary(self):
        """Yalnızca tamamlanmış iş için özet; aksi halde None."""
        if not self.finished:
            return None
        return summarize(self.results, self.settings)
