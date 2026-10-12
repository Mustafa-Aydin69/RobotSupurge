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
