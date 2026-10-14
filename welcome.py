"""Açılış ekranı ve "Nasıl Oynanır?" rehberi.

Bu ekranlar simülasyonla ilgili hiçbir şey bilmez; yalnızca kendilerine
verilen geri çağırma fonksiyonlarını çalıştırır (Oyna, Nasıl Oynanır?,
Ana Menü). Ekran geçişlerini ``gui.AppShell`` yönetir; bütün ekranlar aynı
ana pencerede açılır.

Açılış ekranı tek bir tuvalden oluşur. Soldaki illüstrasyon ve özellik
simgeleri referans tasarımdan kırpılmış görsellerdir (``welcome_assets``);
başlık ve metinler tuval yazısı, düğmeler gerçek ttk/ttkbootstrap
düğmeleridir. Arka plandaki açık mavi lekeler tuvalde çizilir; böylece
pencere büyüdükçe bulanıklaşmaz.
"""

import base64
import io
import math
import tkinter as tk
from dataclasses import dataclass
from tkinter import font as tkfont
from tkinter import ttk

import theme
import welcome_assets
from views import draw_logo

WELCOME_TITLE = "Robot Süpürge Ajanı"
WELCOME_SUBTITLE = "Yapay zekâ ajanlarının ortamı algılama ve temizlik davranışlarını simüle edin."
PLAY_TEXT = "Oyna"
GUIDE_TEXT = "Nasıl Oynanır?"
HOME_TEXT = "Ana Menü"

# Alt bölümdeki özellikler: (görsel adı, metin)
FEATURES = (
    ("feature_agents", "Üç farklı yapay zekâ\najanını deneyin"),
    ("feature_rooms", "Çok odalı ortamlarda\ntemizlik simülasyonu"),
    ("feature_compare", "Ajanları karşılaştırın\nve sonuçları inceleyin"),
    ("feature_log", "Ayrıntılı algı-eylem\ngünlüğünü takip edin"),
)

RELAYOUT_DELAY_MS = 60          # yeniden boyutlandırma bitince yerleşimin yenilenme gecikmesi
WIDE_MIN_WIDTH = 900            # illüstrasyonun solda durduğu en küçük genişlik
FEATURE_GRID_MIN_WIDTH = 720    # dört özelliğin tek satırda durduğu en küçük genişlik
FEATURES_MIN_HEIGHT = 560       # özellik şeridinin gösterildiği en küçük yükseklik
TITLE_SIZES = (40, 34, 28, 22)  # başlık sığmazsa sırayla denenen punto değerleri


def _pil():
    """Pillow varsa ``(Image, ImageTk)``; yoksa ``None`` (görseller Tk ile gösterilir)."""
    try:
        from PIL import Image, ImageTk
        return Image, ImageTk
    except Exception:  # noqa: BLE001  (Pillow yok ya da uyumsuz)
        return None


class ImageLoader:
    """Gömülü PNG'leri istenen boyuta getirir ve önbellekte tutar.

    Pillow varsa yüksek kaliteli (LANCZOS) ölçekleme yapılır. Yoksa Tk'nin
    kendi PNG desteği kullanılır; görsel yalnızca tam sayı oranında
    küçültülebilir, büyütülmez.
    """

    CACHE_LIMIT = 24

    def __init__(self, master, use_pil=True):
        self.master = master
        self.pil = _pil() if use_pil else None
        self._sources = {}
        self._cache = {}

    def native_size(self, name):
        return welcome_assets.SIZES[name]

    def get(self, name, width, height):
        """Görseli en-boy oranını koruyarak ``width × height`` kutusuna sığdırır."""
        native_w, native_h = self.native_size(name)
        factor = min(width / native_w, height / native_h)
        size = (max(1, round(native_w * factor)), max(1, round(native_h * factor)))
        key = (name, size)
        photo = self._cache.pop(key, None)       # en son kullanılan sona taşınır
        if photo is None:
            if len(self._cache) >= self.CACHE_LIMIT:
                self._cache.pop(next(iter(self._cache)))
            photo = self._render(name, size)
        self._cache[key] = photo
        return photo

    def _render(self, name, size):
        data = welcome_assets.PNG[name]
        if self.pil is not None:
            image_module, image_tk = self.pil
            if name not in self._sources:
                self._sources[name] = image_module.open(io.BytesIO(base64.b64decode(data))).convert("RGBA")
            resized = self._sources[name].resize(size, image_module.LANCZOS)
            return image_tk.PhotoImage(resized, master=self.master)
        photo = tk.PhotoImage(master=self.master, data=data)
        step = max(1, math.ceil(photo.width() / max(size[0], 1)))
        return photo.subsample(step) if step > 1 else photo

    def clear(self):
        self._cache.clear()
        self._sources.clear()


