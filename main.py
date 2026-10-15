# Robot Süpürge Ajanı — Yapay Zekâya Giriş, Dönem İçi Proje 1
#
# Gereksinimler : Python 3.9 veya üzeri ve Tkinter (Python'un Windows kurulumuyla gelir).
#                 Arayüz teması için ttkbootstrap 1.14.7 (requirements.txt):
#                     pip install -r requirements.txt
#                 requirements.txt yoksa:  pip install ttkbootstrap==1.14.7
#                 ttkbootstrap kurulu değilse program standart ttk temasıyla, aynı
#                 işlevlerle çalışır; yalnızca görünüm sadeleşir.
# Çalıştırma    : python main.py
# Doğrulama     : python main.py --self-test   (pencere açmadan; çıkış kodu 0 = başarılı)
# Testler       : python -m unittest discover -s tests -v
#
# Dosyalar (hepsi aynı klasörde olmalıdır):
#   main.py            giriş noktası
#   environment.py     grid ve ortam (algılama, temizleme, hareket, kirlenme)
#   agents.py          basit refleks, model tabanlı ve amaç tabanlı (BFS) ajanlar
#   simulation.py      algı-karar-eylem döngüsü ve günlük (arayüzden bağımsız)
#   comparison.py      ajan karşılaştırma ölçümleri (arayüzden bağımsız)
#   gui.py             Tkinter ana penceresi
#   views.py           tuval çizimleri
#   theme.py           arayüz teması: renkler, yazı tipleri, ttkbootstrap stilleri
#   timers.py          duraklatılabilen zamanlayıcı
#   compare_window.py  ajan karşılaştırma penceresi
#   self_test.py       --self-test doğrulaması
#   welcome.py         açılış ekranı ve "Nasıl Oynanır?" rehberi
#   welcome_assets.py  açılış ekranı görselleri (PNG, kaynak koda gömülü)
#   guide.py           etkileşimli "Nasıl Oynanır?" rehberi (gerçek ekran üzerinde)
"""Uygulamanın giriş noktası."""

import sys


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        from self_test import run_self_test

        report = None
        if "--report" in argv:
            index = argv.index("--report")
            report = argv[index + 1] if index + 1 < len(argv) else None
        return run_self_test(report)

    from gui import run

    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
