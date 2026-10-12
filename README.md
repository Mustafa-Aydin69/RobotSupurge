# Robot Süpürge Ajanı

Yapay Zekâya Giriş dersi, Dönem İçi Proje 1.

Algı, eylem ve ajan türleri arasındaki ilişkiyi inceleyen bir robot süpürge
simülasyonu. Python ve Tkinter ile yazılmıştır, ek paket gerektirmez.

> Bu doküman geliştirme sürecinde güncellenmektedir. Şu an zorunlu temel
> uygulama (iki oda, basit refleks ajan), çok odalı grid ortamı, model
> tabanlı ajan ve amaç tabanlı ajan tamamlanmıştır.

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
| Ajan türü | Basit Refleks Ajan (varsayılan), Model Tabanlı Ajan veya Amaç Tabanlı Ajan. Yalnızca Başlat'ta uygulanır; çalışırken veya duraklatılmışken değiştirilemez. |

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

### Model tabanlı ajan

Ajan yalnızca kendi algılarından bir **iç model** kurar; ortamın tamamını
göremez.

- **Model:** Her oda için son bilinen durum (temiz/kirli), bu bilginin ait
  olduğu ajan adımı ve bilginin kaynağı (`algı` ya da `çıkarım`). Hiç
  algılanmamış odalar modelde yer almaz, yani bilinmiyordur.
- **Güncelleme:** Her adımda önce güncel algı modele yazılır; güncel algı her
  zaman eski bilginin önüne geçer.
- **Eylem sonucu:** Simülasyon, ortam eylemi uyguladıktan sonra ajana eylemin
  başarılı olup olmadığını bildirir (`action_result`). Ajan ancak başarılı bir
  Temizle bildiriminden sonra odayı "temiz (çıkarım)" olarak kaydeder;
  başarılı bir hareketten sonra da yalnızca kendi konumunu günceller. Bir
  sonraki algı çıkarımı doğrular ya da düzeltir. Başarısız eylemden çıkarım
  yapılmaz. Refleks ajan bu bildirimi yok sayar.
- **Karar:** Oda kirliyse Temizle. Temizse bulunulan odadan geçerli hareketler
  arasından, hedef komşusu hiç algılanmamış olan; bütün komşular biliniyorsa
  son bilgisi en eski olan seçilir. Eşitlikte seed'li rastgele seçim yapılır.
- **Yaş:** Son bilgiden bu yana geçen ajan adımıdır. Gerçek süre ya da kesin
  bir kirlenme olasılığı değildir; yalnızca bilginin ne kadar eskidiğini
  gösterir.

1×2 ortamda her odadan yalnızca bir geçerli hareket olduğu için model tabanlı
ajanın hareketleri refleks ajanla aynı olabilir. Fark en az üç odalı
grid'lerde görülür.

**İç model paneli:** Model tabanlı veya amaç tabanlı ajan seçiliyken "Ajanın iç modeli (gerçek
durum değil)" paneli gösterilir. Panel yalnızca ajanın salt okunur model
kopyasından çizilir; ajana bilgi vermez ve belleğini değiştiremez.

| Görünüm | Anlamı |
|---|---|
| Gri, `?` | Bilinmiyor (hiç algılanmadı) |
| Yeşil | Temiz (algı) |
| Yeşil, kesikli kenar | Temiz (kendi Temizle eyleminden çıkarım) |
| Sarı | Eskimiş: yaş ≥ max(4, oda sayısı). Yalnızca görselleştirme içindir. |
| Kahverengi | Kirli |

### Amaç tabanlı ajan

Model tabanlı ajanın iç modelini aynen kullanır. **Amacı:** temiz olduğundan
en az emin olunan odayı kontrol etmek ve kirliyse temizlemek. Bunun için
açık bir hedef oda seçer, oraya BFS ile en kısa rotayı çıkarır ve rotayı adım
adım izler. Hedef seçimi yalnızca iç modele, grid bilgisine ve ajanın kendi
konumuna dayanır; ajan algılamadığı bir odanın gerçek durumunu bilmez.

**Hedef öncelikleri:**