class WelcomeScreen:
    """Uygulamanın açılış ekranı."""

    def __init__(self, root, scale=1.0, on_play=None, on_guide=None, use_pil=True):
        self.root = root
        self.scale = scale
        self.on_play = on_play
        self.on_guide = on_guide
        self.images = ImageLoader(root, use_pil=use_pil)
        self._job = None
        self._size = None
        c = theme.COLORS

        self.canvas = tk.Canvas(root, background=c["welcome_bg"], highlightthickness=0, borderwidth=0,
                                **theme.tk_options())
        self.canvas.grid(row=0, column=0, sticky="nsew")
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)

        self.play_button = ttk.Button(self.canvas, text=theme.button_text("start", PLAY_TEXT),
                                      style="Hero.TButton", command=self._play)
        self.guide_button = ttk.Button(self.canvas, text=theme.button_text("guide", GUIDE_TEXT),
                                       style="HeroAlt.TButton", command=self._guide)
        self._play_window = self.canvas.create_window(0, 0, window=self.play_button, anchor="n")
        self._guide_window = self.canvas.create_window(0, 0, window=self.guide_button, anchor="n")

        self.canvas.bind("<Configure>", self._schedule_relayout)
        root.bind("<Return>", lambda _e: self._play())
        self.play_button.focus_set()

    # ------------------------------------------------------------------
    def _play(self):
        if self.on_play is not None:
            self.on_play()

    def _guide(self):
        if self.on_guide is not None:
            self.on_guide()

    def _px(self, value):
        return theme.px(value, self.scale)

    def _schedule_relayout(self, _event=None):
        if self._job is not None:
            self.canvas.after_cancel(self._job)
        self._job = self.canvas.after(RELAYOUT_DELAY_MS, self._on_relayout_timer)

    def _on_relayout_timer(self):
        self._job = None
        self.relayout()

    def destroy(self):
        """Bekleyen yerleşim tetiklemesini iptal eder ve ekranı kaldırır."""
        if self._job is not None:
            self.canvas.after_cancel(self._job)
            self._job = None
        self.root.unbind("<Return>")
        self.canvas.destroy()
        self.images.clear()

    # ------------------------------------------------------------------
    def relayout(self):
        """Bütün öğeleri tuvalin güncel boyutuna göre yerleştirir.

        Doğrudan çağrılırsa bekleyen yerleşim tetiklemesi iptal edilir; böylece
        hiçbir zaman sahipsiz (iptal edilemeyen) bir tetikleme kalmaz.
        """
        if self._job is not None:
            self.canvas.after_cancel(self._job)
            self._job = None
        c = self.canvas
        width, height = c.winfo_width(), c.winfo_height()
        if width <= 1 or height <= 1:
            return
        self._size = (width, height)
        c.delete("redraw")
        self._draw_blobs(width, height)

        show_features = height >= self._px(FEATURES_MIN_HEIGHT)
        feature_rows = 1 if width >= self._px(FEATURE_GRID_MIN_WIDTH) else 2
        feature_height = self._px(150 if feature_rows == 1 else 250) if show_features else 0
        top = height - feature_height
        wide = width >= self._px(WIDE_MIN_WIDTH)

        if wide:
            content_box = (width * 0.5, 0, width, top)
            column = min(self._px(540), content_box[2] - content_box[0] - self._px(56))
            block = self._content_height(column, logo=True)
            logo = block[1] <= top - self._px(32)
            self._place_illustration((0, 0, width * 0.5, top), align="left")
            self._place_content(content_box, column, logo=logo)
        else:
            column = min(self._px(460), width - self._px(48))
            needed = self._content_height(column, logo=False)[1] + self._px(32)
            illustration_height = top - needed
            if illustration_height >= self._px(120):
                self._place_illustration((0, 0, width, illustration_height), align="center")
                self._place_content((0, illustration_height, width, top), column, logo=False)
            else:
                self._place_content((0, 0, width, top), column, logo=False)
        if show_features:
            self._place_features(top, width, height, feature_rows)

    def _draw_blobs(self, width, height):
        c, colors = self.canvas, theme.COLORS
        blobs = [
            (width * 1.02, height * 0.02, width * 0.17, colors["welcome_blob"]),
            (width * 1.01, height * 0.86, width * 0.11, colors["welcome_blob_dark"]),
            (-width * 0.02, height * 1.02, width * 0.19, colors["welcome_blob"]),
        ]
        for x, y, r, color in blobs:
            c.create_oval(x - r, y - r * 0.85, x + r, y + r * 0.85, fill=color, outline="",
                          tags=("redraw", "blob"))

    def _title_font(self, column):
        """Başlığı sütuna sığan en büyük punto ile döndürür."""
        for size in TITLE_SIZES:
            spec = (theme.FONT_FAMILY, size, "bold")
            if tkfont.Font(root=self.root, font=spec).measure(WELCOME_TITLE) <= column:
                return spec
        return (theme.FONT_FAMILY, TITLE_SIZES[-1], "bold")

    def _content_height(self, column, logo):
        """Başlık bloğunun yüksekliği: ``(logo olmadan, logo ile)``."""
        title_font = tkfont.Font(root=self.root, font=self._title_font(column))
        subtitle_font = tkfont.Font(root=self.root, font=theme.font("hero_subtitle"))
        lines = max(1, math.ceil(subtitle_font.measure(WELCOME_SUBTITLE) / max(column, 1) * 1.15))
        base = (title_font.metrics("linespace") + self._px(14) + lines * subtitle_font.metrics("linespace")
                + self._px(34) + self._px(64) + self._px(14) + self._px(58))
        return base, base + self._logo_size() + self._px(18)

    def _logo_size(self):
        return self._px(124)

    def _place_illustration(self, box, align):
        x0, y0, x1, y1 = box
        photo = self.images.get("illustration", x1 - x0, y1 - y0)
        x = x0 if align == "left" else (x0 + x1 - photo.width()) / 2
        y = (y0 + y1 - photo.height()) / 2
        self.canvas.create_image(x, y, image=photo, anchor="nw", tags=("redraw", "illustration"))

    def _place_content(self, box, column, logo):
        c, colors = self.canvas, theme.COLORS
        x0, y0, x1, y1 = box
        cx = x0 + (x1 - x0) * (0.44 if x0 > 0 else 0.5)
        without_logo, with_logo = self._content_height(column, logo)
        block = with_logo if logo else without_logo
        y = max(y0 + self._px(16), y0 + (y1 - y0 - block) / 2)
        if logo:
            size = self._logo_size()
            photo = self.images.get("logo", size, size)
            c.create_image(cx, y, image=photo, anchor="n", tags=("redraw", "logo"))
            y += photo.height() + self._px(18)
        title = c.create_text(cx, y, text=WELCOME_TITLE, font=self._title_font(column), fill=colors["hero_title"],
                              anchor="n", tags=("redraw", "title"))
        y = c.bbox(title)[3] + self._px(14)
        subtitle = c.create_text(cx, y, text=WELCOME_SUBTITLE, font=theme.font("hero_subtitle"),
                                 fill=colors["hero_text"], width=column, justify="center", anchor="n",
                                 tags=("redraw", "subtitle"))
        y = c.bbox(subtitle)[3] + self._px(34)
        c.coords(self._play_window, cx, y)
        c.itemconfigure(self._play_window, width=column, height=self._px(64))
        y += self._px(64) + self._px(14)
        c.coords(self._guide_window, cx, y)
        c.itemconfigure(self._guide_window, width=column, height=self._px(58))

    def _place_features(self, top, width, height, rows):
        c, colors = self.canvas, theme.COLORS
        per_row = len(FEATURES) // rows
        margin = self._px(40) if rows == 1 else self._px(16)
        cell = (width - 2 * margin) / per_row
        row_height = (height - top) / rows
        icon = self._px(56)
        for index, (image_name, text) in enumerate(FEATURES):
            row, column = divmod(index, per_row)
            cx = margin + cell * (column + 0.5)
            y = top + row * row_height + self._px(16)
            photo = self.images.get(image_name, icon, icon)
            c.create_image(cx, y, image=photo, anchor="n", tags=("redraw", "feature-icon"))
            c.create_text(cx, y + photo.height() + self._px(10), text=text, font=theme.font("feature"),
                          fill=colors["hero_text"], justify="center", anchor="n", width=cell - self._px(12),
                          tags=("redraw", "feature-text"))
            if column:
                x = margin + cell * column
                c.create_line(x, y, x, y + self._px(110), fill=colors["separator"], tags=("redraw", "separator"))


