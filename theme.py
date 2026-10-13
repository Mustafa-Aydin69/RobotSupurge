"""Arayüz teması: renkler, yazı tipleri, boşluklar, simgeler ve ttk stilleri.

Görünümle ilgili bütün değerler bu modülde toplanır; simülasyon ve ajanlarla
hiçbir ilgisi yoktur.

ttkbootstrap kuruluysa (``pip install -r requirements.txt``) "robot" adlı açık
bir tema kaydedilir ve düğme, giriş alanı ve tablo gibi bileşenler
``bootstyle`` ile biçimlenir. Kurulu değilse uygulama aynı renklerle standart
ttk ("clam") temasında çalışır; yalnızca görünüm sadeleşir, işlev değişmez.

Modül yüklenirken Tkinter'ı içe aktarmaz (sabitler Tkinter'dan bağımsızdır);
Tkinter ve ttkbootstrap yalnızca tema bir pencereye uygulanırken yüklenir.
"""

import os

# ----------------------------------------------------------------------
# Renkler
# ----------------------------------------------------------------------
COLORS = {
    "page": "#eef3f9",            # pencere zemini
    "card": "#ffffff",            # kart zemini
    "border": "#dbe3ee",          # kart ve tablo kenarlığı
    "text": "#1f2a37",
    "muted": "#64748b",           # açıklama ve başlık altı metinleri
    "primary": "#1b6fe4",
    "primary_active": "#155bc0",
    "danger": "#d93644",
    "danger_soft": "#fde8ea",
    "danger_soft_active": "#f9d3d7",
    "neutral": "#e9edf3",         # ikincil düğme
    "neutral_active": "#dce3ec",
    "disabled_bg": "#f1f4f8",
    "disabled_fg": "#a3adba",
    "badge_bg": "#e6f0fd",        # kısayol rozeti
    "badge_fg": "#1e4f91",
    "heading_bg": "#f4f7fb",      # tablo başlığı
    "select_bg": "#dbe8fb",
    "row_dirt_fg": "#c2410c",     # günlükte kirlenme satırı
    "row_dirt_bg": "#fff4eb",
    "row_goal_fg": "#7b3fbf",     # günlükte hedef değişimi satırı
    "row_goal_bg": "#f5effc",
    "row_info_fg": "#1d70b8",     # günlükte bilgi satırı
    "row_info_bg": "#eef5fd",
    "ok": "#22a447",              # "Çalışıyor" göstergesi
    "warning": "#d48806",
}

# Tuval (ortam ve iç model) renkleri
CANVAS_COLORS = {
    "background": "#ffffff",
    "clean": "#cdeac0",
    "dirty": "#c8a27a",
    "dirt_spot": "#6f4a2b",
    "robot": "#2f3e4e",
    "robot_ring": "#5fa8d3",
    "active_border": "#1b6fe4",
    "cell_border": "#b7c4d3",
    "cell_text": "#1f2a37",
    "goal": "#7b3fbf",
    "model_unknown": "#e4e8ee",
    "model_stale": "#fbe7a6",
    "stale_hatch": "#d5aa3a",
    "stale_border": "#e0b54a",
    "empty": "#eef1f5",
}

# ----------------------------------------------------------------------
# Yazı tipleri (punto) ve boşluklar (piksel, %100 ölçekte)
# ----------------------------------------------------------------------
FONT_FAMILY = "Segoe UI"
MONO_FAMILY = "Consolas"
FONT_SIZES = {
    "title": 20,
    "subtitle": 11,
    "card_title": 12,
    "body": 10,
    "caption": 9,
    "stat_value": 13,
    "log": 10,
    "badge": 9,
}

SPACING = {
    "page": 16,        # pencere kenarı
    "gap": 12,         # kartlar arası
    "card": 14,        # kart iç boşluğu
    "field": 10,       # ayar alanları arası
}

