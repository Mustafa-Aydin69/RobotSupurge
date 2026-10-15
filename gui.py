"""Tkinter arayüzü: ana pencere, kontroller, durum satırı ve günlük.

Projede Tkinter'ı yalnızca arayüz modülleri kullanır (``gui``, ``views``,
``compare_window``). Tuval çizimleri ``views``, duraklatılabilen zamanlayıcı
``timers`` modülündedir. Arayüz simülasyonun mantığını
içermez; ``Simulation`` nesnesini iki bağımsız zamanlayıcıyla sürer:

* adım zamanlayıcısı ``Simulation.step()`` çağırır,
* kirlenme zamanlayıcısı ``Simulation.dirty_tick()`` çağırır.

Zamanlayıcılar duraklatıldığında kalan sürelerini korur ve devam edildiğinde
o süreden devam eder.
"""

import os
import sys
import tkinter as tk
from collections import deque
from tkinter import messagebox, ttk

from agents import AGENT_TYPES, DEFAULT_AGENT_TYPE, GOAL_DIRTY, GOAL_EXPLORE, GOAL_UNKNOWN
from environment import MAX_GRID_SIZE, MIN_GRID_SIZE, Action, Grid, Status
from simulation import DirtRecord, Simulation, SimulationState
import theme
from timers import PausableTimer  # noqa: F401  (testler ve geriye uyumluluk için dışa aktarılır)
from views import (  # noqa: F401  (testler ve geriye uyumluluk için dışa aktarılır)
    COLOR_GOAL, MODEL_AGE_NOTE, MODEL_CATEGORY_FILL, MODEL_CATEGORY_TEXT, MODEL_CLEAN, MODEL_DIRTY,
    MODEL_INFERRED, MODEL_PANEL_NAME, MODEL_PANEL_NOTE, MODEL_PANEL_TITLE, MODEL_STALE, MODEL_UNKNOWN,
    STATUS_TEXT, compute_layout, draw_environment, draw_logo, draw_model, empty_snapshot,
    environment_legend_items, model_category, model_legend_items, stale_threshold,
)

# ----------------------------------------------------------------------
# Varsayılanlar ve sınırlar
# ----------------------------------------------------------------------
DEFAULT_STEP_MS = 700
MIN_STEP_MS, MAX_STEP_MS = 100, 5000
DEFAULT_DIRT_SECONDS = 3.0
CLOCK_REFRESH_MS = 200          # süre göstergesinin yenilenme aralığı
SIDE_BY_SIDE_MIN_WIDTH = 760    # iki panelin yan yana dizildiği en küçük tahta genişliği
PANEL_MIN_HEIGHT = 230          # alt alta dizilen bir panelin en küçük yüksekliği
LEGEND_MIN_PANEL_HEIGHT = 220   # açıklama satırının gösterildiği en küçük kart yüksekliği
MAX_LOG_LINES = 10000           # ekrandaki günlüğün en fazla satır sayısı
LOG_TRIM_NOTICE = ("… Eski kayıtlar ekrandan kaldırıldı ({count} satır). "
                   "Simülasyonun kendi günlüğü eksiksiz korunuyor.")
LOG_CLEARED_NOTICE = "Günlük ekranı temizlendi; simülasyonun kendi kayıtları korunuyor."
MIN_DIRT_SECONDS, MAX_DIRT_SECONDS = 0.5, 60.0
DEFAULT_ROWS, DEFAULT_COLS = 1, 2

# ----------------------------------------------------------------------
# Arayüz metinleri (iç adlar İngilizce, ekranda Türkçe)
# ----------------------------------------------------------------------
AGENT_TYPE_TEXT = {key: cls.name for key, cls in AGENT_TYPES.items()}
AGENT_TYPE_BY_TEXT = {text: key for key, text in AGENT_TYPE_TEXT.items()}
ACTION_TEXT = {
    Action.CLEAN: "Temizle",
    Action.RIGHT: "Sağa git",
    Action.LEFT: "Sola git",
    Action.UP: "Yukarı git",
    Action.DOWN: "Aşağı git",
}

GOAL_KIND_TEXT = {
    GOAL_DIRTY: "bilinen kirli oda",
    GOAL_UNKNOWN: "bilinmeyen oda",
    GOAL_EXPLORE: "keşif",
}

APP_TITLE = "Robot Süpürge Ajanı"
APP_SUBTITLE = "Yapay zekâ ajanlarının ortamı algılama ve temizlik davranışlarını simüle edin."
SETTINGS_NOTE = ("Aralıklar çalışırken de değiştirilebilir. Satır/sütun (1–6, en az 2 oda) "
                 "ve ajan türü yalnızca Başlat'ta uygulanır.")
SEED_PLACEHOLDER = "örn. 42"
FIELD_SHORT_LABELS = {          # alçak ve dar pencerede kullanılan kısa etiketler
    "Adım aralığı (ms)": "Adım (ms)",
    "Kirlenme aralığı (sn)": "Kirlenme (sn)",
    "Seed (isteğe bağlı)": "Seed",
}
SHORTCUTS_TEXT = "Kısayollar: Boşluk = Duraklat/Devam, Esc = Durdur"
MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT = 680, 720
COMPACT_HEIGHT = 900            # bu yükseklikten alçak pencerede sıkı yerleşim

# İstatistik kartları: (anahtar, simge, başlık). "known" yalnızca iç modeli
# olan, "target" yalnızca hedefi olan ajanlarda gösterilir.
STAT_FIELDS = (
    ("state", "state", "Durum"),
    ("agent", "agent", "Seçili ajan türü"),
    ("size", "grid", "Ortam boyutu"),
    ("dirty", "dirty", "Kirli oda sayısı"),
    ("known", "known", "Bilinen oda sayısı"),
    ("target", "target", "Hedef"),
    ("steps", "steps", "Adım"),
    ("cleans", "cleans", "Temizleme"),
    ("moves", "moves", "Hareket"),
    ("elapsed", "elapsed", "Süre"),
)
STAT_MIN_WIDTH = 120            # bir istatistik kartının en küçük genişliği
STATE_STYLE = {                 # durum: (simge, renk anahtarı)
    SimulationState.READY: ("state", "muted"),
    SimulationState.RUNNING: ("state", "ok"),
    SimulationState.PAUSED: ("state_paused", "warning"),
    SimulationState.STOPPED: ("state_stopped", "danger"),
}

# Rehberin örnek simülasyonu: 3×3, amaç tabanlı ajan. Seed, adım sayısı ve
# kirlenme sıklığı, gerçek simülasyonda iç modelde bilinen, bilinmeyen ve eski
# odaların, kirli odaların ve boş olmayan bir rotanın birlikte görüldüğü bir
# an seçilerek belirlendi (tests/test_guide.py bunu denetler).
GUIDE_DEMO_SEED = 299
GUIDE_DEMO_STEPS = 14
GUIDE_DEMO_DIRT_EVERY = 4

# Rehber sırasında etkileşimli bileşenlerin olaylarını durduran bağlama etiketi.
GUIDE_LOCK_TAG = "RobotGuideLock"
GUIDE_LOCKED_EVENTS = (
    "<Button>", "<ButtonRelease>", "<Double-Button>", "<Triple-Button>", "<B1-Motion>", "<B2-Motion>",
    "<B3-Motion>", "<Key>", "<KeyRelease>", "<MouseWheel>", "<Shift-MouseWheel>",
)

TWO_ROOM_MODEL_NOTE = (
    "Not: 1×2 ortamda her odadan yalnızca bir geçerli hareket olduğu için bu ajanın "
    "hareketleri refleks ajanla aynı olabilir. Fark iç modelde görülür."
)

def format_elapsed(seconds):
    """Geçen süreyi ``dd:ss.s`` biçiminde yazar."""
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes):02d}:{secs:04.1f}"


def format_record(record):
    """Bir günlük kaydını ekranda gösterilecek tek satıra çevirir."""
    if isinstance(record, DirtRecord):
        rooms = ", ".join(record.rooms)
        return f"Kirlenme  | Süre: {format_elapsed(record.elapsed)} | {rooms} odası kirlendi"
    return (
        f"Adım {record.step:>4} | Süre: {format_elapsed(record.elapsed)} | "
        f"Oda: {record.room} | Algı: {STATUS_TEXT[record.status]} | "
        f"Eylem: {ACTION_TEXT[record.action]}"
    )


# Günlük tablosunun sütunları: (anahtar, başlık, genişlik, uzayabilir mi)
LOG_COLUMNS = (
    ("step", "Adım", 64, False),
    ("time", "Süre", 84, False),
    ("room", "Oda", 110, False),
    ("percept", "Algı", 84, False),
    ("action", "Eylem", 110, False),
    ("note", "Açıklama", 420, True),
)
LOG_EMPTY = "–"