# ----------------------------------------------------------------------
# Nasıl Oynanır? rehberi
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class GuideStep:
    """Rehberin bir adımı. ``section`` ileride vurgulanacak arayüz bölümünün adıdır."""

    title: str
    body: str
    section: str = ""


# Rehberin içeriği veridir; yeni adımlar bu listeye eklenerek rehber genişletilir.
GUIDE_STEPS = (
    GuideStep(
        "Simülasyonu başlatın",
        "Oyna ile simülasyon ekranına geçin, ayarları seçip Başlat'a basın. Robot ajan bulunduğu "
        "odayı algılar ve her adımda bir eylem seçer: temizlemek ya da başka bir odaya gitmek.",
    ),
    GuideStep(
        "Adım adım rehber hazırlanıyor",
        "Ayarlar, Gerçek Ortam, Ajanın İç Modeli, Simülasyon Durumu ve Algı-Eylem Günlüğü "
        "bölümleri sonraki sürümde bu ekranda tek tek tanıtılacak.",
    ),
)


class GuideNavigator:
    """Rehber adımları arasında gezinme (arayüzden bağımsız)."""

    def __init__(self, steps=GUIDE_STEPS):
        if not steps:
            raise ValueError("Rehberde en az bir adım olmalıdır.")
        self.steps = tuple(steps)
        self.index = 0

    @property
    def current(self):
        return self.steps[self.index]

    @property
    def can_back(self):
        return self.index > 0

    @property
    def can_next(self):
        return self.index < len(self.steps) - 1

    def next(self):
        if self.can_next:
            self.index += 1
        return self.current

    def back(self):
        if self.can_back:
            self.index -= 1
        return self.current

    def position_text(self):
        return f"{self.index + 1} / {len(self.steps)}"


