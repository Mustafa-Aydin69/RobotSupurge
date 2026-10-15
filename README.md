# Robot Süpürge Ajanı

Yapay Zekâya Giriş dersi, Dönem İçi Proje 1.

## Projenin amacı

Algı, eylem ve ajan türleri arasındaki ilişkiyi çalışan bir program üzerinde
incelemek. Robot süpürge, odaları kendiliğinden yeniden kirlenen bir ortamda
çalışır ve üç farklı ajan türüyle yönetilebilir:

| Ajan | Karar mekanizması |
|---|---|
| **Basit Refleks Ajan** | Yalnızca o anki algı (oda + temiz/kirli). Geçmiş kullanılmaz. |
| **Model Tabanlı Ajan** | Algılarından kurduğu iç model (her odanın son bilinen durumu ve yaşı). |
| **Amaç Tabanlı Ajan** | Aynı iç model + açık bir hedef oda ve oraya BFS ile çıkarılan rota. |

Program Python ve Tkinter ile yazılmıştır; arayüz teması için ttkbootstrap
kullanılır (kurulu değilse standart ttk temasıyla aynı işlevlerle çalışır). Ödevin
zorunlu kısmı (iki oda, basit refleks ajan, otomatik kirlenme, günlük,
durdurma) ve bütün isteğe bağlı geliştirmeler (çok odalı grid, model tabanlı
ajan, amaç tabanlı ajan) tamamlanmıştır.

## Python kaynak kodundan çalıştırma

**Gereksinimler:** Python 3.9 veya üzeri ve Tkinter (Python'un Windows
kurulumuyla birlikte gelir). Arayüz teması için ttkbootstrap 1.14.7
(`requirements.txt`; bağımlılığı Pillow). Python 3.9, 3.12 ve 3.13 ile test
edilmiştir.

```bash
pip install -r requirements.txt
python main.py
```

`requirements.txt` yoksa `pip install ttkbootstrap==1.14.7` yeterlidir.
ttkbootstrap kurulu değilse program aynı renklerle standart ttk ("clam")
temasında çalışır; bütün işlevler aynıdır, yalnızca görünüm sadeleşir.
Global Python kurulumunu değiştirmemek için sanal ortam önerilir:

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

Pencere açmadan doğrulama (çıkış kodu 0 = başarılı):

```bash
python main.py --self-test
```

## EXE kullanımı

Windows için hazırlanan `RobotSupurge.exe` Python kurulumu gerektirmez; çift
tıklayarak açılır. Tek dosyalık sürüm ilk açılışta kendini geçici bir klasöre
açtığı için 2–3 saniye bekleyebilir.

EXE'yi kaynak koddan üretmek için (proje klasöründe):

```bash
build_exe.bat
```

