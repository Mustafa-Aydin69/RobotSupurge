# Robot Süpürge Ajanı — Yapay Zekâya Giriş, Dönem İçi Proje 1
#
# Gereksinimler : Python 3.9 veya üzeri. Ek paket gerekmez
#                 (yalnızca standart kütüphane ve Tkinter kullanılır).
# Çalıştırma    : python main.py
# Testler       : python -m unittest discover -s tests -v
#
# Dosyalar:
#   environment.py  grid ve ortam (algılama, temizleme, hareket, kirlenme)
#   agents.py       basit refleks ajan ve model tabanlı ajan
#   simulation.py   algı-karar-eylem döngüsü ve günlük (arayüzden bağımsız)
#   gui.py          Tkinter arayüzü
"""Uygulamanın giriş noktası."""

from gui import run


def main():
    run()


if __name__ == "__main__":
    main()
