"""Robot süpürgenin içinde çalıştığı ortam.

Ortam, yan yana duran iki odadan (A ve B) oluşur. Her oda temiz veya kirli
olabilir. Ortam üç ayrı kural grubunu birbirinden bağımsız olarak yönetir:

* Algılama: ajan yalnızca bulunduğu odayı ve o odanın durumunu algılar.
* Temizleme: ajan yalnızca bulunduğu odayı temizleyebilir.
* Hareket: ajan yalnızca komşu odaya geçebilir, sınır dışına çıkamaz.

Bu modül grafik arayüzden tamamen bağımsızdır.
"""

import random
from enum import Enum


class Status(Enum):
    """Bir odanın temizlik durumu."""

    CLEAN = "Clean"
    DIRTY = "Dirty"


class Action(Enum):
    """Ajanın gerçekleştirebileceği eylemler."""

    CLEAN = "Clean"
    LEFT = "Left"
    RIGHT = "Right"


# Odalar soldan sağa sıralıdır: A solda, B sağda.
ROOMS = ("A", "B")

# Hareket eylemlerinin oda sırası üzerindeki etkisi.
MOVE_OFFSETS = {Action.LEFT: -1, Action.RIGHT: +1}

DEFAULT_DIRT_PROBABILITY = 0.3


class Environment:
    """İki odalı robot süpürge ortamı.

    Başlangıç konumu ve oda durumları verilmezse ``rng`` ile rastgele seçilir.
    Aynı tohumla (seed) oluşturulan ``rng`` her seferinde aynı ortamı üretir.
    """

    def __init__(
        self,
        rng=None,
        dirt_probability=DEFAULT_DIRT_PROBABILITY,
        location=None,
        statuses=None,
    ):
        if not 0.0 <= dirt_probability <= 1.0:
            raise ValueError("Kirlenme olasılığı 0 ile 1 arasında olmalıdır.")

        self._rng = rng if rng is not None else random.Random()
        self.dirt_probability = dirt_probability

        if statuses is None:
            statuses = {room: self._rng.choice(list(Status)) for room in ROOMS}
        if set(statuses) != set(ROOMS):
            raise ValueError(f"Oda durumları tam olarak {ROOMS} odalarını içermelidir.")
        self._statuses = dict(statuses)

        if location is None:
            location = self._rng.choice(ROOMS)
        if location not in ROOMS:
            raise ValueError(f"Geçersiz oda: {location!r}")
        self._location = location

    # ------------------------------------------------------------------
    # Durum sorguları
    # ------------------------------------------------------------------
    @property
    def location(self):
        """Ajanın şu an bulunduğu oda."""
        return self._location

    def status_of(self, room):
        """Verilen odanın temiz/kirli durumu."""
        return self._statuses[room]

    def statuses(self):
        """Tüm odaların durumunun bir kopyası (arayüz ve testler için)."""
        return dict(self._statuses)

    # ------------------------------------------------------------------
    # Algılama kuralı
    # ------------------------------------------------------------------
    def percept(self):
        """Ajanın algısı: (bulunduğu oda, o odanın durumu).

        Ajan diğer odanın durumunu göremez.
        """
        return self._location, self._statuses[self._location]

    # ------------------------------------------------------------------
    # Temizleme kuralı
    # ------------------------------------------------------------------
    def clean(self):
        """Ajanın bulunduğu odayı temizler."""
        self._statuses[self._location] = Status.CLEAN

    # ------------------------------------------------------------------
    # Hareket kuralı
    # ------------------------------------------------------------------
    def can_move(self, action):
        """Hareket eylemi ajanı ortamın içinde tutuyorsa True döner."""
        if action not in MOVE_OFFSETS:
            return False
        target = ROOMS.index(self._location) + MOVE_OFFSETS[action]
        return 0 <= target < len(ROOMS)

    def move(self, action):
        """Ajanı komşu odaya taşır.

        Sınır dışına çıkaracak bir hareket kesinlikle uygulanmaz ve
        ``ValueError`` fırlatılır; ortamın durumu değişmeden kalır.
        """
        if action not in MOVE_OFFSETS:
            raise ValueError(f"{action} bir hareket eylemi değildir.")
        if not self.can_move(action):
            raise ValueError(
                f"{self._location} odasından {action.value} hareketi ortam sınırının dışına çıkar."
            )
        self._location = ROOMS[ROOMS.index(self._location) + MOVE_OFFSETS[action]]

    # ------------------------------------------------------------------
    # Eylem yürütme
    # ------------------------------------------------------------------
    def execute(self, action):
        """Tek bir eylemi uygular: temizleme ya da hareket, asla ikisi birden."""
        if action is Action.CLEAN:
            self.clean()
        else:
            self.move(action)

    # ------------------------------------------------------------------
    # Otomatik kirlenme
    # ------------------------------------------------------------------
    def dirty_tick(self):
        """Temiz olan her odayı bağımsız olarak ``dirt_probability`` ile kirletir.

        Ajanın konumunu değiştirmez. Yeni kirlenen odaların listesini döndürür.
        """
        newly_dirty = []
        for room in ROOMS:
            if self._statuses[room] is Status.CLEAN and self._rng.random() < self.dirt_probability:
                self._statuses[room] = Status.DIRTY
                newly_dirty.append(room)
        return newly_dirty