- Betik PyInstaller 6.22.3'ü ve `requirements.txt`'teki ttkbootstrap'ı
  projeye özel `.venv-build` sanal ortamına kurar (global Python'a dokunmaz),
  kaynak kodu `--self-test` ile doğrular ve `dist\RobotSupurge.exe` dosyasını
  üretir (`--onefile --windowed`). ttkbootstrap EXE'nin içine paketlenir;
  EXE'nin `--self-test` raporu kullanılan temayı ve sürümünü yazar.
- `build_exe.bat onedir` tek klasörlük sürüm üretir
  (`dist\RobotSupurge\RobotSupurge.exe`); daha hızlı açılır ama yaklaşık
  1.000 dosyadan oluşur.
- EXE'nin doğrulanması (sonuç dosyaya yazılır, çıkış kodu 0 = başarılı):

  ```bash
  start /wait dist\RobotSupurge.exe --self-test --report self_test_report.txt
  ```

- EXE imzasız olduğu için Windows SmartScreen ya da antivirüs bir uyarı
  gösterebilir.
- **Python kurulu olmayan bir bilgisayarda deneme:** Windows 11 Pro'da
  "Windows Özellikleri" bölümünden *Windows Korumalı Alan* (Windows Sandbox)
  etkinleştirilebilir (yönetici yetkisi ve yeniden başlatma gerekir). EXE
  korumalı alana kopyalanıp yukarıdaki `--self-test` komutu ve aşağıdaki
  teslim öncesi kontrol listesi uygulanır.

## Ortam

- Varsayılan ortam yan yana iki odadan oluşur: **A** (solda) ve **B** (sağda).
- Ortam 6×6'ya kadar iki boyutlu bir grid olabilir (en az 2 oda). 1×2
  dışındaki grid'lerde odalar satır harfi ve sütun numarasıyla adlandırılır:
  `A1, A2, …, B1, …, F6` (A en üst satır, 1 en sol sütun).
- Eylemler: Temizle, Sağa git, Sola git, Yukarı git, Aşağı git. Ajan ortam
  sınırlarının dışına çıkamaz; sınır dışı bir hareket ortam tarafından
  reddedilir.
- Ajanın başlangıç odası ve odaların temiz/kirli durumu rastgele belirlenir.
- Ajan yalnızca bulunduğu odayı ve o odanın durumunu algılar.
- Her algı-karar-eylem döngüsünde tek bir eylem gerçekleştirilir; temizleme ve
  hareket ayrı adımlardır.
- **Otomatik kirlenme:** Kirlenme zamanlayıcısı her tetiklendiğinde temiz
  olan her oda birbirinden bağımsız olarak %30 olasılıkla kirlenir. Bu
  zamanlayıcı ajanın adımlarından bağımsız çalışır ve adım sayısını artırmaz.
- Program kullanıcı durdurana kadar çalışır; bütün odalar temiz olsa bile ajan
  dolaşmaya devam eder.

## Ajanlar

### Basit refleks ajan

Kararını yalnızca güncel algıya göre verir; geçmiş algıları, önceki eylemleri
ve günlüğü kullanmaz. Ödevin karar tablosu birebir uygulanır:

| Güncel algı | Seçilen eylem |
|---|---|
| A odası, kirli | Temizle |
| A odası, temiz | Sağa git (B odasına geç) |
| B odası, kirli | Temizle |
| B odası, temiz | Sola git (A odasına geç) |

1×2 dışındaki grid'lerde: oda kirliyse **Temizle**; temizse bulunulan odadan
sınırlar içinde kalan hareketlerden **rastgele biri**. Ajan yalnızca değişmez
grid yerleşimini ve bir rastgele sayı üretecini tutar. Rastgele sayı üreteci
algı belleği değildir; geçmiş konumlar, ziyaret sayıları ve önceki eylemler
kararı etkilemez.

### Model tabanlı ajan

Yalnızca kendi algılarından bir **iç model** kurar; ortamın tamamını göremez.

- **Model:** Her oda için son bilinen durum, bu bilginin ait olduğu ajan adımı
  ve kaynağı (`algı` ya da `çıkarım`). Hiç algılanmamış odalar modelde yoktur,
  yani bilinmiyordur.
- **Güncelleme:** Her adımda önce güncel algı modele yazılır; güncel algı her
  zaman eski bilginin önüne geçer.
- **Eylem sonucu:** Simülasyon, ortam eylemi uyguladıktan sonra ajana eylemin
  başarılı olup olmadığını bildirir. Ajan ancak başarılı bir Temizle'den sonra
  odayı "temiz (çıkarım)" olarak kaydeder; başarılı bir hareketten sonra
  yalnızca kendi konumunu günceller. Sonraki algı çıkarımı doğrular ya da
  düzeltir. Başarısız eylemden çıkarım yapılmaz.
- **Karar:** Oda kirliyse Temizle. Temizse komşular arasından hiç
  algılanmamış olana; hepsi biliniyorsa son bilgisi en eski olana gider.
  Eşitlikte seed'li rastgele seçim yapılır.
- **Yaş:** Son bilgiden bu yana geçen ajan adımıdır; gerçek süre ya da kesin
  bir kirlenme olasılığı değildir.

1×2 ortamda her odadan yalnızca bir geçerli hareket olduğu için hareketleri
refleks ajanla aynı olabilir; fark en az üç odalı grid'lerde görülür.

### Amaç tabanlı ajan

Model tabanlı ajanın iç modelini kullanır. **Amacı:** temiz olduğundan en az
emin olunan odayı kontrol etmek ve kirliyse temizlemek. Açık bir hedef oda
seçer, oraya BFS ile en kısa rotayı çıkarır ve rotayı adım adım izler. Hedef
seçimi yalnızca iç modele, grid bilgisine ve ajanın kendi konumuna dayanır.

**Hedef öncelikleri:**

1. **Bilinen kirli oda** — en kısa BFS mesafesindeki.
2. **Bilinmeyen oda** (hiç algılanmamış) — en kısa BFS mesafesindeki.
3. **Keşif** — daha önce görülmüş odalar arasında `(yaş + d) / d` puanı en
   yüksek olan (`d`: BFS mesafesi). Bu sezgisel bir hedef seçim kuralıdır;
   kesin bir kirlenme olasılığı ya da kanıtlanmış en iyi strateji değildir.

Eşitlikte önce kısa mesafe, sonra seed'li rastgele seçim kullanılır; ajanın
bulunduğu oda hedef seçilmez. Ajan kirli gördüğü odayı hemen temizlediği ve
uzaktaki kirlenmeyi göremediği için 1. öncelik pratikte nadiren oluşur.

**BFS:** Komşular her zaman **Sol, Sağ, Yukarı, Aşağı** sırasıyla gezilir;
aynı uzunlukta birden fazla en kısa rota varsa bu sıra belirleyicidir.

**Hedefe bağlılık ve yeniden planlama:** Hedef; hedefe ulaşılması, hedefin
geçersizleşmesi, daha öncelikli bir hedef türünün ortaya çıkması, başarısız
hareket ya da rotanın ajanın bildiği konumdan hedefe ulaşmaması durumlarında
yeniden seçilir; aksi halde her adımda değiştirilmez. Yeni plan ajanın kendi
bildiği konumdan çıkarılır, rota yalnızca başarılı bildirilen hareket kadar
ilerler ve yoldaki kirli oda rotayı değiştirmeden temizlenir.

## Açılış ekranı

Program açıldığında önce açılış ekranı gösterilir: solda robot süpürge
illüstrasyonu, sağda başlık, kısa açıklama ve iki düğme, altta dört özellik.

| Düğme | İşlev |
|---|---|
| **Oyna** (Enter) | Simülasyon ekranını aynı pencerede açar. |
| **Nasıl Oynanır?** | Rehber ekranını açar: adımlar arasında İleri/Geri, Ana Menü ve Oyna. Rehber şimdilik kısa bir tanıtımdır; bölüm bölüm etkileşimli rehber sonraki sürümde eklenecektir. |
| **Ana Menü** (simülasyon ekranında, başlığın sağında) | Çalışan simülasyonu durdurur, zamanlayıcıları iptal eder, açık karşılaştırma penceresini kapatır ve açılış ekranına döner. Yeniden Oyna yeni bir oturum açar. |

Bütün ekranlar aynı ana pencerede açılır. İllüstrasyon ve simgeler referans
tasarımdan kırpılmış görsellerdir (`assets/welcome/`); kaynak koda
`welcome_assets.py` olarak gömülüdür ve `python -m tools.make_welcome_assets`
ile yeniden üretilir. Başlık, açıklama ve düğmeler gerçek arayüz
bileşenleridir. Dar pencerede illüstrasyon küçülerek üste geçer, özellikler iki
satıra iner; düğmeler her boyutta görünür kalır.

## Arayüz rehberi

Simülasyon ekranı yukarıdan aşağıya altı bölümden oluşur: başlık, **Ayarlar** kartı
(ayar alanları ve kontrol düğmeleri), **Gerçek ortam** ve **Ajanın iç modeli**
kartları, **Simülasyon durumu** kartları ve **Algı ve eylem günlüğü** tablosu.
Renkler, yazı tipleri ve boşluklar `theme.py`'de tanımlıdır.

| Kontrol | İşlev |
|---|---|
| **Başlat** | Yeni bir simülasyon başlatır; önceki durum ve günlük sıfırlanır. |
| **Duraklat / Devam** (Boşluk) | Durumu koruyarak askıya alır ya da kaldığı yerden sürdürür. Adım ve kirlenme zamanlayıcıları kalan sürelerini korur; süre göstergesi de durur. |
| **Durdur** (Esc) | Simülasyonu sonlandırır; günlük ve son durum ekranda kalır, süre sabitlenir. |
| **Ajanları Karşılaştır** | Karşılaştırma penceresini açar (aşağıya bakın). Ana simülasyonu etkilemez. |
| **Ekranı Temizle** | Günlük tablosundaki satırları ekrandan siler; simülasyonun kendi kayıtlarına dokunmaz. |
| Adım aralığı (ms) | Ajanın iki adımı arasındaki süre (100–5000, varsayılan 700). Çalışırken değiştirilebilir. |
| Kirlenme aralığı (sn) | Kirlenme tetiklemeleri arasındaki süre (0,5–60, varsayılan 3). Çalışırken değiştirilebilir. |
| Seed | İsteğe bağlı. Aynı seed aynı başlangıcı, kirlenmeleri ve ajan seçimlerini üretir. |
| Satır / Sütun | Grid boyutu (1–6, en az 2 oda). Yalnızca Başlat'ta uygulanır. |
| Ajan türü | Yalnızca Başlat'ta uygulanır. |

Satır, sütun ve ajan türü simülasyon çalışırken ya da duraklatılmışken
değiştirilemez. Düğme metinlerinin önündeki simgeler yalnızca görseldir; her
düğmenin anlamı metnindedir (`ROBOT_UI_TEXT_ONLY=1` ile simgeler kapatılır).

Pencerenin başlangıç boyutu kullanılabilir ekrana göre belirlenir (en çok
1440×1040) ve pencere yeniden boyutlandırılabilir; grid kullanılabilir alana
göre ölçeklenir. Dar pencerede ayar alanları ve durum kartları alt satıra
geçer, paneller alt alta dizilir. Alçak pencerede alt başlık başlığın yanına
geçer, ayar etiketleri kısalır ("Adım (ms)" gibi) ve kart başlıkları ile
gerekirse açıklama satırları gizlenir. Windows'ta yüksek DPI (ör. %150
ölçekleme) desteklenir.