class GuideScreen:
    """"Nasıl Oynanır?" ekranı: adım kartı, İleri/Geri, Ana Menü ve Oyna."""

    def __init__(self, root, scale=1.0, on_home=None, on_play=None, steps=GUIDE_STEPS):
        self.root = root
        self.scale = scale
        self.navigator = GuideNavigator(steps)
        px = lambda value: theme.px(value, scale)  # noqa: E731

        self.frame = ttk.Frame(root, style="Page.TFrame", padding=px(24))
        self.frame.grid(row=0, column=0, sticky="nsew")
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)

        top = ttk.Frame(self.frame, style="Page.TFrame")
        top.grid(row=0, column=0, sticky="ew", pady=(0, px(16)))
        self.home_button = ttk.Button(top, text=theme.button_text("home", HOME_TEXT), command=on_home,
                                      **theme.button_options("small"))
        self.home_button.pack(side="left")
        ttk.Label(top, text=GUIDE_TEXT, style="Title.TLabel").pack(side="left", padx=(px(16), 0))

        outer, body = theme.card(self.frame, 28, scale)
        outer.grid(row=1, column=0, sticky="new")             # kart içeriği kadar yüksek
        body.columnconfigure(0, weight=1)
        self.position = ttk.Label(body, style="CardNote.TLabel")
        self.position.grid(row=0, column=0, sticky="w")
        self.step_title = ttk.Label(body, style="GuideTitle.TLabel")
        self.step_title.grid(row=1, column=0, sticky="w", pady=(px(8), px(10)))
        self.step_body = ttk.Label(body, style="GuideBody.TLabel", justify="left")
        self.step_body.grid(row=2, column=0, sticky="new")
        body.bind("<Configure>", lambda e: self.step_body.configure(wraplength=max(px(200), e.width - px(60))))

        nav = ttk.Frame(body, style="Card.TFrame")
        nav.grid(row=3, column=0, sticky="ew", pady=(px(20), 0))
        self.back_button = ttk.Button(nav, text=theme.button_text("back", "Geri"), command=self.back,
                                      width=-10, **theme.button_options("secondary"))
        self.next_button = ttk.Button(nav, text=f"İleri  {theme.BUTTON_SYMBOLS['next']}"
                                      if not theme.text_only() else "İleri",
                                      command=self.next, width=-10, **theme.button_options("secondary"))
        self.play_button = ttk.Button(nav, text=theme.button_text("start", PLAY_TEXT), command=on_play,
                                      width=-10, **theme.button_options("primary"))
        self.back_button.pack(side="left")
        self.next_button.pack(side="left", padx=(px(10), 0))
        self.play_button.pack(side="right")
        root.bind("<Escape>", lambda _e: on_home() if on_home else None)
        self._show()

    def _show(self):
        step = self.navigator.current
        self.position.configure(text=f"Adım {self.navigator.position_text()}")
        self.step_title.configure(text=step.title)
        self.step_body.configure(text=step.body)
        self.back_button.configure(state="normal" if self.navigator.can_back else "disabled")
        self.next_button.configure(state="normal" if self.navigator.can_next else "disabled")

    def next(self):
        self.navigator.next()
        self._show()

    def back(self):
        self.navigator.back()
        self._show()

    def destroy(self):
        self.root.unbind("<Escape>")
        self.frame.destroy()