# ----------------------------------------------------------------------
# Simgeler
# ----------------------------------------------------------------------
# Windows'un simge yazı tiplerindeki karakterler. Yazı tipi yoksa simge
# gösterilmez; her simgenin yanında anlamı taşıyan bir metin bulunur.
ICON_FONT_FAMILIES = ("Segoe Fluent Icons", "Segoe MDL2 Assets")
ICON_GLYPHS = {
    "settings": "",
    "environment": "",
    "model": "",
    "stats": "",
    "log": "",
    "info": "",
    "keyboard": "",
    "state": "",
    "agent": "",
    "grid": "",
    "dirty": "",
    "known": "",
    "steps": "",
    "cleans": "",
    "moves": "",
    "elapsed": "",
    "target": "",
    "compare": "",
}

# Düğme metinlerinin önündeki simgeler (Segoe UI Symbol'de bulunan Unicode
# karakterler). Düğmenin anlamı her zaman metindedir.
BUTTON_SYMBOLS = {
    "start": "▶",      # ▶
    "pause": "❚❚",  # ❚❚
    "resume": "▶",
    "stop": "■",       # ■
    "compare": "⇄",    # ⇄
    "clear": "✕",      # ✕
}

# Bu ortam değişkeni tanımlıysa simgeler hiç kullanılmaz (yalnızca metin).
PLAIN_TEXT_ENV = "ROBOT_UI_TEXT_ONLY"

THEME_NAME = "robot"


def font(size_key, *style):
    """Tkinter yazı tipi tanımı, ör. ``font("title", "bold")``."""
    return (FONT_FAMILY, FONT_SIZES[size_key], *style)


def mono_font(size_key="log"):
    return (MONO_FAMILY, FONT_SIZES[size_key])


def text_only():
    return bool(os.environ.get(PLAIN_TEXT_ENV))


# ----------------------------------------------------------------------
# ttkbootstrap
# ----------------------------------------------------------------------
_bootstrap = None          # None: denenmedi, False: yok, modül: var


def _load_bootstrap():
    global _bootstrap
    if _bootstrap is None:
        try:
            import ttkbootstrap
            from ttkbootstrap.style import Style, ThemeDefinition  # noqa: F401
            _bootstrap = ttkbootstrap
        except Exception:  # noqa: BLE001  (eksik ya da uyumsuz kurulum: yedek temaya geçilir)
            _bootstrap = False
    return _bootstrap or None


def bootstrap_available():
    """ttkbootstrap kurulu ve yüklenebilir mi?"""
    return _load_bootstrap() is not None


def bootstrap_version():
    """Kurulu ttkbootstrap sürümü; bilinmiyorsa ``None``."""
    if not bootstrap_available():
        return None
    try:
        from importlib.metadata import version
        return version("ttkbootstrap")
    except Exception:  # noqa: BLE001  (paketlenmiş EXE'de üst veri bulunmayabilir)
        return getattr(_bootstrap, "__version__", None)


def theme_description():
    """Kullanılan temanın kısa açıklaması (rapor ve self-test için)."""
    if bootstrap_available():
        return f"ttkbootstrap {bootstrap_version() or '(sürüm bilinmiyor)'}"
    return "standart ttk (ttkbootstrap kurulu değil)"


def _bootstrap_colors():
    c = COLORS
    return {
        "primary": c["primary"], "secondary": "#6c7a8c", "success": c["ok"], "info": "#1d70b8",
        "warning": c["warning"], "danger": c["danger"], "light": c["neutral"], "dark": "#2b3440",
        "bg": c["card"], "fg": c["text"], "selectbg": c["select_bg"], "selectfg": c["text"],
        "border": c["border"], "inputfg": c["text"], "inputbg": c["card"], "active": c["neutral"],
    }


# Düğme türleri: ttkbootstrap'ta ``bootstyle`` ile, yedek temada bu
# modülde tanımlanan stillerle biçimlenir.
_BUTTON_BOOTSTYLE = {"primary": "primary", "outline": "secondary-outline"}
_BUTTON_STYLE = {
    "primary": "Start.TButton",
    "secondary": "Hold.TButton",
    "danger": "Stop.TButton",
    "outline": "Plain.TButton",
    "small": "Small.TButton",
}


def button_options(kind):
    """``ttk.Button`` için stil seçenekleri (``bootstyle`` ya da ``style``)."""
    if bootstrap_available() and kind in _BUTTON_BOOTSTYLE:
        return {"bootstyle": _BUTTON_BOOTSTYLE[kind]}
    return {"style": _BUTTON_STYLE[kind]}