**Gerçek ortam paneli:**

| Görünüm | Anlamı |
|---|---|
| Yeşil / küçük hücrede **T** | Temiz oda |
| Kahverengi, lekeli / küçük hücrede **K** | Kirli oda |
| Mavi çerçeve ve robot | Robotun bulunduğu oda |
| ◆ Mor elmas | Amaç tabanlı ajanın hedefi |

**İç model paneli** — "Ajanın iç modeli (gerçek durum değil)". Model tabanlı
ve amaç tabanlı ajanda görünür; yalnızca ajanın salt okunur model ve plan
kopyalarından çizilir, ajana bilgi vermez ve belleğini değiştiremez.

| Görünüm | Anlamı |
|---|---|
| Gri, `?` | Bilinmiyor (hiç algılanmadı) |
| Yeşil | Temiz (algı) |
| Yeşil, kesikli kenar | Temiz (ajanın kendi Temizle eyleminden çıkarım) |
| Sarı, çizgili, "Eski" | Eskimiş bilgi: yaş ≥ max(4, oda sayısı). Yalnızca görselleştirmedir. |
| Kahverengi | Kirli |
| ● Mavi nokta | Ajanın bildiği kendi konumu |
| □ Mor çerçeve ve ok | Amaç tabanlı ajanın hedefi ve kalan rotası |

