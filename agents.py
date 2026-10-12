"""Robot süpürge ajanları.

Her ajan aynı arayüzü uygular:

* ``act(percept) -> Action``: güncel algıya göre tam olarak bir eylem seçer.
* ``action_result(action, succeeded)``: ortam eylemi uyguladıktan sonra
  simülasyon tarafından çağrılır ve eylemin başarılı olup olmadığını bildirir.
  Ajan bu bildirimi iç modelini güncellemek için kullanabilir; ortamın durumu
  hakkında başka hiçbir bilgi içermez.

Bu modül grafik arayüzden tamamen bağımsızdır.
"""

import random
from dataclasses import dataclass
from types import MappingProxyType

from environment import Action, Grid, Status


class ReflexAgent:
    """Basit refleks ajan (simple-reflex agent).

    Kararını yalnızca o anki algıya, yani bulunduğu oda ve o odanın temiz/kirli
    durumuna göre verir. Geçmiş algılar, önceki eylemler, ziyaret edilen odalar
    ve log kayıtları karar vermede kullanılmaz.

    1×2 ortamda karar tablosu (ödev tanımındaki tablonun birebir karşılığı):

        A odası, kirli  -> Temizle
        A odası, temiz  -> Sağa git
        B odası, kirli  -> Temizle
        B odası, temiz  -> Sola git

    Diğer grid'lerde: oda kirliyse Temizle; temizse bulunulan odadan sınırlar
    içinde kalan hareketlerden rastgele biri.

    Ajan iki şey tutar ve ikisi de algı belleği değildir:

    * ``grid``: ortamın değişmez yerleşimi (yapılandırma bilgisi),
    * ``rng``: rastgele sayı üreteci. Seçimi rastgele yapmanın aracıdır; hangi
      algıların görüldüğünü saklamaz ve olası seçimleri değiştirmez.
    """

    name = "Basit Refleks Ajan"

    # 1×2 ortamın hareket kuralı: temiz odada gidilecek yön yalnızca odaya bağlıdır.
    MOVE_RULES = {"A": Action.RIGHT, "B": Action.LEFT}

    # Yalnızca bu iki yapılandırma alanına izin verilir; geçmiş tutacak yeni bir
    # öznitelik eklenemez.
    __slots__ = ("_grid", "_rng")

    def __init__(self, grid=None, rng=None):
        self._grid = grid if grid is not None else Grid()
        self._rng = rng if rng is not None else random.Random()

    @property
    def grid(self):
        return self._grid

    def act(self, percept):
        location, status = percept
        if status is Status.DIRTY:
            return self.clean_rule()
        return self.move_rule(location)

    def action_result(self, action, succeeded):
        """Refleks ajan eylem sonucunu kullanmaz; hiçbir şey saklamaz."""

    @staticmethod
    def clean_rule():
        """Temizleme kuralı: bulunulan oda kirliyse temizle."""
        return Action.CLEAN

    def move_rule(self, location):
        """Hareket kuralı: bulunulan oda temizse başka bir odaya geç.

        1×2'de ödev tablosu uygulanır. Diğer grid'lerde yalnızca bulunulan
        odaya göre geçerli olan hareketlerden biri rastgele seçilir.
        """
        if self._grid.is_two_room:
            return self.MOVE_RULES[location]
        return self._rng.choice(self._grid.valid_moves(location))


# Bilginin kaynağı
SOURCE_PERCEPT = "algı"       # ajan odayı bizzat algıladı
SOURCE_INFERENCE = "çıkarım"  # ajan kendi başarılı eyleminden sonucu çıkardı


@dataclass(frozen=True)
class Observation:
    """İç modeldeki bir odanın son bilinen durumu."""

    status: Status
    step: int      # bilginin ait olduğu ajan adımı
    source: str    # SOURCE_PERCEPT ya da SOURCE_INFERENCE


@dataclass(frozen=True)
class ModelSnapshot:
    """İç modelin salt okunur kopyası (arayüz ve testler için).

    ``observations`` değiştirilemez bir eşlemedir; içindeki ``Observation``
    nesneleri de değiştirilemez. Kopya üzerinde yapılan hiçbir işlem ajanın
    belleğini etkilemez.
    """

    step: int
    location: str
    observations: MappingProxyType

    def age_of(self, room):
        """Odanın son bilgisinden bu yana geçen ajan adımı; bilinmiyorsa None."""
        observation = self.observations.get(room)
        return None if observation is None else self.step - observation.step


