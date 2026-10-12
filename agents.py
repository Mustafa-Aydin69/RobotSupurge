"""Robot süpürge ajanları.

Her ajan aynı arayüzü uygular: ``act(percept) -> Action``. Ajan her çağrıda
tam olarak bir eylem döndürür.

Bu modül grafik arayüzden tamamen bağımsızdır.
"""

from environment import Action, Status


class ReflexAgent:
    """Basit refleks ajan (simple-reflex agent).

    Kararını yalnızca o anki algıya, yani bulunduğu oda ve o odanın temiz/kirli
    durumuna göre verir. Hiçbir iç durum tutmaz: geçmiş algılar, önceki
    eylemler ve log kayıtları karar vermede kullanılmaz.

    Karar tablosu (ödev tanımındaki tablonun birebir karşılığı):

        A odası, kirli  -> Temizle
        A odası, temiz  -> Sağa git
        B odası, kirli  -> Temizle
        B odası, temiz  -> Sola git
    """

    name = "Basit Refleks Ajan"

    # Hareket kuralı: temiz odada hangi yöne gidileceği yalnızca odaya bağlıdır.
    MOVE_RULES = {"A": Action.RIGHT, "B": Action.LEFT}

    # İç durum tutulmadığını garanti etmek için örnek özniteliği yasaklanır.
    __slots__ = ()

    def act(self, percept):
        location, status = percept
        if status is Status.DIRTY:
            return self.clean_rule()
        return self.move_rule(location)

    @staticmethod
    def clean_rule():
        """Temizleme kuralı: bulunulan oda kirliyse temizle."""
        return Action.CLEAN

    def move_rule(self, location):
        """Hareket kuralı: bulunulan oda temizse diğer odaya geç."""
        return self.MOVE_RULES[location]