**Simülasyon durumu kartları:** durum (renkli: çalışıyor yeşil, duraklatıldı
turuncu, durduruldu kırmızı), seçili ajan türü, ortam boyutu, kirli oda
sayısı, bilinen oda sayısı (model/amaç), hedef ve kalan rota (amaç), adım,
temizleme ve hareket sayıları ve saniye saniye akan süre. Son eylem günlük
tablosunda görülür.

### Günlük

Algı dizisi ve eylemler çalışma boyunca sırayla bir tabloda gösterilir:

| Adım | Süre | Oda | Algı | Eylem | Açıklama |
|---|---|---|---|---|---|
| 12 | 00:08.4 | A | Kirli | Temizle | – |
| – | 00:09.0 | B | – | – | Kirlenme: B odası kirlendi |
| – | 00:09.1 | A1 | – | – | Hedef: A1 (keşif, 2 adım, puan 6.00) — hedefe ulaşıldı |

- Adım satırları algı-eylem kayıtlarıdır. **Kirlenme** (turuncu zemin),
  **hedef değişimi** (mor zemin) ve **bilgi** (mavi zemin) satırları adım
  sayısını artırmaz.
- Ekranda en fazla 10.000 kayıt tutulur; eski satırlar kaldırıldığında en
  üstte bilgi verilir. Simülasyonun kendi günlüğü eksiksiz korunur.
