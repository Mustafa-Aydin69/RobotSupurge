"""Simülasyon yönetimi: algı-karar-eylem döngüsü, kirlenme, durum ve günlük.

Bu modül zamanlayıcı içermez ve grafik arayüzden tamamen bağımsızdır. İki
bağımsız giriş noktası sunar:

* ``step()``: tek bir algı-karar-eylem döngüsü yürütür.
* ``dirty_tick()``: ortamın otomatik kirlenmesini bir kez tetikler.

İkisi de birbirini çağırmaz. Hangi aralıkla çağrılacaklarına dışarıdaki
zamanlayıcılar (arayüz) ya da testler karar verir. Böylece kirlenme, ajanın
adımlarından bağımsız çalışır.
"""

import random
import time
from dataclasses import dataclass
from enum import Enum

from agents import ReflexAgent
from environment import DEFAULT_DIRT_PROBABILITY, Action, Environment, Status


class SimulationState(Enum):
    READY = "Hazır"
    RUNNING = "Çalışıyor"
    PAUSED = "Duraklatıldı"
    STOPPED = "Durduruldu"


@dataclass(frozen=True)
class StepRecord:
    """Bir ajan adımının günlük kaydı (algı ve eylem)."""

    step: int
    elapsed: float
    room: str
    status: Status
    action: Action


@dataclass(frozen=True)
class DirtRecord:
    """Bir kirlenme olayının günlük kaydı. Ajan adım sayısını artırmaz."""

    elapsed: float
    rooms: tuple


class Simulation:
    """Ortamı, ajanı ve günlüğü bir arada yöneten simülasyon.

    ``seed`` verilirse ortamın başlangıcı ve kirlenmeler her seferinde aynı
    şekilde üretilir. ``rows`` ve ``cols`` grid boyutudur (varsayılan 1×2).
    ``location`` ve ``statuses`` verilirse başlangıç durumu rastgele seçilmez.
    ``clock`` testlerde sahte bir saat vermek içindir.
    """

    def __init__(
        self,
        seed=None,
        dirt_probability=DEFAULT_DIRT_PROBABILITY,
        location=None,
        statuses=None,
        clock=time.monotonic,
        rows=1,
        cols=2,
    ):
        self.seed = seed
        master_rng = random.Random(seed)
        # Ortamın üreteci ilk olarak türetilir; böylece 1×2'de aynı seed,
        # Faz 1 ile birebir aynı başlangıcı ve kirlenme dizisini üretir.
        self.environment = Environment(
            rng=random.Random(master_rng.getrandbits(64)),
            dirt_probability=dirt_probability,
            location=location,
            statuses=statuses,
            rows=rows,
            cols=cols,
        )
        self.agent = ReflexAgent(
            grid=self.environment.grid,
            rng=random.Random(master_rng.getrandbits(64)),
        )

        self.state = SimulationState.READY
        self.log = []
        self.step_count = 0
        self.clean_count = 0
        self.move_count = 0

        self._clock = clock
        self._started_at = None
        self._paused_at = None
        self._paused_total = 0.0
        self._stopped_elapsed = None

    # ------------------------------------------------------------------
    # Yaşam döngüsü
    # ------------------------------------------------------------------
    def start(self):
        self._require(SimulationState.READY)
        self._started_at = self._clock()
        self.state = SimulationState.RUNNING

    def pause(self):
        """Durumu korur; duraklama süresi geçen süreye eklenmez."""
        self._require(SimulationState.RUNNING)
        self._paused_at = self._clock()
        self.state = SimulationState.PAUSED

    def resume(self):
        """Duraklatıldığı andaki durumdan devam eder."""
        self._require(SimulationState.PAUSED)
        self._paused_total += self._clock() - self._paused_at
        self._paused_at = None
        self.state = SimulationState.RUNNING

    def stop(self):
        """Simülasyonu sonlandırır. Günlük ve son durum okunabilir kalır."""
        if self.state is SimulationState.STOPPED:
            return
        self._stopped_elapsed = self.elapsed
        self.state = SimulationState.STOPPED

    @property
    def is_running(self):
        return self.state is SimulationState.RUNNING

    @property
    def elapsed(self):
        """Başlangıçtan bu yana geçen süre (saniye), duraklamalar hariç."""
        if self._stopped_elapsed is not None:
            return self._stopped_elapsed
        if self._started_at is None:
            return 0.0
        now = self._paused_at if self._paused_at is not None else self._clock()
        return now - self._started_at - self._paused_total

    # ------------------------------------------------------------------
    # Algı-karar-eylem döngüsü
    # ------------------------------------------------------------------
    def step(self):
        """Tek döngü: algıla, karar ver, tek bir eylem uygula, sonucu bildir, kaydet.

        Eylemin sonucu ajana ``action_result`` ile bildirilir. Ortam eylemi
        uygulayamazsa (``ValueError``) ajana başarısız olduğu bildirilir ve hata
        yükseltilir; adım sayılmaz ve günlüğe yazılmaz.
        """
        self._require(SimulationState.RUNNING)

        percept = self.environment.percept()   # algı
        action = self.agent.act(percept)       # karar
        try:
            self.environment.execute(action)   # eylem
        except ValueError:
            self.agent.action_result(action, succeeded=False)
            raise
        self.agent.action_result(action, succeeded=True)

        self.step_count += 1
        if action is Action.CLEAN:
            self.clean_count += 1
        else:
            self.move_count += 1

        room, status = percept
        record = StepRecord(self.step_count, self.elapsed, room, status, action)
        self.log.append(record)
        return record

    # ------------------------------------------------------------------
    # Otomatik kirlenme
    # ------------------------------------------------------------------
    def dirty_tick(self):
        """Kirlenmeyi bir kez tetikler.

        En az bir oda kirlendiyse kaydı günlüğe ekleyip döndürür, aksi halde
        ``None`` döner. Ajan adım sayısı değişmez.
        """
        self._require(SimulationState.RUNNING)
        rooms = self.environment.dirty_tick()
        if not rooms:
            return None
        record = DirtRecord(self.elapsed, tuple(rooms))
        self.log.append(record)
        return record

    # ------------------------------------------------------------------
    def _require(self, *states):
        if self.state not in states:
            raise RuntimeError(
                f"Bu işlem '{self.state.value}' durumunda yapılamaz."
            )
