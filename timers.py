"""Duraklatılabilen zamanlayıcı.

Arayüzün adım ve kirlenme zamanlayıcıları bu sınıfı kullanır. Tkinter'a
doğrudan bağlı değildir: ``after`` / ``after_cancel`` metodlarına sahip her
nesneyle (pencere ya da testlerde sahte bir zamanlayıcı) çalışır.
"""

import time


class PausableTimer:
    """Duraklatılabilen tek seferlik zamanlayıcı.

    ``scheduler`` Tkinter'ın ``after`` / ``after_cancel`` metodlarına sahip bir
    nesnedir (pencere ya da testlerde sahte bir zamanlayıcı). Duraklatıldığında
    kalan süreyi saklar, devam edildiğinde yalnızca kalan süre kadar bekler.
    """

    def __init__(self, scheduler, callback, clock=time.monotonic):
        self._scheduler = scheduler
        self._callback = callback
        self._clock = clock
        self._job = None
        self._due = None          # bekleyen tetiklemenin saati (saniye)
        self._remaining = None    # duraklatıldığında kalan süre (saniye)

    @property
    def is_pending(self):
        """Zamanlayıcı şu an tetiklenmeyi bekliyorsa True."""
        return self._job is not None

    @property
    def is_paused(self):
        return self._remaining is not None

    @property
    def remaining_ms(self):
        """Tetiklenmeye kalan süre (ms); bekleyen tetikleme yoksa None."""
        if self._remaining is not None:
            return self._remaining * 1000
        if self._due is not None:
            return max(0.0, self._due - self._clock()) * 1000
        return None

    def start(self, delay_ms):
        """Önceki bekleyen tetiklemeyi iptal edip tam aralıkla yeniden kurar."""
        self.cancel()
        self._schedule(delay_ms / 1000)

    def pause(self):
        """Bekleyen tetiklemeyi iptal eder ve kalan süreyi saklar."""
        if self._job is None:
            return
        self._remaining = max(0.0, self._due - self._clock())
        self._scheduler.after_cancel(self._job)
        self._job = None
        self._due = None

    def resume(self):
        """Duraklatıldığı andaki kalan süreden devam eder."""
        if self._remaining is None:
            return
        remaining, self._remaining = self._remaining, None
        self._schedule(remaining)

    def cancel(self):
        """Bekleyen ya da duraklatılmış tetiklemeyi tamamen iptal eder."""
        if self._job is not None:
            self._scheduler.after_cancel(self._job)
        self._job = None
        self._due = None
        self._remaining = None

    def _schedule(self, seconds):
        self._due = self._clock() + seconds
        self._job = self._scheduler.after(round(seconds * 1000), self._fire)

    def _fire(self):
        self._job = None
        self._due = None
        self._callback()