def record_row(record):
    """Bir günlük kaydının tablo satırı: ``(tür, değerler)``. Tür "step" ya da "dirt"."""
    elapsed = format_elapsed(record.elapsed)
    if isinstance(record, DirtRecord):
        rooms = ", ".join(record.rooms)
        return "dirt", (LOG_EMPTY, elapsed, rooms, LOG_EMPTY, LOG_EMPTY, f"Kirlenme: {rooms} odası kirlendi")
    return "step", (str(record.step), elapsed, record.room, STATUS_TEXT[record.status],
                     ACTION_TEXT[record.action], LOG_EMPTY)


def goal_row(plan, elapsed):
    """Hedef değişiminin tablo satırı (adım sayılmaz)."""
    target = plan.target
    detail = f"{GOAL_KIND_TEXT[target.kind]}, {target.distance} adım"
    if target.score is not None:
        detail += f", puan {float(target.score):.2f}"
    return "goal", (LOG_EMPTY, format_elapsed(elapsed), target.room, LOG_EMPTY, LOG_EMPTY,
                    f"Hedef: {target.room} ({detail}) — {plan.reason}")


def parse_seed(text):
    """Boş metin için ``None``, tam sayı için sayıyı döndürür."""
    text = text.strip()
    if not text:
        return None
    return int(text)  # geçersizse ValueError


def parse_grid_size(rows_text, cols_text):
    """Satır ve sütun metnini doğrulayıp ``(rows, cols)`` döndürür.

    Geçersizse kullanıcıya gösterilecek Türkçe mesajla ``ValueError`` fırlatır.
    """
    try:
        rows, cols = int(rows_text.strip()), int(cols_text.strip())
    except ValueError:
        raise ValueError("Satır ve sütun sayısı tam sayı olmalıdır.") from None
    Grid(rows, cols)  # sınırları ve en az iki oda kuralını denetler
    return rows, cols


def agent_has_model(agent_type):
    """Ajan türü bir iç model kopyası sunuyor mu? (Panel bu yeteneğe göre gösterilir.)"""
    return hasattr(AGENT_TYPES[agent_type], "model_snapshot")


def agent_has_plan(agent_type):
    """Ajan türü bir hedef/rota kopyası sunuyor mu?"""
    return hasattr(AGENT_TYPES[agent_type], "plan_snapshot")


def format_goal_change(plan):
    """Hedef değişimini günlükte gösterilecek bilgi satırına çevirir.

    Bu satır bir ajan adımı değildir; adım sayısını etkilemez.
    """
    target = plan.target
    detail = f"{GOAL_KIND_TEXT[target.kind]}, {target.distance} adım"
    if target.score is not None:
        detail += f", puan {float(target.score):.2f}"
    return f"Hedef     | {target.room} ({detail}) — {plan.reason}"