class ModelBasedAgent:
    """Model tabanlı ajan (model-based reflex agent).

    Algılarından bir iç model kurar: her oda için son bilinen durum, bu
    bilginin ait olduğu adım ve bilginin kaynağı. Hiç algılanmamış odalar
    modelde yer almaz, yani bilinmiyor kabul edilir.

    Ajan ortamın tamamını göremez. Model yalnızca iki yoldan güncellenir:

    * ``act`` içinde güncel algı modele yazılır (güncel algı her zaman eski
      bilginin önüne geçer),
    * ``action_result`` ile başarılı olduğu bildirilen Temizle eyleminden sonra
      oda "temiz (çıkarım)" olarak kaydedilir. Bir sonraki algı bu çıkarımı
      doğrular ya da düzeltir.

    Gözlem yaşı ajanın kendi adım sayısıyla ölçülür; gerçek süre ya da kesin
    bir kirlenme olasılığı değildir.
    """

    name = "Model Tabanlı Ajan"

    __slots__ = ("_grid", "_rng", "_memory", "_step", "_location", "_pending")

    def __init__(self, grid=None, rng=None):
        self._grid = grid if grid is not None else Grid()
        self._rng = rng if rng is not None else random.Random()
        self._memory = {}       # oda -> Observation
        self._step = 0          # ajanın aldığı algı sayısı
        self._location = None   # son algıdaki oda
        self._pending = None    # sonucu beklenen eylem: (oda, eylem)

    @property
    def grid(self):
        return self._grid

    # ------------------------------------------------------------------
    # Ajan arayüzü
    # ------------------------------------------------------------------
    def act(self, percept):
        self.update_model(percept)
        location, status = percept
        if status is Status.DIRTY:
            action = self.clean_rule()
        else:
            action = self.move_rule(location)
        self._pending = (location, action)
        return action

    def action_result(self, action, succeeded):
        """Eylem sonucunu modele işler.

        Yalnızca başarılı bir Temizle eyleminden sonra oda "temiz (çıkarım)"
        olarak kaydedilir. Başarısız eylemden hiçbir çıkarım yapılmaz.
        """
        pending, self._pending = self._pending, None
        if pending is None or pending[1] is not action or not succeeded:
            return
        room, _ = pending
        if action is Action.CLEAN:
            self._memory[room] = Observation(Status.CLEAN, self._step, SOURCE_INFERENCE)

    # ------------------------------------------------------------------
    # Model güncelleme
    # ------------------------------------------------------------------
    def update_model(self, percept):
        """Güncel algıyı modele yazar ve ajan adım sayacını artırır."""
        location, status = percept
        self._grid.position_of(location)  # bilinmeyen oda adı reddedilir
        self._step += 1
        self._location = location
        self._memory[location] = Observation(status, self._step, SOURCE_PERCEPT)

    def model_snapshot(self):
        """İç modelin salt okunur bir kopyası."""
        return ModelSnapshot(self._step, self._location, MappingProxyType(dict(self._memory)))

    # ------------------------------------------------------------------
    # Kurallar
    # ------------------------------------------------------------------
    @staticmethod
    def clean_rule():
        """Temizleme kuralı: bulunulan oda kirliyse temizle."""
        return Action.CLEAN

    def move_rule(self, location):
        """Hareket kuralı: modele göre en çok bakılması gereken komşuya git.

        1. Hiç algılanmamış (bilinmeyen) komşular önceliklidir.
        2. Bütün komşular biliniyorsa son bilgisi en eski olan komşu seçilir.
        3. Eşitlikte adaylardan biri seed'li rng ile rastgele seçilir.

        Yalnızca bulunulan odadan geçerli olan hareketler değerlendirilir.
        """
        moves = self._grid.valid_moves(location)
        priorities = {move: self.neighbor_priority(self._grid.neighbor(location, move)) for move in moves}
        best = max(priorities.values())
        candidates = [move for move in moves if priorities[move] == best]
        return self._rng.choice(candidates)

    def neighbor_priority(self, room):
        """Bir komşunun önceliği: (bilinmiyor mu, gözlem yaşı).

        Bilinmeyen oda her bilinen odadan önce gelir; bilinen odalar arasında
        yaşı büyük olan öne geçer.
        """
        observation = self._memory.get(room)
        if observation is None:
            return (1, 0)
        return (0, self._step - observation.step)