- **Ekranı Temizle** yalnızca ekrandaki satırları siler. **Başlat** yeni
  simülasyonla günlüğü sıfırlar; **Durdur** günlüğü ekranda bırakır.
- Kullanıcı geçmiş kayıtlara bakarken otomatik kaydırma görünümü bozmaz.
- Günlük yalnızca izleme amaçlıdır; ajanların kararlarında kullanılmaz.

## Ajanların karşılaştırılması

Ana penceredeki **Ajanları Karşılaştır** düğmesi, üç ajanı aynı koşullarda
ölçen ayrı bir pencere açar. Ayarlar: grid satır/sütun, ilk seed, seed sayısı,
adım sayısı, kirlenme sıklığı (her N adımda %30) ve kirlenme biçimi.
Sonuçlar tablo ve çubuk grafik olarak gösterilir. Hesaplama ana döngüde
küçük dilimlerle (en fazla ~15 ms) yürütüldüğü için arayüz donmaz; **İptal**
edilen ölçümün kısmi sonuçları gösterilmez.

**Ölçütler:**

- **Kapsama adımı:** Kirlenme kapalıyken bütün odaların en az bir kez
  algılandığı adım (başlangıç odası 1. adımda algılanır). Ortalama, ortanca
  ve en kötü değer gösterilir. Adım sınırı içinde tamamlanmayan koşular
  ayrıca sayılır; değerleri bilinmediği için (sağdan sansürlü veri) ortalama
  yerine "≥" ile bir alt sınır, ortanca ya da en kötü değer bilinmiyorsa
  "> sınır" gösterilir.
- **Ortalama temiz oda oranı:** Kirlenme açıkken her adımdan sonra ölçülen
  temiz oda oranının ortalaması; ± seed'ler arası standart sapma.
- **Hareket / temizleme:** Bir temizlik için yapılan hareket sayısı. Hiç
  temizlik yapılmayan koşuda tanımsızdır ve ayrıca sayılır.

**Yöntem:**

- **Aynı başlangıç:** Aynı seed üç ajana aynı başlangıç odasını ve oda
  durumlarını verir; bu her seed için doğrulanır.
- **Ortak kirlenme:** Her tetiklemede her oda için ajandan bağımsız bir sayı
  çekilir; üç ajan aynı kirlenme denemeleri dizisiyle karşılaşır. Kirli odaya
  deneme etkisiz kaldığı için gerçekleşen kirlenmeler yine ajanların
  temizliklerine göre farklılaşabilir.
- **Bağımsız kirlenme:** Simülasyonun kendi mekanizması; ajanlar farklı
  hareket ettiği için karşılaştıkları kirlenmeler aynı olmaz.
- Kapsama adımı ortamın ne kadar hızlı tanındığını, temiz oda oranı sürekli
  kirlenme altında ortamın ne kadar temiz tutulduğunu ölçer; bir ajan birinde
  iyi, diğerinde ötekilerle aynı olabilir. Sonuçlar ölçüldüğü gibi gösterilir.

**Örnek ölçüm** (6×6, seed 0–19, 3000 adım, her 4 adımda %30, ortak kirlenme):

| Ajan | Kapsama ort. / ortanca / en kötü | Temiz oda oranı | Hareket / temizleme |
|---|---|---|---|
| Basit Refleks | 350,6 / 267,5 / 1416 | 0,126 ± 0,003 | 1,47 |
| Model Tabanlı | 73,6 / 70,0 / 102 | 0,157 ± 0,004 | 1,00 |
| Amaç Tabanlı | 60,5 / 61,0 / 67 | 0,158 ± 0,005 | 1,01 |

Aynı ölçümler komut satırından da alınabilir:

```bash
python -m tools.compare_agents
```

## Testler

```bash
python -m unittest discover -s tests -v
```

- Ortam, grid, üç ajan, BFS, simülasyon, zamanlayıcılar, arayüz,
  karşılaştırma, tema, arayüz yerleşimi ve `--self-test` için 340'ı aşkın
  test vardır. Testler ttkbootstrap kurulu ortamda da kurulu olmayan ortamda
  da çalıştırılabilir.
- Faz 1'in 1×2 davranışı seed'li bir regresyon referansıyla
  (`tests/data/phase1_reference.json`), karşılaştırma ölçümleri Faz 4 aracının
  kayıtlı çıktılarıyla (`tests/data/comparison_reference.json`) karşılaştırılır.
