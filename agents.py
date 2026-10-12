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
from collections import deque
from dataclasses import dataclass
from fractions import Fraction
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
    location: str        # ajanın bulunduğunu bildiği oda (algı veya başarılı hareket)
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

    Ajan ortamın tamamını göremez. Model yalnızca şu yollarla güncellenir:

    * ``act`` içinde güncel algı modele yazılır (güncel algı her zaman eski
      bilginin önüne geçer),
    * ``action_result`` ile başarılı olduğu bildirilen Temizle eyleminden sonra
      oda "temiz (çıkarım)" olarak kaydedilir. Bir sonraki algı bu çıkarımı
      doğrular ya da düzeltir,
    * ``action_result`` ile başarılı olduğu bildirilen hareketten sonra
      yalnızca ajanın kendi konum bilgisi güncellenir; hedef odanın durumu
      bilinmiyorsa bilinmiyor olarak kalır.

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
        self._location = None   # ajanın bulunduğunu bildiği oda
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

        * Başarılı Temizle: oda "temiz (çıkarım)" olarak kaydedilir.
        * Başarılı hareket: ajan kendi konumunu hedef oda olarak günceller;
          hedef odanın temiz/kirli durumu hakkında hiçbir bilgi eklenmez.
        * Başarısız eylem: hiçbir çıkarım yapılmaz.
        """
        pending, self._pending = self._pending, None
        if pending is None or pending[1] is not action or not succeeded:
            return
        room, _ = pending
        if action is Action.CLEAN:
            self._memory[room] = Observation(Status.CLEAN, self._step, SOURCE_INFERENCE)
        else:
            self._location = self._grid.neighbor(room, action)

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


# ----------------------------------------------------------------------
# Rota planlama (BFS)
# ----------------------------------------------------------------------
# Komşular her zaman Grid.valid_moves sırasıyla gezilir: Sol, Sağ, Yukarı,
# Aşağı. Aynı uzunlukta birden fazla en kısa rota varsa bu sıra hangisinin
# seçileceğini belirler; sonuç her zaman aynıdır.

def bfs_distances(grid, start):
    """``start`` odasından her odaya en kısa hareket sayısı."""
    grid.position_of(start)  # geçersiz oda adı reddedilir
    distances = {start: 0}
    queue = deque([start])
    while queue:
        room = queue.popleft()
        for move in grid.valid_moves(room):
            neighbor = grid.neighbor(room, move)
            if neighbor not in distances:
                distances[neighbor] = distances[room] + 1
                queue.append(neighbor)
    return distances


def shortest_path(grid, start, goal):
    """``start`` odasından ``goal`` odasına en kısa hareket dizisi (tuple).

    Saf ve deterministiktir; yalnızca grid bilgisini kullanır. Başlangıç ve
    hedef aynıysa boş rota döner. Bütün hareketler grid sınırları içindedir.
    """
    grid.position_of(goal)  # geçersiz oda adı reddedilir
    parents = {start: None}
    queue = deque([start])
    grid.position_of(start)
    while queue:
        room = queue.popleft()
        if room == goal:
            break
        for move in grid.valid_moves(room):
            neighbor = grid.neighbor(room, move)
            if neighbor not in parents:
                parents[neighbor] = (room, move)
                queue.append(neighbor)
    route = []
    room = goal
    while parents[room] is not None:
        room, move = parents[room]
        route.append(move)
    return tuple(reversed(route))


def route_rooms(grid, start, route):
    """Rotanın uğradığı odalar (başlangıç hariç); geçersiz rotada ValueError."""
    rooms = []
    room = start
    for move in route:
        room = grid.neighbor(room, move)
        rooms.append(room)
    return tuple(rooms)


# ----------------------------------------------------------------------
# Amaç tabanlı ajan
# ----------------------------------------------------------------------
# Hedef türleri ve öncelikleri (büyük olan önce gelir)
GOAL_DIRTY = "dirty"        # modelde kirli bilinen oda
GOAL_UNKNOWN = "unknown"    # hiç algılanmamış oda
GOAL_EXPLORE = "explore"    # bilgisi eskiyen, daha önce görülmüş oda
GOAL_PRIORITY = {GOAL_DIRTY: 3, GOAL_UNKNOWN: 2, GOAL_EXPLORE: 1}


@dataclass(frozen=True)
class Target:
    """Seçilen hedef ve seçim gerekçesi."""

    room: str
    kind: str            # GOAL_DIRTY | GOAL_UNKNOWN | GOAL_EXPLORE
    distance: int        # seçim anındaki BFS mesafesi
    score: object        # keşifte (yaş + d) / d, diğer türlerde None


# Yeniden planlama gerekçeleri (arayüzde gösterilir)
REPLAN_FIRST = "ilk hedef"
REPLAN_REACHED = "hedefe ulaşıldı"
REPLAN_INVALID = "hedef geçersiz"
REPLAN_PRIORITY = "daha öncelikli hedef"
REPLAN_FAILED = "başarısız hareket"
REPLAN_INCONSISTENT = "rota tutarsız"


@dataclass(frozen=True)
class PlanSnapshot:
    """Hedef ve rotanın salt okunur kopyası (arayüz ve testler için)."""

    target: object       # Target ya da None
    origin: str          # rotanın başladığı oda (ajanın bildiği konum)
    route: tuple         # kalan hareketler
    route_rooms: tuple   # kalan hareketlerin uğradığı odalar (başlangıç hariç)
    version: int         # hedef her yeniden seçildiğinde artar
    reason: str          # son yeniden seçimin gerekçesi


class GoalBasedAgent(ModelBasedAgent):
    """Amaç tabanlı ajan (goal-based agent).

    Model tabanlı ajanın iç modelini aynen kullanır. Amacı: temiz olduğundan
    en az emin olunan odayı kontrol etmek ve kirliyse temizlemek. Bunun için
    açık bir hedef oda seçer, oraya BFS ile en kısa rotayı çıkarır ve rotayı
    adım adım izler.

    Hedef öncelikleri (yalnızca iç model, grid ve ajanın kendi konumu kullanılır):

    1. Bilinen kirli oda: en kısa BFS mesafesindeki.
    2. Hiç algılanmamış oda: en kısa BFS mesafesindeki.
    3. Keşif: daha önce görülmüş odalar arasında ``(yaş + d) / d`` puanı en
       yüksek olan. Bu sezgisel bir kuraldır; kesin bir kirlenme olasılığı ya
       da kanıtlanmış en iyi strateji değildir.

    Eşitlikte önce kısa mesafe, sonra seed'li rastgele seçim kullanılır.
    Ajanın bulunduğu oda hedef olarak seçilmez.

    Hedefe bağlılık: hedef, aşağıdakilerden biri olana kadar korunur ve her
    adımda gereksiz yere yeniden seçilmez:

    * hedefe ulaşılması,
    * hedefin geçersizleşmesi (ör. bilinmeyen hedefin artık biliniyor olması),
    * daha yüksek öncelikli bir hedef türünün ortaya çıkması,
    * başarısız hareket,
    * rotanın ajanın bildiği konumdan hedefe ulaşmaması.

    Yeni plan her zaman ajanın kendi bildiği konumdan çıkarılır. Rota
    üzerindeki kirli oda önce temizlenir; temizlik rotayı değiştirmez.
    """

    name = "Amaç Tabanlı Ajan"

    __slots__ = ("_target", "_route", "_plan_version", "_plan_reason", "_replan_request")

    def __init__(self, grid=None, rng=None):
        super().__init__(grid=grid, rng=rng)
        self._target = None          # Target
        self._route = ()             # kalan hareketler
        self._plan_version = 0
        self._plan_reason = None
        self._replan_request = None  # başarısız hareketten sonra bir sonraki adımda yeniden planla

    # ------------------------------------------------------------------
    # Eylem sonucu
    # ------------------------------------------------------------------
    def action_result(self, action, succeeded):
        """Model güncellemesine ek olarak rotayı yönetir.

        * Başarılı hareket: rota yalnızca doğrulanan bu hareket kadar ilerler.
        * Başarısız hareket: rota ve hedef geçersiz kılınır; bir sonraki
          adımda ajanın bildiği konumdan yeniden planlanır.
        * Temizle: rota değişmez.
        """
        pending = self._pending
        super().action_result(action, succeeded)
        if pending is None or pending[1] is not action or action is Action.CLEAN:
            return
        if succeeded and self._route and self._route[0] is action:
            self._route = self._route[1:]
        elif not succeeded:
            self._target = None
            self._route = ()
            self._replan_request = REPLAN_FAILED

    def plan_snapshot(self):
        """Hedef ve rotanın salt okunur kopyası."""
        origin = self._location
        try:
            rooms = route_rooms(self._grid, origin, self._route) if origin else ()
        except ValueError:
            rooms = ()
        return PlanSnapshot(self._target, origin, tuple(self._route), rooms,
                            self._plan_version, self._plan_reason)

    # ------------------------------------------------------------------
    # Yeniden planlama kararı
    # ------------------------------------------------------------------
    def replan_reason(self, location):
        """Hedefin yeniden seçilmesi gerekiyorsa gerekçesini, yoksa None döndürür."""
        if self._replan_request is not None:
            return self._replan_request
        target = self._target
        if target is None:
            return REPLAN_FIRST
        if location == target.room:
            return REPLAN_REACHED
        if not self._target_still_valid(target):
            return REPLAN_INVALID
        if GOAL_PRIORITY[self._best_available_kind(location)] > GOAL_PRIORITY[target.kind]:
            return REPLAN_PRIORITY
        if not self._route_reaches_target(location):
            return REPLAN_INCONSISTENT
        return None

    def _target_still_valid(self, target):
        observation = self._memory.get(target.room)
        if target.kind == GOAL_DIRTY:
            return observation is not None and observation.status is Status.DIRTY
        if target.kind == GOAL_UNKNOWN:
            return observation is None
        return observation is not None

    def _best_available_kind(self, location):
        others = [room for room in self._grid.rooms if room != location]
        if any(r in self._memory and self._memory[r].status is Status.DIRTY for r in others):
            return GOAL_DIRTY
        if any(r not in self._memory for r in others):
            return GOAL_UNKNOWN
        return GOAL_EXPLORE

    def _route_reaches_target(self, location):
        if not self._route:
            return False
        try:
            rooms = route_rooms(self._grid, location, self._route)
        except ValueError:
            return False
        return rooms[-1] == self._target.room

    # ------------------------------------------------------------------
    # Hedef seçimi
    # ------------------------------------------------------------------
    def choose_target(self, location):
        """İç modele göre en uygun hedefi seçer (bulunulan oda hariç)."""
        distances = bfs_distances(self._grid, location)
        candidates = [room for room in self._grid.rooms if room != location]

        dirty = [r for r in candidates
                 if r in self._memory and self._memory[r].status is Status.DIRTY]
        if dirty:
            return self._nearest(dirty, distances, GOAL_DIRTY)

        unknown = [r for r in candidates if r not in self._memory]
        if unknown:
            return self._nearest(unknown, distances, GOAL_UNKNOWN)

        scores = {}
        for room in candidates:
            age = self._step - self._memory[room].step
            d = distances[room]
            scores[room] = Fraction(age + d, d)
        best_score = max(scores.values())
        best = [r for r in candidates if scores[r] == best_score]
        shortest = min(distances[r] for r in best)
        room = self._rng.choice([r for r in best if distances[r] == shortest])
        return Target(room, GOAL_EXPLORE, distances[room], best_score)

    def _nearest(self, rooms, distances, kind):
        shortest = min(distances[r] for r in rooms)
        room = self._rng.choice([r for r in rooms if distances[r] == shortest])
        return Target(room, kind, shortest, None)

    # ------------------------------------------------------------------
    # Kurallar
    # ------------------------------------------------------------------
    def move_rule(self, location):
        """Hareket kuralı: gerekirse yeniden planla, rotanın ilk hareketini uygula."""
        reason = self.replan_reason(location)
        if reason is not None:
            self._target = self.choose_target(location)
            self._route = shortest_path(self._grid, location, self._target.room)
            self._plan_version += 1
            self._plan_reason = reason
            self._replan_request = None
        return self._route[0]


# Simülasyon ve arayüzün kullandığı ajan türleri (anahtar -> sınıf).
# Sıra, arayüzdeki seçim listesinin sırasıdır; ilk tür varsayılandır.
AGENT_TYPES = {
    "reflex": ReflexAgent,
    "model": ModelBasedAgent,
    "goal": GoalBasedAgent,
}
DEFAULT_AGENT_TYPE = "reflex"