def enable_windows_dpi_awareness():
    """Windows'ta yüksek DPI ekranlarda bulanık görüntüyü önler.

    Pencere oluşturulmadan önce çağrılmalıdır. Başarılı olursa True döner;
    diğer işletim sistemlerinde ya da hata durumunda hiçbir şey yapmaz.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)   # sistem DPI farkındalığı
        return True
    except (AttributeError, OSError):
        try:
            import ctypes
            return bool(ctypes.windll.user32.SetProcessDPIAware())
        except (AttributeError, OSError):
            return False


def ui_scale(root):
    """Ekran ölçeği: %100 -> 1.0, %150 -> 1.5 (en az 1.0)."""
    return max(1.0, root.winfo_fpixels("1i") / 96.0)


class LegendText(tk.Text):
    """Renk kutucuklu, satır sonunda kendiliğinden alta geçen açıklama satırı.

    Yüksekliği içeriğe göre ayarlanır; salt okunurdur. Öğeler
    ``views.*_legend_items`` biçimindedir: ``(tür, renk, simge, metin)``.
    """

    def __init__(self, parent, scale=1.0):
        super().__init__(parent, height=1, wrap="word", borderwidth=0, highlightthickness=0,
                         background=theme.COLORS["card"], foreground=theme.COLORS["muted"],
                         font=theme.font("caption"), cursor="arrow", takefocus=0,
                         padx=0, pady=theme.px(4, scale), spacing1=theme.px(2, scale),
                         spacing3=theme.px(2, scale), **theme.tk_options())
        self.tag_configure("note", foreground=theme.COLORS["muted"])
        self._content = None
        self.configure(state="disabled")
        self.bind("<Configure>", lambda _e: self._fit())

    def set_items(self, items, note=None):
        content = (tuple(items), note)
        if content == self._content:
            return
        self._content = content
        self.configure(state="normal")
        self.delete("1.0", "end")
        for index, (kind, color, symbol, text) in enumerate(items):
            if index:
                self.insert("end", "    ")
            # Bölünmez boşluklar: kutucuk ve metni aynı satırda kalır.
            if kind == "swatch":
                tag = f"swatch-{color}"
                self.tag_configure(tag, background=color)
                self.insert("end", "\u00a0\u00a0\u00a0\u00a0", tag)
            else:
                tag = f"glyph-{color}"
                self.tag_configure(tag, foreground=color, font=theme.font("caption", "bold"))
                self.insert("end", symbol, tag)
            self.insert("end", "\u00a0" + text.replace(" ", "\u00a0"))
        if note:
            self.insert("end", "\n" + note, "note")
        self.configure(state="disabled")
        self._fit()

    def text(self):
        """Açıklamanın düz metni (bölünmez boşluklar normal boşluk olarak)."""
        return self.get("1.0", "end").replace("\u00a0", " ").strip()

    def _fit(self):
        if self.winfo_width() <= 1:
            return
        count = self.count("1.0", "end", "displaylines")
        lines = count[0] if isinstance(count, tuple) else count
        if lines and int(self.cget("height")) != lines:
            self.configure(height=lines)


class VacuumApp:
    """Robot süpürge simülasyonunun ana penceresi."""

    CANVAS_WIDTH = 560    # başlangıç boyutu; pencereyle birlikte büyür
    CANVAS_HEIGHT = 240
    CANVAS_MIN_HEIGHT = 120   # tuvalin istediği yükseklik; pencere küçükse günlüğe yer kalır
    LOG_MIN_HEIGHT = 130      # günlüğün dar pencerede de görünür kalan en küçük yüksekliği

    def __init__(self, root, on_home=None):
        """``on_home`` verilirse başlıkta "Ana Menü" düğmesi gösterilir ve pencere
        (başlık, boyut, kapatma) ``AppShell`` tarafından yönetilir."""
        self.root = root
        self.on_home = on_home
        self.simulation = None
        self.step_timer = PausableTimer(root, self._on_step_timer)
        self.dirt_timer = PausableTimer(root, self._on_dirt_timer)
        self._step_ms = DEFAULT_STEP_MS
        self._dirt_seconds = DEFAULT_DIRT_SECONDS
        self._last_action = None
        self._last_plan_version = 0
        self._clock_job = None          # süre göstergesi zamanlayıcısı
        self.compare_window = None      # karşılaştırma penceresi (açıksa)
        self._log_trimmed = 0           # ekrandan kaldırılan günlük satırı sayısı
        self._log_following = True      # günlük en son kaydı takip ediyor mu?

        # Piksel cinsinden boyutlar ekran ölçeğiyle büyütülür; ekrana sığmayacaksa sınırlanır.
        self.scale = ui_scale(root)
        self.style = theme.setup(root, self.scale)
        if on_home is None:                     # tek başına açılan pencere
            root.title(APP_TITLE)
            configure_window_size(root, self.scale)
            root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_header()
        self._build_settings()
        self._build_canvas()
        self._build_status()
        self._build_log()

        # Tuval ve günlük pencereyle birlikte büyür; ayarlar ve düğmeler her
        # zaman üstte görünür kalır.
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=3)
        root.rowconfigure(4, weight=1, minsize=round(self.LOG_MIN_HEIGHT * self.scale))

        root.bind("<space>", self._on_space_key)
        root.bind("<Escape>", self._on_escape_key)

        self._refresh()

    # ------------------------------------------------------------------
    # Arayüz bileşenleri
    # ------------------------------------------------------------------
    def _build_header(self):
        """Üst başlık: simge, uygulama adı ve kısa açıklama."""
        page = theme.COLORS["page"]
        frame = ttk.Frame(self.root, style="Page.TFrame")
        frame.grid(row=0, column=0, sticky="ew", padx=self._px(theme.SPACING["page"]),
                   pady=(self._px(12), self._px(8)))
        size = self._px(52)
        self.logo = tk.Canvas(frame, width=size, height=size, highlightthickness=0, background=page,
                              **theme.tk_options())
        draw_logo(self.logo, size, page)
        self.logo.grid(row=0, column=0, rowspan=2, padx=(0, self._px(14)))
        self.title_label = ttk.Label(frame, text=APP_TITLE, style="Title.TLabel")
        self.title_label.grid(row=0, column=1, sticky="sw")
        self.subtitle = ttk.Label(frame, text=APP_SUBTITLE, style="Subtitle.TLabel")
        self.subtitle.grid(row=1, column=1, sticky="nw")
        self.header = frame
        self.home_button = None
        if self.on_home is not None:
            frame.columnconfigure(8, weight=1)
            self.home_button = ttk.Button(frame, text=theme.button_text("home", "Ana Menü"),
                                          command=self.go_home, takefocus=False, **theme.button_options("small"))
            self.home_button.grid(row=0, column=9, rowspan=2, sticky="e")

    def _build_settings(self):
        """Ayarlar kartı: başlık ve not, ayar alanları, kontrol düğmeleri."""
        outer, body = theme.card(self.root, theme.SPACING["card"], self.scale)
        outer.grid(row=1, column=0, sticky="ew", padx=self._px(theme.SPACING["page"]),
                   pady=(0, self._px(theme.SPACING["gap"])))
        body.columnconfigure(0, weight=1)
        self.settings_card, self._settings_body = outer, body

        # Başlık satırı: simge + "Ayarlar" solda, açıklama notu sağda.
        title_row = ttk.Frame(body, style="Card.TFrame")
        title_row.grid(row=0, column=0, sticky="ew")
        title_row.columnconfigure(2, weight=1)
        self._section_title(title_row, "settings", "Ayarlar").grid(row=0, column=0, sticky="w")
        self.settings_note = ttk.Label(title_row, text=SETTINGS_NOTE, style="Muted.TLabel", justify="right")
        self.settings_note.grid(row=0, column=2, sticky="e", padx=(self._px(16), 0))
        title_row.bind("<Configure>", lambda e: self.settings_note.configure(
            wraplength=max(self._px(200), e.width - self._px(140))))

        # Ayar alanları: etiket üstte, giriş alanı altta.
        self.fields_frame = ttk.Frame(body, style="Card.TFrame")
        self.fields_frame.grid(row=1, column=0, sticky="ew", pady=(self._px(10), self._px(12)))
        self.step_var = tk.StringVar(value=str(DEFAULT_STEP_MS))
        self.dirt_var = tk.StringVar(value=str(DEFAULT_DIRT_SECONDS))
        self.seed_var = tk.StringVar()
        self.rows_var = tk.StringVar(value=str(DEFAULT_ROWS))
        self.cols_var = tk.StringVar(value=str(DEFAULT_COLS))
        self.agent_var = tk.StringVar(value=AGENT_TYPE_TEXT[DEFAULT_AGENT_TYPE])

        self._fields = []
        field = self._field("Adım aralığı (ms)")
        ttk.Spinbox(field, textvariable=self.step_var, from_=MIN_STEP_MS, to=MAX_STEP_MS, increment=100,
                    width=8, **theme.widget_options("primary")).grid(row=1, column=0, sticky="ew")
        field = self._field("Kirlenme aralığı (sn)")
        ttk.Spinbox(field, textvariable=self.dirt_var, from_=MIN_DIRT_SECONDS, to=MAX_DIRT_SECONDS,
                    increment=0.5, width=8, **theme.widget_options("primary")).grid(row=1, column=0, sticky="ew")
        field = self._field("Seed (isteğe bağlı)")
        self.seed_entry = ttk.Entry(field, textvariable=self.seed_var, width=12, **theme.widget_options("primary"))
        self.seed_entry.grid(row=1, column=0, sticky="ew")
        self._add_placeholder(self.seed_entry, self.seed_var, SEED_PLACEHOLDER)
        field = self._field("Satır")
        self.rows_spin = ttk.Spinbox(field, textvariable=self.rows_var, from_=MIN_GRID_SIZE, to=MAX_GRID_SIZE,
                                     width=6, **theme.widget_options("primary"))
        self.rows_spin.grid(row=1, column=0, sticky="ew")
        field = self._field("Sütun")
        self.cols_spin = ttk.Spinbox(field, textvariable=self.cols_var, from_=MIN_GRID_SIZE, to=MAX_GRID_SIZE,
                                     width=6, **theme.widget_options("primary"))
        self.cols_spin.grid(row=1, column=0, sticky="ew")
        field = self._field("Ajan türü", weight=2)
        self.agent_combo = ttk.Combobox(field, textvariable=self.agent_var, values=list(AGENT_TYPE_TEXT.values()),
                                        state="readonly", width=22, **theme.widget_options("primary"))
        self.agent_combo.grid(row=1, column=0, sticky="ew")
        self.agent_var.trace_add("write", lambda *_: self._on_grid_setting_changed())
        # Simülasyon çalışmıyorken boyut değişikliği tuvalde önizlenir.
        self.rows_var.trace_add("write", lambda *_: self._on_grid_setting_changed())
        self.cols_var.trace_add("write", lambda *_: self._on_grid_setting_changed())
        self._fields_columns = None
        self.fields_frame.bind("<Configure>", lambda e: self._layout_fields(e.width))

        self._build_controls(body)

    def _section_title(self, parent, icon, text, note=None):
        """Kart başlığı: simge (varsa), kalın başlık ve isteğe bağlı açıklama."""
        frame = ttk.Frame(parent, style="Card.TFrame")
        label = theme.icon_label(frame, icon, theme.COLORS["card"], size=14)
        if label is not None:
            label.pack(side="left", padx=(0, self._px(8)))
        title = ttk.Label(frame, text=text, style="CardTitle.TLabel")
        title.pack(side="left")
        frame.title_label = title
        frame.note_label = None
        if note:
            frame.note_label = ttk.Label(frame, text=note, style="CardNote.TLabel")
            frame.note_label.pack(side="left", padx=(self._px(6), 0))
        return frame

    def _field(self, label, weight=1):
        frame = ttk.Frame(self.fields_frame, style="Card.TFrame")
        frame.columnconfigure(0, weight=1)
        frame.label = ttk.Label(frame, text=label, style="Field.TLabel")
        frame.label.grid(row=0, column=0, sticky="w", pady=(0, self._px(4)))
        frame.texts = (label, FIELD_SHORT_LABELS.get(label, label))
        self._fields.append((frame, weight))
        return frame

    def _layout_fields(self, width=None):
        """Ayar alanlarını genişliğe göre 6, 3 ya da 2 sütuna yerleştirir.

        Alçak pencerede etiketler kısalır ("Adım (ms)" gibi); böylece dar
        pencerede de altı alan tek satıra sığar ve tahtaya yer kalır.
        """
        width = self.fields_frame.winfo_width() if width is None else width
        if width >= 6 * self._px(150):
            columns, short = 6, False
        elif self._is_compact() and width >= 6 * self._px(100):
            columns, short = 6, True
        else:
            columns, short = (3 if width >= 3 * self._px(150) else 2), False
        if (columns, short) == self._fields_columns:
            return
        self._fields_columns = (columns, short)
        for frame, _ in self._fields:
            frame.label.configure(text=frame.texts[1 if short else 0])
        gap = self._px(theme.SPACING["field"])
        for index in range(6):
            self.fields_frame.columnconfigure(index, weight=0, uniform="")
        for index, (frame, weight) in enumerate(self._fields):
            row, column = divmod(index, columns)
            frame.grid(row=row, column=column, sticky="ew",
                       padx=(0 if column == 0 else gap, 0), pady=(0 if row == 0 else gap, 0))
            self.fields_frame.columnconfigure(column, weight=max(weight, 1) if columns == 6 else 1,
                                              uniform="" if columns == 6 else "fields")

    def _add_placeholder(self, entry, variable, text):
        """Boş alanda soluk örnek metin; yazmaya başlayınca kaybolur (değişkene yazılmaz)."""
        hint = tk.Label(entry, text=text, foreground=theme.COLORS["disabled_fg"],
                        background=theme.COLORS["card"], font=theme.font("body"), borderwidth=0,
                        **theme.tk_options())

        def update(*_):
            if variable.get() or entry.focus_get() is entry:
                hint.place_forget()
            else:
                hint.place(x=self._px(8), rely=0.5, anchor="w")

        hint.bind("<Button-1>", lambda _e: entry.focus_set())
        entry.bind("<FocusIn>", update, add="+")
        entry.bind("<FocusOut>", update, add="+")
        variable.trace_add("write", update)
        update()
        self.seed_placeholder = hint

    def _build_controls(self, parent):
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.grid(row=2, column=0, sticky="ew")
        frame.columnconfigure(1, weight=1)
        buttons = ttk.Frame(frame, style="Card.TFrame")
        buttons.grid(row=0, column=0, sticky="w")

        # Düğmeler odak almaz; böylece Boşluk tuşu yalnızca kısayol olarak çalışır.
        self.start_button = ttk.Button(buttons, text=theme.button_text("start", "Başlat"), command=self.start,
                                       takefocus=False, width=-12, **theme.button_options("primary"))
        self.pause_button = ttk.Button(buttons, text=theme.button_text("pause", "Duraklat"),
                                       command=self.toggle_pause, takefocus=False, width=-12,
                                       **theme.button_options("secondary"))
        self.stop_button = ttk.Button(buttons, text=theme.button_text("stop", "Durdur"), command=self.stop,
                                      takefocus=False, width=-12, **theme.button_options("danger"))
        self.compare_button = ttk.Button(buttons, text=theme.button_text("compare", "Ajanları Karşılaştır"),
                                         command=self.open_comparison, takefocus=False,
                                         **theme.button_options("outline"))
        gap = self._px(10)
        self.start_button.pack(side="left")
        self.pause_button.pack(side="left", padx=(gap, 0))
        self.stop_button.pack(side="left", padx=(gap, 0))
        self.compare_button.pack(side="left", padx=(gap, 0))

        prefix = "" if theme.text_only() else "\u2328  "
        self.shortcut_badge = tk.Label(
            frame, text=f"{prefix}{SHORTCUTS_TEXT}",
            background=theme.COLORS["badge_bg"], foreground=theme.COLORS["badge_fg"],
            font=theme.font("badge"), padx=self._px(12), pady=self._px(6), borderwidth=0,
            **theme.tk_options(),
        )
        self.shortcut_badge.grid(row=0, column=2, sticky="e", padx=(self._px(12), 0))
        self._controls_frame, self._buttons_frame = frame, buttons
        self._density = None
        frame.bind("<Configure>", lambda _e: self._update_density())
        self.root.bind("<Configure>", lambda e: self._update_density() if e.widget is self.root else None,
                       add="+")

    def _is_compact(self):
        """Pencere alçak mı? (Sıkı yerleşim: alt başlık yanda, kısa etiketler, başlıksız istatistik.)"""
        return self.root.winfo_height() < self._px(COMPACT_HEIGHT)

    def _update_density(self):
        """Pencere boyutuna göre sıkı ya da ferah yerleşim.

        * Alçak pencerede alt başlık gizlenir.
        * Kısayol rozeti düğmelerin yanına sığmazsa ferah yerleşimde alta iner;
          alçak pencerede rozet gizlenir ve kısayollar ayarlar notuna eklenir.
        """
        compact = self._is_compact()
        needed = (self._buttons_frame.winfo_reqwidth() + self.shortcut_badge.winfo_reqwidth()
                  + self._px(24))
        fits = self._controls_frame.winfo_width() >= needed
        density = (compact, fits, self.header.winfo_width())
        if density == self._density:
            return
        self._density = density
        # Alçak pencerede alt başlık başlığın yanına geçer, simge küçülür.
        if compact:
            self.subtitle.grid(row=0, column=2, sticky="sw", padx=(self._px(16), 0), pady=(0, self._px(5)))
            # Başlığın yanına sığmıyorsa alt başlık gizlenir (yarım görünmez).
            title_width = sum(w.winfo_reqwidth() for w in (self.logo, self.title_label, self.subtitle))
            if self.home_button is not None:
                title_width += self.home_button.winfo_reqwidth() + self._px(16)
            if self.header.winfo_width() < title_width + self._px(40):
                self.subtitle.grid_remove()
        else:
            self.subtitle.grid(row=1, column=1, sticky="nw", padx=0, pady=0)
        logo = self._px(40 if compact else 52)
        self.logo.configure(width=logo, height=logo)
        draw_logo(self.logo, logo, theme.COLORS["page"])
        self.logo.grid_configure(rowspan=1 if compact else 2)
        self.header.grid_configure(pady=(self._px(8), self._px(6)) if compact else (self._px(12), self._px(8)))
        self._settings_body.configure(padding=self._px(10 if compact else theme.SPACING["card"]))
        self.fields_frame.grid_configure(pady=(self._px(6), self._px(8)) if compact
                                         else (self._px(10), self._px(12)))
        note = SETTINGS_NOTE
        if fits:
            self.shortcut_badge.grid(row=0, column=2, columnspan=1, sticky="e", padx=(self._px(12), 0), pady=0)
        elif not compact:
            self.shortcut_badge.grid(row=1, column=0, columnspan=3, sticky="w", padx=0, pady=(self._px(8), 0))
        else:
            self.shortcut_badge.grid_remove()
            note = f"{SETTINGS_NOTE} {SHORTCUTS_TEXT}."
        if hasattr(self, "status_title"):
            if compact:
                self.status_title.pack_forget()
            else:
                self.status_title.pack(side="top", anchor="w", before=self.stats_frame)
            self._layout_stats()
        self._layout_fields()
        self.settings_note.configure(text=note)

    def _px(self, value):
        return theme.px(value, self.scale)

    def _build_canvas(self):
        # Gerçek ortam ve iç model iki ayrı kartta. Geniş alanda yan yana,
        # dar alanda alt alta yerleştirilir.
        self.board = ttk.Frame(self.root, style="Page.TFrame")
        self.board.grid(row=2, column=0, sticky="nsew", padx=self._px(theme.SPACING["page"]),
                        pady=(0, self._px(theme.SPACING["gap"])))
        self._board_layout = None   # (model görünür mü, yan yana mı)
        card_bg = theme.COLORS["card"]

        self.env_frame, body = theme.card(self.board, 12, self.scale)
        header, self.env_count = self._panel_header(body, "environment", "Gerçek ortam")
        header.pack(side="top", fill="x")
        self.canvas = tk.Canvas(body, width=self.CANVAS_WIDTH, height=self.CANVAS_MIN_HEIGHT,
                                background=card_bg, highlightthickness=0, **theme.tk_options())
        self.env_legend = LegendText(body, self.scale)
        self.env_legend.pack(side="bottom", fill="x")
        self.canvas.pack(fill="both", expand=True, pady=(self._px(6), 0))

        self.model_frame, body = theme.card(self.board, 12, self.scale)
        header, self.model_count = self._panel_header(body, "model", MODEL_PANEL_NAME, MODEL_PANEL_NOTE)
        self.model_title = header.title
        header.pack(side="top", fill="x")
        self.model_canvas = tk.Canvas(body, width=self.CANVAS_WIDTH // 2, height=self.CANVAS_MIN_HEIGHT,
                                      background=card_bg, highlightthickness=0, **theme.tk_options())
        self.model_legend = LegendText(body, self.scale)
        self.model_note = ttk.Label(body, text=TWO_ROOM_MODEL_NOTE, style="Warn.TLabel")
        self.model_note.bind("<Configure>", lambda e: self.model_note.configure(wraplength=max(120, e.width - 4)))
        self.model_legend.pack(side="bottom", fill="x")
        self.model_canvas.pack(side="top", fill="both", expand=True, pady=(self._px(6), 0))

        self.env_frame.grid(row=0, column=0, sticky="nsew")
        self.model_frame.grid(row=0, column=1, sticky="nsew")
        self.model_frame.grid_remove()

        # Pencere yeniden boyutlandırıldığında yerleşim ve grid yeniden hesaplanır.
        self.board.bind("<Configure>", lambda _event: self._layout_board())
        self.canvas.bind("<Configure>", lambda _event: self._draw())
        self.model_canvas.bind("<Configure>", lambda _event: self._draw())

    def _show_legends(self, visible):
        if not visible:
            self.env_legend.pack_forget()
            self.model_legend.pack_forget()
            return
        if not self.env_legend.winfo_manager():
            self.env_legend.pack(side="bottom", fill="x", before=self.canvas)
        if not self.model_legend.winfo_manager():
            before = self.model_note if self.model_note.winfo_manager() else self.model_canvas
            self.model_legend.pack(side="bottom", fill="x", before=before)

    def _panel_header(self, parent, icon, title, note=None):
        """Kart başlığı ve sağda oda sayısı: ``(çerçeve, sayı etiketi)``."""
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.title = self._section_title(frame, icon, title, note)
        frame.title.pack(side="left")
        count = ttk.Label(frame, style="CardNote.TLabel")
        count.pack(side="right")

        def fit(_event=None):
            # Oda sayısı sığmıyorsa yarım görünmek yerine gizlenir.
            fits = frame.winfo_width() >= frame.title.winfo_reqwidth() + count.winfo_reqwidth() + self._px(12)
            if fits and not count.winfo_manager():
                count.pack(side="right")
            elif not fits and count.winfo_manager():
                count.pack_forget()

        frame.bind("<Configure>", fit)
        return frame, count

    def _layout_board(self):
        """Panelleri yerleştirir.

        Model paneli gizliyse gerçek ortam bütün alanı kullanır. Görünürse
        tahta yeterince genişse ya da alt alta dizilemeyecek kadar alçaksa
        yan yana, değilse alt alta dizilir. Kartlar çok alçaksa açıklama
        satırları gizlenir; öncelik oda çizimlerindedir.
        """
        width, height = self.board.winfo_width(), self.board.winfo_height()
        model_visible = self.model_frame.winfo_manager() == "grid"
        side_by_side = (width >= self._px(SIDE_BY_SIDE_MIN_WIDTH)
                        or height < 2 * self._px(PANEL_MIN_HEIGHT))
        card_height = height if side_by_side or not model_visible else height / 2
        legends = card_height >= self._px(LEGEND_MIN_PANEL_HEIGHT)
        layout = (model_visible, side_by_side, legends)
        if layout == self._board_layout:
            return
        self._board_layout = layout
        self._show_legends(legends)
        for index in range(2):
            self.board.columnconfigure(index, weight=0, minsize=0, uniform="")
            self.board.rowconfigure(index, weight=0)
        half_gap = self._px(theme.SPACING["gap"]) // 2
        if not model_visible:
            self.board.columnconfigure(0, weight=1)
            self.board.rowconfigure(0, weight=1)
            self.env_frame.grid_configure(padx=0)
        elif side_by_side:
            # İki kart eşit genişlikte; panel başlığı dar pencerede de okunabilsin.
            self.board.columnconfigure(0, weight=1, uniform="panels")
            self.board.columnconfigure(1, weight=1, uniform="panels", minsize=round(300 * self.scale))
            self.board.rowconfigure(0, weight=1)
            self.env_frame.grid_configure(padx=(0, half_gap))
            self.model_frame.grid_configure(row=0, column=1, padx=(half_gap, 0), pady=0)
        else:
            self.board.columnconfigure(0, weight=1)
            self.board.rowconfigure(0, weight=1)
            self.env_frame.grid_configure(padx=0)
            self.board.rowconfigure(1, weight=1)
            self.model_frame.grid_configure(row=1, column=0, padx=0, pady=(self._px(8), 0))

    def _build_status(self):
        """Simülasyon durumu: simgeli istatistik kartları (dar pencerede birden çok satır)."""
        outer, body = theme.card(self.root, 12, self.scale)
        outer.grid(row=3, column=0, sticky="ew", padx=self._px(theme.SPACING["page"]),
                   pady=(0, self._px(theme.SPACING["gap"])))
        self.status_card = outer
        self.status_title = self._section_title(body, "stats", "Simülasyon durumu")
        self.status_title.pack(side="top", anchor="w")
        self.stats_frame = ttk.Frame(body, style="Card.TFrame")
        self.stats_frame.pack(side="top", fill="x", pady=(self._px(8), 0))
        card_bg = theme.COLORS["card"]
        self.stat_vars, self.stat_cells, self._stat_values, self._stat_icons = {}, {}, {}, {}
        for key, icon, caption in STAT_FIELDS:
            cell = ttk.Frame(self.stats_frame, style="Card.TFrame")
            cell.separator = tk.Frame(cell, width=1, background=theme.COLORS["border"], **theme.tk_options())
            icon_label = theme.icon_label(cell, icon, card_bg, size=16)
            if icon_label is not None:
                icon_label.pack(side="left", padx=(self._px(12), self._px(8)))
                self._stat_icons[key] = icon_label
            texts = ttk.Frame(cell, style="Card.TFrame")
            texts.pack(side="left", fill="x", padx=(0 if icon_label else self._px(12), self._px(6)))
            cell.texts = texts
            ttk.Label(texts, text=caption, style="StatCaption.TLabel").pack(anchor="w")
            var = tk.StringVar(value="—")
            value = ttk.Label(texts, textvariable=var, style="StatValue.TLabel")
            value.pack(anchor="w")
            cell.caption = caption
            self.stat_vars[key], self.stat_cells[key], self._stat_values[key] = var, cell, value
        self._stats_layout = None
        self.stats_frame.bind("<Configure>", lambda _e: self._layout_stats())

    def _visible_stats(self):
        agent_type = self._displayed()[2]
        hidden = set()
        if not agent_has_model(agent_type):
            hidden.add("known")
        if not agent_has_plan(agent_type):
            hidden.add("target")
        return [key for key, _, _ in STAT_FIELDS if key not in hidden]

    def _layout_stats(self):
        """Görünen kartları sığdığı kadar sütuna dizer; ayırıcılar satır içindedir.

        Sütun genişliği içeriğe göre belirlenir. Alçak pencerede kartlar tek
        satıra sığmıyorsa simgeler gizlenir.
        """
        keys = self._visible_stats()
        width = self.stats_frame.winfo_width()
        if width <= 1:
            return
        show_icons = True
        columns = self._stat_columns(keys, width, show_icons)
        if columns < len(keys) and self._is_compact():
            show_icons = False
            columns = self._stat_columns(keys, width, show_icons)
        layout = (tuple(keys), columns, show_icons)
        if layout == self._stats_layout:
            return
        self._stats_layout = layout
        for key, cell in self.stat_cells.items():
            if key not in keys:
                cell.grid_remove()
            icon = self._stat_icons.get(key)
            if icon is not None:
                if show_icons:
                    icon.pack(side="left", padx=(self._px(12), self._px(8)), before=cell.texts)
                else:
                    icon.pack_forget()
            has_icon = show_icons and icon is not None
            cell.texts.pack_configure(padx=(0 if has_icon else self._px(12), self._px(6)))
        for index in range(len(STAT_FIELDS)):
            self.stats_frame.columnconfigure(index, weight=0, uniform="")
        for index, key in enumerate(keys):
            row, column = divmod(index, columns)
            cell = self.stat_cells[key]
            cell.grid(row=row, column=column, sticky="ew", pady=(0 if row == 0 else self._px(8), 0))
            slaves = cell.pack_slaves()
            if column and cell.separator not in slaves:
                cell.separator.pack(side="left", fill="y", before=slaves[0])
            elif not column:
                cell.separator.pack_forget()
        for column in range(columns):
            self.stats_frame.columnconfigure(column, weight=1)

    def _stat_columns(self, keys, width, show_icons):
        """Kartların sığdığı en çok sütun sayısı (her sütun en geniş kartı kadar)."""
        widths = []
        for key in keys:
            content = self.stat_cells[key].texts.winfo_reqwidth() + self._px(20)
            if show_icons and key in self._stat_icons:
                content += self._px(40)
            widths.append(max(content, self._px(STAT_MIN_WIDTH if show_icons else 80)))
        for columns in range(len(keys), 1, -1):
            needed = sum(max(widths[i] for i in range(column, len(keys), columns)) for column in range(columns))
            if needed <= width:
                return columns
        return 1

    def status_summary(self):
        """Görünen istatistiklerin düz metni, ör. "Durum: Çalışıyor | Adım: 12 | …"."""
        return " | ".join(f"{self.stat_cells[key].caption}: {self.stat_vars[key].get()}"
                          for key in self._visible_stats())

    def _build_log(self):
        """Algı ve eylem günlüğü: sütunlu tablo ve "Ekranı Temizle" düğmesi."""
        outer, body = theme.card(self.root, 12, self.scale)
        outer.grid(row=4, column=0, sticky="nsew", padx=self._px(theme.SPACING["page"]),
                   pady=(0, self._px(theme.SPACING["page"])))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)
        self.log_card = outer

        header = ttk.Frame(body, style="Card.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, self._px(8)))
        self._section_title(header, "log", "Algı ve eylem günlüğü").pack(side="left")
        self.clear_log_button = ttk.Button(header, text=theme.button_text("clear", "Ekranı Temizle"),
                                           command=self.clear_log_view, takefocus=False,
                                           **theme.button_options("small"))
        self.clear_log_button.pack(side="right")

        columns = [key for key, *_ in LOG_COLUMNS]
        self.log_table = ttk.Treeview(body, columns=columns, show="headings", height=3,
                                      selectmode="none", style="Log.Treeview", takefocus=False)
        for key, heading, width, stretch in LOG_COLUMNS:
            self.log_table.heading(key, text=heading, anchor="w")
            self.log_table.column(key, width=self._px(width), minwidth=self._px(min(width, 60)),
                                  stretch=stretch, anchor="w")
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.log_table.yview)
        x_scrollbar = ttk.Scrollbar(body, orient="horizontal", command=self.log_table.xview)
        self.log_table.configure(yscrollcommand=scrollbar.set, xscrollcommand=x_scrollbar.set)
        self.log_table.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")
        x_scrollbar.grid(row=2, column=0, sticky="ew")

        c = theme.COLORS
        self.log_table.tag_configure("dirt", foreground=c["row_dirt_fg"], background=c["row_dirt_bg"])
        self.log_table.tag_configure("goal", foreground=c["row_goal_fg"], background=c["row_goal_bg"])
        self.log_table.tag_configure("info", foreground=c["row_info_fg"], background=c["row_info_bg"])
        self._log_rows = deque()        # ekrandaki kayıt satırları (bilgi notu hariç)
        self._trim_notice = None        # "eski kayıtlar kaldırıldı" satırı

        # Günlük alanı yeniden boyutlanınca (ör. pencere ya da durum kartları
        # değişince) en son kaydı izleyen görünüm en altta kalır. Kullanıcı
        # kaydırınca takip durumu kullanıcının konumuna göre güncellenir.
        self.log_table.bind("<Configure>", lambda _e: self._keep_log_position())
        for widget, sequences in ((self.log_table, ("<MouseWheel>", "<Prior>", "<Next>", "<Up>", "<Down>",
                                                    "<Home>", "<End>")),
                                  (scrollbar, ("<ButtonRelease-1>",))):
            for sequence in sequences:
                widget.bind(sequence, lambda _e: self.root.after_idle(self._update_log_following), add="+")

    def _update_log_following(self):
        if self.log_table.winfo_exists():
            self._log_following = self.log_table.yview()[1] >= 0.999

    def _keep_log_position(self):
        if self._log_following:
            self.log_table.yview_moveto(1.0)

    # ------------------------------------------------------------------
    # Kullanıcı komutları
    # ------------------------------------------------------------------
    def start(self):
        """Yeni bir simülasyon başlatır; önceki durum ve günlük sıfırlanır."""
        if self.simulation is not None and self.simulation.state in (
            SimulationState.RUNNING, SimulationState.PAUSED,
        ):
            return
        try:
            seed = parse_seed(self.seed_var.get())
        except ValueError:
            messagebox.showerror("Geçersiz seed", "Seed boş bırakılmalı ya da bir tam sayı olmalıdır.")
            return
        try:
            rows, cols = parse_grid_size(self.rows_var.get(), self.cols_var.get())
        except ValueError as exc:
            messagebox.showerror("Geçersiz ortam boyutu", str(exc))
            return

        self._cancel_timers()
        self._last_plan_version = 0
        self.simulation = Simulation(seed=seed, rows=rows, cols=cols, agent_type=self.selected_agent_type())
        self._last_action = None
        self._clear_log()
        self._append_log(self._start_message(seed), "info")

        self.simulation.start()
        # Yeni simülasyonda iki zamanlayıcı da tam aralıktan başlar.
        self.step_timer.start(self._read_step_ms())
        self.dirt_timer.start(self._read_dirt_ms())
        self._start_clock()
        self._refresh()

    def toggle_pause(self):
        if self.simulation is None:
            return
        if self.simulation.state is SimulationState.RUNNING:
            # Kalan süreler korunur; duraklama boyunca hiçbir tetikleme olmaz.
            self.step_timer.pause()
            self.dirt_timer.pause()
            self._stop_clock()
            self.simulation.pause()
            self._append_log("Simülasyon duraklatıldı.", "info")
        elif self.simulation.state is SimulationState.PAUSED:
            self.simulation.resume()
            self._append_log("Simülasyon devam ediyor.", "info")
            self.step_timer.resume()
            self.dirt_timer.resume()
            self._start_clock()
        self._refresh()

    def stop(self):
        """Simülasyonu sonlandırır; günlük ekranda kalır."""
        if self.simulation is None or self.simulation.state not in (
            SimulationState.RUNNING, SimulationState.PAUSED,
        ):
            return
        self._cancel_timers()
        self.simulation.stop()
        self._append_log(
            f"Simülasyon kullanıcı tarafından durduruldu. Toplam {self.simulation.step_count} adım.", "info"
        )
        self._refresh()

    def _start_message(self, seed):
        env = self.simulation.environment
        seed_text = f", seed: {seed}" if seed is not None else ""
        agent_text = AGENT_TYPE_TEXT[self.simulation.agent_type]
        header = f"Simülasyon başladı ({env.grid.rows}×{env.grid.cols}{seed_text}, {agent_text})."
        if env.grid.is_two_room:
            rooms = ", ".join(f"{room}: {STATUS_TEXT[env.status_of(room)]}" for room in env.rooms)
            return f"{header} Ajan {env.location} odasında; {rooms}"
        dirty = [room for room in env.rooms if env.status_of(room) is Status.DIRTY]
        dirty_text = ", ".join(dirty) if dirty else "yok"
        return (f"{header} Ajan {env.location} odasında; kirli odalar "
                f"({len(dirty)}/{len(env.rooms)}): {dirty_text}")

    def open_comparison(self):
        """Karşılaştırma penceresini açar (zaten açıksa öne getirir).

        Pencere ana simülasyonla nesne paylaşmaz; ana simülasyon çalışmaya devam eder.
        """
        from compare_window import CompareWindow

        if self.compare_window is not None and not self.compare_window.closed:
            self.compare_window.window.lift()
            return self.compare_window
        try:
            rows, cols = parse_grid_size(self.rows_var.get(), self.cols_var.get())
        except ValueError:
            rows, cols = 4, 4
        self.compare_window = CompareWindow(self.root, rows=rows, cols=cols)
        return self.compare_window

    def selected_agent_type(self):
        """Seçim listesindeki ajan türünün anahtarı."""
        return AGENT_TYPE_BY_TEXT.get(self.agent_var.get(), DEFAULT_AGENT_TYPE)

    def _on_grid_setting_changed(self):
        if not self._is_active():
            self._draw()
            self._update_status()

    def _is_active(self):
        return self.simulation is not None and self.simulation.state in (
            SimulationState.RUNNING, SimulationState.PAUSED,
        )

    def on_close(self):
        self._cancel_timers()
        self.root.destroy()

    def go_home(self):
        """ "Ana Menü": simülasyon ekranı kapatılır ve açılış ekranına dönülür."""
        if self.on_home is not None:
            self.on_home()

    def shutdown(self):
        """Ekranı kapatır; ana pencere açık kalır.

        Çalışan simülasyon durdurulur, bekleyen zamanlayıcılar iptal edilir,
        karşılaştırma penceresi kapatılır, pencereye eklenen kısayollar
        kaldırılır ve ekranın bileşenleri yok edilir.
        """
        self._cancel_timers()
        if self._is_active():
            self.simulation.stop()
        if self.compare_window is not None and not self.compare_window.closed:
            self.compare_window.close()
        self.set_interaction_locked(False)
        for sequence in ("<space>", "<Escape>", "<Configure>"):
            self.root.unbind(sequence)
        for widget in (self.header, self.settings_card, self.board, self.status_card, self.log_card):
            widget.destroy()

    # ------------------------------------------------------------------
    # Etkileşimli rehber için kancalar (rehber guide.py'dedir)
    # ------------------------------------------------------------------
    def guide_targets(self):
        """Rehberin vurguladığı gerçek bileşenler: ``{anahtar: bileşen}``."""
        fields = [frame for frame, _ in self._fields]
        targets = {
            "step": fields[0], "dirt": fields[1], "seed": fields[2], "rows": fields[3], "cols": fields[4],
            "agent": fields[5],
            "start": self.start_button, "pause": self.pause_button, "stop": self.stop_button,
            "compare": self.compare_button,
            "environment": self.env_frame, "model": self.model_frame, "plan": self.model_canvas,
            "status": self.status_card, "log": self.log_card,
        }
        if self.home_button is not None:
            targets["home"] = self.home_button
        return targets

    def prepare_guide_demo(self, seed=GUIDE_DEMO_SEED, steps=GUIDE_DEMO_STEPS, dirt_every=GUIDE_DEMO_DIRT_EVERY):
        """Rehber için örnek: 3×3, amaç tabanlı ajan.

        Gerçek ``Simulation`` API'siyle zamanlayıcı kullanmadan ``steps`` adım
        ilerletilir (her ``dirt_every`` adımda bir kirlenme tetiklemesi) ve
        duraklatılmış bırakılır. Adım ve kirlenme zamanlayıcıları hiç
        başlatılmaz; rehber açıkken simülasyon kendiliğinden ilerlemez.
        """
        self._cancel_timers()
        self.rows_var.set("3")
        self.cols_var.set("3")
        self.agent_var.set(AGENT_TYPE_TEXT["goal"])
        self.seed_var.set(str(seed))
        self._last_plan_version = 0
        self.simulation = Simulation(seed=seed, rows=3, cols=3, agent_type="goal")
        self._last_action = None
        self._clear_log()
        self._append_log(self._start_message(seed), "info")
        self.simulation.start()
        for index in range(1, steps + 1):
            record = self.simulation.step()
            self._last_action = record.action
            self._log_record(record)
            self._log_goal_change()
            if dirt_every and index % dirt_every == 0:
                dirt = self.simulation.dirty_tick()
                if dirt is not None:
                    self._log_record(dirt)
        self.simulation.pause()
        self._refresh()

    def set_interaction_locked(self, locked):
        """Rehber kilidi: bütün etkileşimli bileşenlerin fare, klavye ve kaydırma olayları durdurulur.

        Bileşenlerin durumu ve görünümü değişmez; olay zincirlerinin başına
        bir bağlama etiketi eklenir ve kilit kaldırılınca özgün zincir aynen
        geri yüklenir. Boşluk ve Esc kısayolları kilit süresince kaldırılır.
        """
        if locked == bool(getattr(self, "_locked_bindtags", None)):
            return
        if locked:
            for sequence in GUIDE_LOCKED_EVENTS:
                self.root.bind_class(GUIDE_LOCK_TAG, sequence, lambda _e: "break")
            self._locked_bindtags = {}
            for widget in self._interactive_widgets():
                tags = widget.bindtags()
                self._locked_bindtags[widget] = tags
                widget.bindtags((GUIDE_LOCK_TAG,) + tuple(tags))
            self.root.unbind("<space>")
            self.root.unbind("<Escape>")
            self.root.focus_set()
        else:
            for widget, tags in self._locked_bindtags.items():
                if widget.winfo_exists():
                    widget.bindtags(tags)
            self._locked_bindtags = None
            self.root.bind("<space>", self._on_space_key)
            self.root.bind("<Escape>", self._on_escape_key)

    @property
    def interaction_locked(self):
        return bool(getattr(self, "_locked_bindtags", None))

    def _interactive_widgets(self):
        """Ekranın bütün bileşenleri (kartlar, alanlar, düğmeler, tuvaller, tablo)."""
        found, stack = [], [self.header, self.settings_card, self.board, self.status_card, self.log_card]
        while stack:
            widget = stack.pop()
            found.append(widget)
            stack.extend(widget.winfo_children())
        return found

    def _on_space_key(self, event):
        # Yazı alanlarında boşluk tuşu normal davranışını korur.
        if isinstance(event.widget, (tk.Entry, tk.Spinbox, ttk.Entry, ttk.Spinbox)):
            return None
        self.toggle_pause()
        return "break"

    def _on_escape_key(self, _event):
        self.stop()
        return "break"

    # ------------------------------------------------------------------
    # Zamanlayıcılar (birbirinden bağımsız)
    # ------------------------------------------------------------------
    def _on_step_timer(self):
        if self.simulation is None or not self.simulation.is_running:
            return
        record = self.simulation.step()
        self._last_action = record.action
        self._log_record(record)
        self._log_goal_change()
        self._refresh()
        self.step_timer.start(self._read_step_ms())

    def _log_goal_change(self):
        """Hedef değiştiyse ayrı renkli bir bilgi satırı ekler (adım sayılmaz)."""
        if not agent_has_plan(self.simulation.agent_type):
            return
        plan = self.simulation.agent.plan_snapshot()
        if plan.version != self._last_plan_version and plan.target is not None:
            self._add_log_row(*goal_row(plan, self.simulation.elapsed))
        self._last_plan_version = plan.version

    def _on_dirt_timer(self):
        if self.simulation is None or not self.simulation.is_running:
            return
        record = self.simulation.dirty_tick()
        if record is not None:
            self._log_record(record)
            self._refresh()
        self.dirt_timer.start(self._read_dirt_ms())

    def _cancel_timers(self):
        self.step_timer.cancel()
        self.dirt_timer.cancel()
        self._stop_clock()

    # ------------------------------------------------------------------
    # Süre göstergesi (adım ve kirlenme zamanlayıcılarından bağımsız)
    # ------------------------------------------------------------------
    def _start_clock(self):
        self._stop_clock()
        self._clock_job = self.root.after(CLOCK_REFRESH_MS, self._on_clock_tick)

    def _stop_clock(self):
        if self._clock_job is not None:
            self.root.after_cancel(self._clock_job)
            self._clock_job = None

    def _on_clock_tick(self):
        """Yalnızca durum satırını yeniler; simülasyona dokunmaz.

        Süre simülasyonun kendi saatinden okunduğu için duraklamada durur,
        durdurulunca sabitlenir.
        """
        if self.simulation is None or not self.simulation.is_running:
            self._stop_clock()
            return
        self._update_status()
        # _start_clock bekleyen bir tetikleme varsa önce onu iptal eder; böylece
        # hiçbir zaman sahipsiz (iptal edilemeyen) bir tetikleme kalmaz.
        self._start_clock()

    def _read_step_ms(self):
        """Ayar alanını okur; geçersizse son geçerli değeri kullanır."""
        try:
            value = int(float(self.step_var.get()))
        except ValueError:
            return self._step_ms
        self._step_ms = max(MIN_STEP_MS, min(MAX_STEP_MS, value))
        return self._step_ms

    def _read_dirt_seconds(self):
        try:
            value = float(self.dirt_var.get().replace(",", "."))
        except ValueError:
            return self._dirt_seconds
        self._dirt_seconds = max(MIN_DIRT_SECONDS, min(MAX_DIRT_SECONDS, value))
        return self._dirt_seconds

    def _read_dirt_ms(self):
        return round(self._read_dirt_seconds() * 1000)

    # ------------------------------------------------------------------
    # Günlük
    # ------------------------------------------------------------------
    def _append_log(self, message, kind="info"):
        """Bilgi satırı ekler (ör. "Simülasyon duraklatıldı."); açıklama sütununda gösterilir."""
        elapsed = format_elapsed(self.simulation.elapsed) if self.simulation is not None else ""
        self._add_log_row(kind, ("", elapsed, "", "", "", message))

    def _log_record(self, record):
        """Simülasyon kaydını (adım ya da kirlenme) tabloya ekler."""
        self._add_log_row(*record_row(record))

    def _add_log_row(self, kind, values):
        """Satır ekler; ekranda en fazla MAX_LOG_LINES kayıt tutar.

        Otomatik kaydırma yalnızca kullanıcı zaten en alttaysa yapılır; geçmiş
        kayıtlara bakan kullanıcının görünümü korunur.
        """
        table = self.log_table
        # Pencere görünür değilken (ör. simge durumunda) kaydırma konumu
        # güvenilir değildir; bu durumda takip sürdürülür.
        at_bottom = not table.winfo_viewable() or table.yview()[1] >= 0.999
        self._log_rows.append(table.insert("", "end", values=values, tags=(kind,)))
        self._trim_log()
        self._log_following = at_bottom
        if at_bottom:
            table.yview_moveto(1.0)

    def _log_line_count(self):
        """Ekrandaki kayıt sayısı (kaldırma bilgisi satırı hariç)."""
        return len(self._log_rows)

    def _trim_log(self):
        excess = len(self._log_rows) - MAX_LOG_LINES
        if excess <= 0:
            return
        self.log_table.delete(*[self._log_rows.popleft() for _ in range(excess)])
        self._log_trimmed += excess
        values = ("", "", "", "", "", LOG_TRIM_NOTICE.format(count=self._log_trimmed))
        if self._trim_notice is None:            # bilgi satırı en üstte kalır
            self._trim_notice = self.log_table.insert("", 0, values=values, tags=("info",))
        else:
            self.log_table.item(self._trim_notice, values=values)

    def _clear_log(self):
        self.log_table.delete(*self.log_table.get_children())
        self._log_rows.clear()
        self._trim_notice = None
        self._log_trimmed = 0
        self._log_following = True

    def clear_log_view(self):
        """"Ekranı Temizle": yalnızca ekrandaki satırları siler; simülasyonun günlüğüne dokunmaz."""
        self._clear_log()
        self._append_log(LOG_CLEARED_NOTICE)

    def log_entries(self):
        """Ekrandaki satırlar: ``[(tür, değerler), …]`` (test ve inceleme için)."""
        table = self.log_table
        return [(table.item(iid, "tags")[0], tuple(str(v) for v in table.item(iid, "values")))
                for iid in table.get_children()]

    # ------------------------------------------------------------------
    # Görünüm güncelleme
    # ------------------------------------------------------------------
    def _refresh(self):
        self._update_buttons()
        self._update_status()
        self._draw()

    def _update_buttons(self):
        state = self.simulation.state if self.simulation else None
        active = state in (SimulationState.RUNNING, SimulationState.PAUSED)
        self.start_button.configure(state="disabled" if active else "normal")
        self.pause_button.configure(
            state="normal" if active else "disabled",
            text=(theme.button_text("resume", "Devam") if state is SimulationState.PAUSED
                  else theme.button_text("pause", "Duraklat")),
        )
        self.stop_button.configure(state="normal" if active else "disabled")
        # Grid boyutu çalışırken ve duraklatılmışken değiştirilemez.
        for spin in (self.rows_spin, self.cols_spin):
            spin.configure(state="disabled" if active else "normal")
        # Ajan türü de çalışırken ve duraklatılmışken değiştirilemez.
        self.agent_combo.configure(state="disabled" if active else "readonly")

    def _update_status(self):
        grid, env, agent_type = self._displayed()
        sim = self.simulation if self._is_active() or env is not None else None
        rooms = len(grid.rooms)
        state = sim.state if sim is not None else SimulationState.READY
        values = {
            "state": state.value,
            "agent": AGENT_TYPE_TEXT[agent_type],
            "size": f"{grid.rows} × {grid.cols}",
            "dirty": "—", "known": "—", "target": "—",
            "steps": "0", "cleans": "0", "moves": "0", "elapsed": format_elapsed(0),
        }
        if sim is not None:
            statuses = sim.environment.statuses().values()
            values["dirty"] = f"{sum(1 for status in statuses if status is Status.DIRTY)} / {rooms}"
            values.update(steps=str(sim.step_count), cleans=str(sim.clean_count), moves=str(sim.move_count),
                          elapsed=format_elapsed(sim.elapsed))
            if agent_has_model(sim.agent_type):
                values["known"] = f"{len(sim.agent.model_snapshot().observations)} / {rooms}"
            if agent_has_plan(sim.agent_type):
                plan = sim.agent.plan_snapshot()
                if plan.target is not None:
                    remaining = f"{len(plan.route)} adım" if plan.route else "ulaşıldı"
                    values["target"] = f"{plan.target.room} · {remaining}"
        for key, value in values.items():
            if self.stat_vars[key].get() != value:
                self.stat_vars[key].set(value)
        icon, color = STATE_STYLE[state]
        self._stat_values["state"].configure(foreground=theme.COLORS[color])
        if "state" in self._stat_icons:
            self._stat_icons["state"].configure(text=theme.ICON_GLYPHS[icon], foreground=theme.COLORS[color])
        self._layout_stats()

    def _displayed(self):
        """Çizilecek grid, ortam ve ajan türü: ``(grid, env, agent_type)``.

        Simülasyon çalışıyor ya da duraklatılmışsa onun ortamı çizilir. Aksi
        halde ayarlardaki boyut ve ajan türü önizlenir; durdurulmuş
        simülasyonun ortamı, ayarlar değişmediyse son hâliyle ekranda kalır.
        """
        if self._is_active():
            env = self.simulation.environment
            return env.grid, env, self.simulation.agent_type
        agent_type = self.selected_agent_type()
        try:
            grid = Grid(*parse_grid_size(self.rows_var.get(), self.cols_var.get()))
        except ValueError:
            grid = Grid(DEFAULT_ROWS, DEFAULT_COLS)
        sim = self.simulation
        if sim is not None and sim.environment.grid == grid and sim.agent_type == agent_type:
            return grid, sim.environment, agent_type
        return grid, None, agent_type

    def _displayed_snapshot(self, env):
        """Model panelinin kaynağı: yalnızca ajanın salt okunur model kopyası."""
        if env is not None and self.simulation is not None and agent_has_model(self.simulation.agent_type):
            return self.simulation.agent.model_snapshot()
        return empty_snapshot()

    def _displayed_plan(self, env):
        """Hedef/rota çiziminin kaynağı: yalnızca ajanın salt okunur plan kopyası."""
        if env is not None and self.simulation is not None and agent_has_plan(self.simulation.agent_type):
            return self.simulation.agent.plan_snapshot()
        return None

    def _draw(self):
        grid, env, agent_type = self._displayed()
        plan = self._displayed_plan(env)
        count = f"{grid.rows} × {grid.cols} oda"
        self.env_count.configure(text=count)
        self.env_legend.set_items(environment_legend_items(agent_has_plan(agent_type)))
        self._draw_environment(grid, env, plan)
        show_model = agent_has_model(agent_type)
        if show_model != (self.model_frame.winfo_manager() == "grid"):
            if show_model:
                self.model_frame.grid()
            else:
                self.model_frame.grid_remove()
            self._layout_board()
        if show_model:
            if grid.is_two_room:
                self.model_note.pack(side="bottom", fill="x", before=self.model_canvas)
            else:
                self.model_note.pack_forget()
            self.model_count.configure(text=count)
            self.model_legend.set_items(model_legend_items(stale_threshold(grid), agent_has_plan(agent_type)),
                                        MODEL_AGE_NOTE)
            self._draw_model(grid, self._displayed_snapshot(env), plan)

    def _draw_model(self, grid, snapshot, plan=None):
        """İç modeli çizer. Yalnızca ``snapshot`` ve ``plan`` kopyaları kullanılır; ortam okunmaz."""
        threshold = stale_threshold(grid)
        draw_model(self.model_canvas, grid, snapshot, plan, threshold,
                   (self.CANVAS_WIDTH // 2, self.CANVAS_HEIGHT))

    def _draw_environment(self, grid, env, plan=None):
        draw_environment(self.canvas, grid, env, plan, (self.CANVAS_WIDTH, self.CANVAS_HEIGHT))


def configure_window_size(root, scale):
    """Başlangıç boyutu kullanılabilir ekrana göre; en küçük boyut altı bölümü gösterir."""
    width = min(round(1440 * scale), int(root.winfo_screenwidth() * 0.94))
    height = min(round(1040 * scale), int(root.winfo_screenheight() * 0.90))
    root.geometry(f"{width}x{height}")
    root.minsize(min(round(MIN_WINDOW_WIDTH * scale), width), min(round(MIN_WINDOW_HEIGHT * scale), height))


DIAGNOSTIC_LOG_ENV = "ROBOT_DIAG_LOG"


def install_diagnostics(root, path):
    """Tanılama günlüğü (yalnızca ``ROBOT_DIAG_LOG`` tanımlıyken kullanılır).

    Pencereli EXE'de hata çıktısı görünmez. Bu günlük, geri çağırmalardaki
    Python hatalarını ve Tcl arka plan hatalarını (ör. "invalid command name")
    dosyaya yazar. Program davranışını değiştirmez. Yazma fonksiyonunu döndürür.
    """
    import traceback

    def write(line):
        try:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass

    def on_exception(exc_type, value, tb):
        write("HATA (geri çağırma): " + "".join(traceback.format_exception(exc_type, value, tb)).strip())

    root.report_callback_exception = on_exception
    root.tk.createcommand("robot_background_error", lambda message: write(f"HATA (Tcl): {message}"))
    root.tk.eval("proc bgerror {message} {robot_background_error $message}")
    return write


class AppShell:
    """Tek ana pencerede ekranlar arası geçiş: açılış, rehber ve simülasyon.

    Her geçişte önceki ekran tamamen kapatılır (zamanlayıcılar, kısayollar,
    bileşenler); yeni bir Tk kök penceresi oluşturulmaz.
    """

    def __init__(self, root, diagnostics=None):
        self.root = root
        self.scale = ui_scale(root)
        self.style = theme.setup(root, self.scale)
        self.screen = None          # WelcomeScreen
        self.app = None             # VacuumApp (simülasyon ekranı; rehberde de kullanılır)
        self.tour = None            # guide.GuideTour (etkileşimli rehber)
        self.diagnostics = diagnostics  # tanılama günlüğüne yazan fonksiyon (isteğe bağlı)
        root.title(APP_TITLE)
        configure_window_size(root, self.scale)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.show_welcome()

    @property
    def current(self):
        """Gösterilen ekran: "welcome", "guide" ya da "simulation"."""
        if self.tour is not None:
            return "guide"
        return "simulation" if self.app is not None else "welcome"

    def show_welcome(self):
        from welcome import WelcomeScreen
        self._clear()
        self.screen = WelcomeScreen(self.root, self.scale, on_play=self.show_simulation,
                                    on_guide=self.show_guide)
        self._report("açılış ekranı")

    def show_guide(self, dim=True):
        """Etkileşimli rehber: gerçek simülasyon ekranı, zamanlayıcısız örnek ve üstünde rehber katmanı."""
        from guide import GuideTour
        from welcome import GUIDE_STEPS
        self._clear()
        self.app = VacuumApp(self.root, on_home=self.show_welcome)
        self.app.prepare_guide_demo()
        self.tour = GuideTour(self.app, GUIDE_STEPS, on_home=self.show_welcome, on_play=self.show_simulation,
                              scale=self.scale, dim=dim)
        self._report("rehber")

    def show_simulation(self):
        self._clear()
        self.app = VacuumApp(self.root, on_home=self.show_welcome)
        self._report("simülasyon")

    def _clear(self):
        if self.tour is not None:           # önce rehber katmanı ve kilitler kaldırılır
            self.tour.destroy()
            self.tour = None
        if self.app is not None:
            self.app.shutdown()
            self.app = None
        if self.screen is not None:
            self.screen.destroy()
            self.screen = None
        # Önceki ekranın satır/sütun ağırlıkları sıfırlanır.
        for index in range(5):
            self.root.rowconfigure(index, weight=0, minsize=0)
        self.root.columnconfigure(0, weight=0)

    def close(self):
        self._clear()
        self._report("kapanış (ekranlar kaldırıldı)")
        self.root.destroy()

    def _report(self, event):
        """Tanılama günlüğüne geçişi, bekleyen tetiklemeleri ve açık alt pencereleri yazar."""
        if self.diagnostics is None:
            return
        jobs = self.root.tk.splitlist(self.root.tk.call("after", "info"))
        scripts = [str(self.root.tk.splitlist(self.root.tk.call("after", "info", job))[0]) for job in jobs]
        windows = [w.winfo_class() for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)]
        self.diagnostics(f"{event}: ekran={self.current} bekleyen_after={len(jobs)} {scripts} "
                         f"alt_pencereler={windows}")


def run():
    enable_windows_dpi_awareness()
    root = tk.Tk()
    log_path = os.environ.get(DIAGNOSTIC_LOG_ENV)
    write = install_diagnostics(root, log_path) if log_path else None
    if write is None:
        AppShell(root)
    else:
        write("başlangıç")
        AppShell(root, diagnostics=write)
    root.mainloop()