- Arayüz testleri gerçek bir Tkinter penceresi oluşturur; ekranı olmayan bir
  ortamda otomatik olarak atlanır.
- 50.000 adımlık dayanıklılık testleri normal paketten ayrıdır:

  ```bash
  set ROBOT_LONG_TESTS=1
  python -m unittest tests.test_endurance -v
  ```

## Proje klasör yapısı

```
main.py             giriş noktası (--self-test desteği)
environment.py      grid ve ortam: algılama, temizleme, hareket, kirlenme
agents.py           basit refleks, model tabanlı ve amaç tabanlı (BFS) ajanlar
simulation.py       algı-karar-eylem döngüsü, durum yönetimi ve günlük
comparison.py       ajan karşılaştırma ölçümleri
gui.py              Tkinter ana penceresi, kontroller, durum kartları ve günlük
views.py            tuval çizimleri (gerçek ortam, iç model, hedef ve rota)
theme.py            arayüz teması: renkler, yazı tipleri, ttkbootstrap stilleri
welcome.py          açılış ekranı ve "Nasıl Oynanır?" rehberi
welcome_assets.py   açılış ekranı görselleri (PNG, kaynak koda gömülü)
timers.py           duraklatılabilen zamanlayıcı
compare_window.py   ajan karşılaştırma penceresi
self_test.py        pencere açmadan doğrulama
tests/              unittest testleri ve referans veriler
tools/              komut satırı karşılaştırma aracı, açılış görsellerini kırpma betiği
assets/welcome/     açılış ekranının referans tasarımı ve kırpılmış görseller
build_exe.bat       Windows EXE derleme betiği
requirements.txt    arayüz teması bağımlılığı (ttkbootstrap)
```

Bağımlılık yönü `gui → simulation → agents / environment` şeklindedir. Ortam,
ajanlar, simülasyon ve karşılaştırma çekirdeği Tkinter kullanmaz; arayüz
olmadan çalıştırılıp test edilebilir.

## LMS teslimi

Ödev şartı gereği LMS'ye **yalnızca kaynak kod dosyaları** yüklenir. Programın
çalışması için gereken modüllerin tamamı şunlardır (hepsi aynı klasörde
olmalıdır):

```
main.py  environment.py  agents.py  simulation.py  comparison.py
gui.py  views.py  theme.py  timers.py  compare_window.py  self_test.py
welcome.py  welcome_assets.py  guide.py
```

Arayüz teması için gereken paket `main.py`'nin başındaki açıklamada yazılıdır
(`pip install ttkbootstrap==1.14.7`); aynı bilgi `requirements.txt` dosyasındadır.
ttkbootstrap kurulu değilse program standart ttk temasıyla aynı işlevlerle çalışır.

EXE dosyaları, `tests/`, `tools/`, `build_exe.bat` ve README teslime dahil
edilmez; GitHub reposunda korunur. Bu on dört dosyanın eksiksiz olduğu bir testle
doğrulanır (`tests/test_submission.py`).

## Teslim öncesi kontrol listesi

Ödev tanımındaki kontroller (kaynak koddan ya da EXE'den):

- [ ] 1×2, Basit Refleks Ajan: temiz odadan diğer odaya geçiliyor.
- [ ] Kirli oda temizleniyor; temizleme ve hareket ayrı adımlarda.
- [ ] Zamanlayıcıyla odalar yeniden kirleniyor (turuncu "Kirlenme" satırları).
- [ ] Günlük tablosunda adım numarası, oda, algı ve eylem sırayla görünüyor.
- [ ] Bütün odalar temizken de ajan dolaşmaya devam ediyor.
- [ ] Duraklat/Devam (Boşluk) ve Durdur (Esc) çalışıyor; durdurunca süre sabit.
- [ ] Çok odalı grid (ör. 3×4, 6×6) ve model/amaç tabanlı ajanlar çalışıyor.
- [ ] `python main.py --self-test` ya da EXE ile `--self-test` 9/9 başarılı (tema satırında "ttkbootstrap 1.14.7").
- [ ] Program açılış ekranıyla açılıyor; Oyna simülasyonu, Ana Menü açılış ekranını açıyor.
