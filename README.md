# Robot Süpürge Ajanı

Yapay Zekâya Giriş dersi, Dönem İçi Proje 1.

Algı, eylem ve ajan türleri arasındaki ilişkiyi inceleyen bir robot süpürge
simülasyonu. Python ve Tkinter ile yazılmıştır, ek paket gerektirmez.

> Bu doküman geliştirme sürecinde güncellenmektedir. Şu an zorunlu temel
> uygulama (iki oda, basit refleks ajan) ve çok odalı grid ortamı
> tamamlanmıştır.

## Gereksinimler

- Python 3.9 veya üzeri (Tkinter, Python'un Windows kurulumuyla birlikte gelir)
- Ek paket gerekmez

## Çalıştırma

```bash
python main.py
```

## Testler

```bash
python -m unittest discover -s tests -v
```

Arayüz testleri gerçek bir Tkinter penceresi oluşturur. Ekranı olmayan bir
ortamda bu testler otomatik olarak atlanır.

## Kullanım

| Kontrol | İşlev |
|---|---|
| **Başlat** | Yeni bir simülasyon başlatır. Önceki durum ve günlük sıfırlanır. |
| **Duraklat / Devam** (Boşluk) | Simülasyonu durumunu koruyarak askıya alır ya da kaldığı yerden sürdürür. Adım ve kirlenme zamanlayıcıları kalan sürelerini korur; devam edildiğinde tam aralıktan değil, kalan süreden devam ederler. |
| **Durdur** (Esc) | Simülasyonu sonlandırır. Günlük ekranda kalır. |
| Adım aralığı (ms) | Ajanın iki adımı arasındaki süre. Varsayılan 700 ms. |
| Kirlenme aralığı (sn) | Kirlenme zamanlayıcısının tetiklenme aralığı. Varsayılan 3 sn. |
| Seed | İsteğe bağlı. Aynı seed aynı başlangıcı, kirlenme dizisini ve ajan seçimlerini üretir. |
| Satır / Sütun | Ortamın boyutu (1–6, en az 2 oda). Varsayılan 1×2. Yalnızca Başlat'ta uygulanır; simülasyon çalışırken veya duraklatılmışken değiştirilemez. |

Program kullanıcı durdurana kadar çalışır. Bütün odalar temiz olsa bile ajan
odalar arasında dolaşmaya devam eder.

Pencere yeniden boyutlandırılabilir; grid kullanılabilir alana göre ölçeklenir.

## Ortam ve ajan

- Varsayılan ortam yan yana iki odadan oluşur: **A** (solda) ve **B** (sağda).
- Ortam 6×6'ya kadar iki boyutlu bir grid olabilir. 1×2 dışındaki grid'lerde
  odalar satır harfi ve sütun numarasıyla adlandırılır: `A1, A2, …, B1, …, F6`
  (A en üst satır, 1 en sol sütun).
- Ajanın eylemleri: Temizle, Sağa git, Sola git, Yukarı git, Aşağı git.
  Ajan ortam sınırlarının dışına çıkamaz.
- Ajanın başlangıç odası ve odaların temiz/kirli durumu rastgele belirlenir.
- Ajan yalnızca bulunduğu odayı ve o odanın durumunu algılar.
- Her algı-karar-eylem döngüsünde tek bir eylem gerçekleştirilir:
  temizleme ve hareket ayrı adımlardır.
- Kirlenme zamanlayıcısı her tetiklendiğinde, temiz olan her oda birbirinden
  bağımsız olarak %30 olasılıkla kirlenir. Bu zamanlayıcı ajanın adımlarından
  bağımsız çalışır ve adım sayısını artırmaz.

### Basit refleks ajan

Ajan kararını yalnızca güncel algıya göre verir; geçmiş algıları, önceki
eylemleri ve günlüğü kullanmaz.

| Güncel algı | Seçilen eylem |
|---|---|
| A odası, kirli | Temizle |
| A odası, temiz | Sağa git (B odasına geç) |
| B odası, kirli | Temizle |
| B odası, temiz | Sola git (A odasına geç) |

1×2 dışındaki grid'lerde kural şöyledir:

- Bulunulan oda kirliyse **Temizle**.
- Temizse, bulunulan odadan sınırlar içinde kalan hareketlerden (sağ, sol,
  yukarı, aşağı) **rastgele biri**.

Ajan yalnızca değişmez grid yerleşimini ve bir rastgele sayı üretecini tutar.
Rastgele sayı üreteci algı belleği değildir: hangi odaların görüldüğünü
saklamaz, yalnızca geçerli hareketler arasından seçim yapar. Geçmiş konumlar,
ziyaret sayıları ve önceki eylemler kararı etkilemez.

## Günlük

Her ajan adımı için adım numarası, geçen süre, oda, algı ve eylem gösterilir:

```
Adım   12 | Süre: 00:08.4 | Oda: A | Algı: Kirli | Eylem: Temizle
Kirlenme  | Süre: 00:09.0 | B odası kirlendi
```

Günlük yalnızca izleme amaçlıdır, ajanın kararlarında kullanılmaz.

## Proje yapısı

```
main.py          giriş noktası
environment.py   grid ve ortam: algılama, temizleme, hareket ve kirlenme kuralları
agents.py        ajanlar
simulation.py    algı-karar-eylem döngüsü, durum yönetimi ve günlük
gui.py           Tkinter arayüzü
tests/           unittest testleri
tests/data/      Faz 1 (1×2) davranışının seed'li regresyon referansı
```

Bağımlılık yönü `gui → simulation → agents / environment` şeklindedir. Tkinter
yalnızca `gui.py` içinde kullanılır; ortam, ajan ve simülasyon arayüz olmadan
çalıştırılıp test edilebilir.