1. **Bilinen kirli oda** — en kısa BFS mesafesindeki.
2. **Bilinmeyen oda** (hiç algılanmamış) — en kısa BFS mesafesindeki.
3. **Keşif** — daha önce görülmüş odalar arasında `(yaş + d) / d` puanı en
   yüksek olan (`d`: BFS mesafesi). Bu sezgisel bir hedef seçim kuralıdır;
   kesin bir kirlenme olasılığı ya da kanıtlanmış en iyi strateji değildir.
   Yakın ve eski odaları öne çıkarır; uzak bir oda ancak yeterince eskiyse
   seçilir.

Eşitlikte önce kısa mesafe, sonra seed'li rastgele seçim kullanılır. Ajanın
bulunduğu oda hedef seçilmez. Ajan kirli gördüğü odayı hemen temizlediği ve
uzaktaki kirlenmeyi göremediği için 1. öncelik pratikte nadiren oluşur; ajan
çoğu zaman bilinmeyen ve keşif hedefleriyle çalışır.

**BFS:** Komşular her zaman **Sol, Sağ, Yukarı, Aşağı** sırasıyla gezilir.
Aynı uzunlukta birden fazla en kısa rota varsa bu sıra hangisinin seçileceğini
belirler; sonuç her zaman aynıdır.

**Hedefe bağlılık ve yeniden planlama:** Hedef, aşağıdakilerden biri olana
kadar korunur ve her adımda yeniden seçilmez:

- hedefe ulaşılması,
- hedefin geçersizleşmesi,
- daha yüksek öncelikli bir hedef türünün ortaya çıkması,
- başarısız hareket,
- rotanın ajanın bildiği konumdan hedefe ulaşmaması.

Yeni plan her zaman ajanın kendi bildiği konumdan çıkarılır. Rota yalnızca
başarılı olduğu bildirilen hareket kadar ilerler. Rota üzerindeki kirli oda
önce temizlenir; temizlik rotayı değiştirmez.

**Arayüzde:** Model panelinde hedef oda mor çerçeveyle ve kalan rota ok
olarak, gerçek ortamda yalnızca hedef işareti (mor elmas) gösterilir. Durum
satırında hedef, hedef türü ve kalan rota uzunluğu yer alır. Hedef her
değiştiğinde günlüğe mor renkte bir bilgi satırı eklenir:

```
Hedef     | A1 (keşif, 2 adım, puan 6.00) — hedefe ulaşıldı
```

Bu satırlar ajan adımı değildir; adım sayısını etkilemez.

## Ajanların karşılaştırılması

Ölçüm aracı arayüzden bağımsızdır:

```bash
python -m tools.compare_agents
```

- **Aynı başlangıç:** Ortamın rastgele üreteci ajanınkinden önce türetildiği
  için aynı seed bütün ajanlara aynı başlangıç odasını ve oda durumlarını
  verir; araç bunu her seed için ayrıca doğrular.
- **Kapsama adımı:** Kirlenme kapalıyken bütün odaların en az bir kez
  algılandığı adımın numarası (başlangıç odası 1. adımda algılanır).
- **Temiz oda oranı:** Her adımdan sonra ölçülen temiz oda oranlarının
  ortalaması (3000 adım, her 4 adımda bir %30 kirlenme).
- **Kirlenme biçimleri:** *Bağımsız* biçimde simülasyonun kendi kirlenme
  mekanizması kullanılır; ajanlar farklı hareket ettiği için aynı seed
  kullanılsa bile karşılaştıkları kirlenme olayları aynı olmaz. *Ortak*
  biçimde her tetiklemede her oda için ajandan bağımsız bir sayı çekilir;
  bütün ajanlar aynı kirlenme denemeleri dizisiyle karşılaşır.

Sonuçlar ölçüldüğü gibi raporlanır; testlerde herhangi bir ajanın
üstünlüğü şart koşulmaz.

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
tools/           ajan karşılaştırma ölçüm aracı (arayüzden bağımsız)
```

Bağımlılık yönü `gui → simulation → agents / environment` şeklindedir. Tkinter
yalnızca `gui.py` içinde kullanılır; ortam, ajan ve simülasyon arayüz olmadan
çalıştırılıp test edilebilir.