def widget_options(bootstyle):
    """Giriş alanı, seçim listesi ve tablo için ``bootstyle`` (yalnızca ttkbootstrap'ta)."""
    return {"bootstyle": bootstyle} if bootstrap_available() else {}


def tk_options():
    """Düz Tk bileşenleri (Frame, Label, Canvas, Text) için ek seçenek.

    ttkbootstrap, düz Tk bileşenlerine kendi zemin ve kenarlık rengini verir;
    renkleri bu modül belirlediği için bu otomatik biçimleme kapatılır.
    """
    return {"autostyle": False} if bootstrap_available() else {}


def button_text(symbol_key, text):
    """Düğme metni: varsa simge + metin, yoksa yalnızca metin."""
    if text_only() or symbol_key not in BUTTON_SYMBOLS:
        return text
    return f"{BUTTON_SYMBOLS[symbol_key]}  {text}"


def icon_font_family(root):
    """Kullanılabilir simge yazı tipi; yoksa ``None``."""
    if text_only():
        return None
    from tkinter import font as tkfont
    families = set(tkfont.families(root))
    return next((family for family in ICON_FONT_FAMILIES if family in families), None)


# ----------------------------------------------------------------------
# Temayı uygulama
# ----------------------------------------------------------------------
def setup(root, scale=1.0):
    """Temayı ``root`` penceresine uygular ve ``ttk.Style`` nesnesini döndürür.

    Her ``Tk`` kökü için bir kez çağrılır (testler birden çok kök oluşturur).
    """
    from tkinter import ttk

    if bootstrap_available():
        from ttkbootstrap.publisher import Publisher
        from ttkbootstrap.style import Style, ThemeDefinition
        # ttkbootstrap tek bir Style nesnesi ve tema değişikliği aboneleri tutar;
        # önceki pencere kapandıysa onlar bırakılır ve bu pencere için yenisi
        # oluşturulur (kapanmış pencerenin bileşenlerine mesaj gönderilmez).
        if Style.instance is not None and getattr(Style.instance, "master", None) is not root:
            Style.instance = None
            Publisher.clear_subscribers()
        style = Style()
        if THEME_NAME not in style.theme_names():
            style.register_theme(ThemeDefinition(THEME_NAME, _bootstrap_colors(), "light"))
        style.theme_use(THEME_NAME)
    else:
        style = ttk.Style(root)
        style.theme_use("clam")
        _configure_plain_ttk(style)
    _configure_custom_styles(style, scale)
    # ttkbootstrap tema uygulanırken pencere zeminini tema rengine çeker;
    # sayfa zemini bu yüzden en son verilir.
    root.configure(background=COLORS["page"])
    return style


def _configure_plain_ttk(style):
    """ttkbootstrap yokken temel ttk bileşenlerini aynı renklere getirir."""
    c = COLORS
    style.configure(".", background=c["card"], foreground=c["text"], bordercolor=c["border"],
                    lightcolor=c["card"], darkcolor=c["border"], troughcolor=c["neutral"],
                    focuscolor=c["primary"], selectbackground=c["select_bg"], selectforeground=c["text"],
                    fieldbackground=c["card"], font=font("body"))
    style.map(".", foreground=[("disabled", c["disabled_fg"])])
    for widget in ("TEntry", "TSpinbox", "TCombobox"):
        style.configure(widget, padding=5, arrowcolor=c["muted"])
        style.map(widget, fieldbackground=[("disabled", c["disabled_bg"]), ("readonly", c["card"])],
                  bordercolor=[("focus", c["primary"])])
    style.configure("Treeview", background=c["card"], fieldbackground=c["card"], bordercolor=c["border"])
    style.map("Treeview", background=[("selected", c["select_bg"])], foreground=[("selected", c["text"])])
    style.configure("Treeview.Heading", background=c["heading_bg"], relief="flat", font=font("caption", "bold"))
    style.configure("TProgressbar", background=c["primary"], troughcolor=c["neutral"])


