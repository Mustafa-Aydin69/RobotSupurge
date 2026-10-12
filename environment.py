"""Robot süpürgenin içinde çalıştığı ortam.

Ortam, iki boyutlu bir grid üzerine yerleşmiş odalardan oluşur. Varsayılan
ortam, ödevin zorunlu kısmındaki yan yana iki odadır (A ve B). Her oda temiz
veya kirli olabilir. Ortam üç ayrı kural grubunu birbirinden bağımsız olarak yönetir:

* Algılama: ajan yalnızca bulunduğu odayı ve o odanın durumunu algılar.
* Temizleme: ajan yalnızca bulunduğu odayı temizleyebilir.
* Hareket: ajan yalnızca komşu odaya (sağ, sol, yukarı, aşağı) geçebilir,
  sınır dışına çıkamaz.

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
    UP = "Up"
    DOWN = "Down"


# Hareket eylemlerinin (satır, sütun) üzerindeki etkisi.
MOVE_DELTAS = {
    Action.LEFT: (0, -1),
    Action.RIGHT: (0, +1),
    Action.UP: (-1, 0),
    Action.DOWN: (+1, 0),
}

MIN_GRID_SIZE, MAX_GRID_SIZE = 1, 6
ROW_LETTERS = "ABCDEF"


class Grid:
    """Odaların iki boyutlu yerleşimi. Oluşturulduktan sonra değiştirilemez.

    Oda adları:
    * 1×2 ortamda ödev tanımına uygun olarak ``A`` ve ``B``,
    * diğer bütün boyutlarda satır harfi ve sütun numarası: ``A1``, ``B3`` …

    Satır 0 en üstte, sütun 0 en soldadır.
    """

    __slots__ = ("rows", "cols", "rooms", "_positions")

    def __init__(self, rows=1, cols=2):
        for label, value in (("Satır", rows), ("Sütun", cols)):
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{label} sayısı bir tam sayı olmalıdır.")
            if not MIN_GRID_SIZE <= value <= MAX_GRID_SIZE:
                raise ValueError(
                    f"{label} sayısı {MIN_GRID_SIZE} ile {MAX_GRID_SIZE} arasında olmalıdır."
                )
        if rows * cols < 2:
            raise ValueError("Ortamda en az iki oda bulunmalıdır.")

        if (rows, cols) == (1, 2):
            names = ("A", "B")
        else:
            names = tuple(f"{ROW_LETTERS[r]}{c + 1}" for r in range(rows) for c in range(cols))
        positions = {name: divmod(index, cols) for index, name in enumerate(names)}

        object.__setattr__(self, "rows", rows)
        object.__setattr__(self, "cols", cols)
        object.__setattr__(self, "rooms", names)
        object.__setattr__(self, "_positions", positions)

    def __setattr__(self, name, value):
        raise AttributeError("Grid değiştirilemez.")

    def __eq__(self, other):
        return isinstance(other, Grid) and (self.rows, self.cols) == (other.rows, other.cols)

    def __hash__(self):
        return hash((self.rows, self.cols))

    def __repr__(self):
        return f"Grid(rows={self.rows}, cols={self.cols})"

    @property
    def is_two_room(self):
        """Ödevin zorunlu 1×2 ortamı mı?"""
        return (self.rows, self.cols) == (1, 2)

    def name_of(self, row, col):
        if not self.in_bounds(row, col):
            raise ValueError(f"({row}, {col}) konumu ortamın dışındadır.")
        return self.rooms[row * self.cols + col]

    def position_of(self, name):
        """Oda adının (satır, sütun) karşılığı."""
        try:
            return self._positions[name]
        except KeyError:
            raise ValueError(f"Geçersiz oda: {name!r}") from None

    def in_bounds(self, row, col):
        return 0 <= row < self.rows and 0 <= col < self.cols

    def neighbor(self, name, action):
        """Hareket sonrası varılacak oda; sınır dışıysa ``ValueError``."""
        if action not in MOVE_DELTAS:
            raise ValueError(f"{action} bir hareket eylemi değildir.")
        row, col = self.position_of(name)
        d_row, d_col = MOVE_DELTAS[action]
        if not self.in_bounds(row + d_row, col + d_col):
            raise ValueError(f"{name} odasından {action.value} hareketi ortam sınırının dışına çıkar.")
        return self.name_of(row + d_row, col + d_col)

    def valid_moves(self, name):
        """Verilen odadan sınırlar içinde kalan hareketler (sabit sırada)."""
        row, col = self.position_of(name)
        return tuple(
            action for action, (d_row, d_col) in MOVE_DELTAS.items()
            if self.in_bounds(row + d_row, col + d_col)
        )


DEFAULT_DIRT_PROBABILITY = 0.3


class Environment:
    """Grid üzerinde çalışan robot süpürge ortamı (varsayılan 1×2).

    Başlangıç konumu ve oda durumları verilmezse ``rng`` ile rastgele seçilir.
    Aynı tohumla (seed) oluşturulan ``rng`` her seferinde aynı ortamı üretir.
    """

    def __init__(
        self,
        rng=None,
        dirt_probability=DEFAULT_DIRT_PROBABILITY,
        location=None,
        statuses=None,
        rows=1,
        cols=2,
    ):
        if not 0.0 <= dirt_probability <= 1.0:
            raise ValueError("Kirlenme olasılığı 0 ile 1 arasında olmalıdır.")

        self.grid = Grid(rows, cols)
        self._rng = rng if rng is not None else random.Random()
        self.dirt_probability = dirt_probability

        rooms = self.grid.rooms
        if statuses is None:
            statuses = {room: self._rng.choice(list(Status)) for room in rooms}
        if set(statuses) != set(rooms):
            raise ValueError("Oda durumları ortamdaki odaların tamamını içermelidir.")
        self._statuses = dict(statuses)

        if location is None:
            location = self._rng.choice(rooms)
        if location not in rooms:
            raise ValueError(f"Geçersiz oda: {location!r}")
        self._location = location

    # ------------------------------------------------------------------
    # Durum sorguları
    # ------------------------------------------------------------------
    @property
    def rooms(self):
        """Odaların adları, satır satır sıralı."""
        return self.grid.rooms

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

        Ajan diğer odaların durumunu göremez.
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
        return action in self.grid.valid_moves(self._location)

    def move(self, action):
        """Ajanı komşu odaya taşır.

        Sınır dışına çıkaracak bir hareket kesinlikle uygulanmaz ve
        ``ValueError`` fırlatılır; ortamın durumu değişmeden kalır.
        """
        # Grid.neighbor geçersiz eylemde ya da sınır dışında ValueError fırlatır;
        # konum ancak hedef oda geçerliyse güncellenir.
        self._location = self.grid.neighbor(self._location, action)

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
        for room in self.grid.rooms:
            if self._statuses[room] is Status.CLEAN and self._rng.random() < self.dirt_probability:
                self._statuses[room] = Status.DIRTY
                newly_dirty.append(room)
        return newly_dirty