def _button_style(style, name, bg, fg, active_bg, border=None, font_spec=None, padding=(14, 7)):
    c = COLORS
    border = border or bg
    style.configure(name, background=bg, foreground=fg, bordercolor=border, lightcolor=bg, darkcolor=bg,
                    focuscolor=fg, padding=padding, font=font_spec or font("body", "bold"), relief="flat")
    style.map(name,
              background=[("disabled", c["disabled_bg"]), ("pressed", active_bg), ("active", active_bg)],
              lightcolor=[("disabled", c["disabled_bg"]), ("active", active_bg)],
              darkcolor=[("disabled", c["disabled_bg"]), ("active", active_bg)],
              bordercolor=[("disabled", c["border"])],
              foreground=[("disabled", c["disabled_fg"])])


def _configure_custom_styles(style, scale):
    """Her iki modda da kullanılan, uygulamaya özgü stiller."""
    c = COLORS
    page, card = c["page"], c["card"]
    style.configure("Page.TFrame", background=page)
    style.configure("Card.TFrame", background=card)
    style.configure("Title.TLabel", background=page, foreground=c["text"], font=font("title", "bold"))
    style.configure("Subtitle.TLabel", background=page, foreground=c["muted"], font=font("subtitle"))
    style.configure("CardTitle.TLabel", background=card, foreground=c["text"], font=font("card_title", "bold"))
    style.configure("CardNote.TLabel", background=card, foreground=c["muted"], font=font("body"))
    style.configure("Field.TLabel", background=card, foreground=c["text"], font=font("body"))
    style.configure("Muted.TLabel", background=card, foreground=c["muted"], font=font("caption"))
    style.configure("Warn.TLabel", background=card, foreground="#9a5b13", font=font("caption"))
    style.configure("StatCaption.TLabel", background=card, foreground=c["muted"], font=font("caption"))
    style.configure("StatValue.TLabel", background=card, foreground=c["text"], font=font("stat_value", "bold"))

    _button_style(style, "Start.TButton", c["primary"], "#ffffff", c["primary_active"])
    _button_style(style, "Hold.TButton", c["neutral"], c["text"], c["neutral_active"])
    _button_style(style, "Stop.TButton", c["danger_soft"], c["danger"], c["danger_soft_active"],
                  border="#f5c2c8")
    _button_style(style, "Plain.TButton", card, c["text"], c["neutral"], border=c["border"])
    _button_style(style, "Small.TButton", card, c["text"], c["neutral"], border=c["border"],
                  font_spec=font("caption"), padding=(10, 4))

    style.configure("Log.Treeview", font=mono_font(), rowheight=max(20, round(22 * scale)),
                    background=card, fieldbackground=card, bordercolor=c["border"])
    style.configure("Log.Treeview.Heading", font=font("caption", "bold"), background=c["heading_bg"],
                    foreground=c["text"], relief="flat", padding=(6, 4))


# ----------------------------------------------------------------------
# Ortak bileşenler
# ----------------------------------------------------------------------
def px(value, scale=1.0):
    """%100 ölçekteki piksel değerini ekran ölçeğine çevirir."""
    return round(value * scale)


def card(parent, padding, scale=1.0):
    """Beyaz, ince kenarlıklı kart. ``(dış çerçeve, iç alan)`` döndürür.

    Dış çerçeve yerleştirilir (grid/pack), bileşenler iç alana konur.
    """
    import tkinter as tk
    from tkinter import ttk

    outer = tk.Frame(parent, background=COLORS["card"], highlightthickness=1, bd=0,
                     highlightbackground=COLORS["border"], highlightcolor=COLORS["border"], **tk_options())
    body = ttk.Frame(outer, style="Card.TFrame", padding=px(padding, scale))
    body.pack(fill="both", expand=True)
    return outer, body


def icon_label(parent, name, background, size=13, foreground=None):
    """Simge yazı tipiyle simge etiketi; simge yazı tipi yoksa ``None``."""
    import tkinter as tk

    root = parent.winfo_toplevel()
    family = getattr(root, "_robot_icon_family", "?")
    if family == "?":
        family = icon_font_family(root)
        root._robot_icon_family = family
    if family is None:
        return None
    return tk.Label(parent, text=ICON_GLYPHS[name], font=(family, size), background=background,
                    foreground=foreground or COLORS["primary"], borderwidth=0, **tk_options())
