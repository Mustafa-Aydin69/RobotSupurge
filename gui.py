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

import sys
import tkinter as tk
from tkinter import messagebox, ttk

from agents import AGENT_TYPES, DEFAULT_AGENT_TYPE, GOAL_DIRTY, GOAL_EXPLORE, GOAL_UNKNOWN
from environment import MAX_GRID_SIZE, MIN_GRID_SIZE, Action, Grid, Status
from simulation import DirtRecord, Simulation, SimulationState
import theme
from timers import PausableTimer  # noqa: F401  (testler ve geriye uyumluluk için dışa aktarılır)
from views import (  # noqa: F401  (testler ve geriye uyumluluk için dışa aktarılır)
    COLOR_GOAL, MODEL_CATEGORY_FILL, MODEL_CATEGORY_TEXT, MODEL_CLEAN, MODEL_DIRTY, MODEL_INFERRED,
    MODEL_PANEL_TITLE, MODEL_STALE, MODEL_UNKNOWN, STATUS_TEXT, compute_layout, draw_environment,
    draw_model, empty_snapshot, environment_legend_text, model_category, model_legend_text,
    stale_threshold,
)

# ----------------------------------------------------------------------
# Varsayılanlar ve sınırlar
# ----------------------------------------------------------------------
DEFAULT_STEP_MS = 700
MIN_STEP_MS, MAX_STEP_MS = 100, 5000
DEFAULT_DIRT_SECONDS = 3.0
CLOCK_REFRESH_MS = 200          # süre göstergesinin yenilenme aralığı
SIDE_BY_SIDE_MIN_WIDTH = 760    # iki panelin yan yana dizildiği en küçük tahta genişliği
MAX_LOG_LINES = 10000           # ekrandaki günlüğün en fazla satır sayısı
LOG_TRIM_NOTICE = ("… Eski kayıtlar ekrandan kaldırıldı ({count} satır). "
                   "Simülasyonun kendi günlüğü eksiksiz korunuyor.")
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


class VacuumApp:
    """Robot süpürge simülasyonunun ana penceresi."""

    CANVAS_WIDTH = 560    # başlangıç boyutu; pencereyle birlikte büyür
    CANVAS_HEIGHT = 240
    CANVAS_MIN_HEIGHT = 120   # tuvalin istediği yükseklik; pencere küçükse günlüğe yer kalır
    LOG_MIN_HEIGHT = 110      # günlüğün dar pencerede de görünür kalan en küçük yüksekliği

    def __init__(self, root):
        self.root = root
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

        root.title("Robot Süpürge Ajanı")
        # Piksel cinsinden boyutlar ekran ölçeğiyle büyütülür; ekrana sığmayacaksa sınırlanır.
        self.scale = ui_scale(root)
        self.style = theme.setup(root, self.scale)
        width = min(round(820 * self.scale), int(root.winfo_screenwidth() * 0.95))
        height = min(round(800 * self.scale), int(root.winfo_screenheight() * 0.90))
        root.geometry(f"{width}x{height}")
        root.minsize(min(round(680 * self.scale), width), min(round(620 * self.scale), height))
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_settings()
        self._build_controls()
        self._build_canvas()
        self._build_status()
        self._build_log()

        # Tuval ve günlük pencereyle birlikte büyür; ayarlar ve düğmeler her
        # zaman üstte görünür kalır.
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=3)
        root.rowconfigure(4, weight=2, minsize=round(self.LOG_MIN_HEIGHT * self.scale))

        root.bind("<space>", self._on_space_key)
        root.bind("<Escape>", self._on_escape_key)

        self._refresh()

    # ------------------------------------------------------------------
    # Arayüz bileşenleri
    # ------------------------------------------------------------------
    def _build_settings(self):
        frame = ttk.LabelFrame(self.root, text="Ayarlar", padding=8)
        frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))

        ttk.Label(frame, text="Adım aralığı (ms):").grid(row=0, column=0, sticky="w")
        self.step_var = tk.StringVar(value=str(DEFAULT_STEP_MS))
        ttk.Spinbox(
            frame, textvariable=self.step_var, from_=MIN_STEP_MS, to=MAX_STEP_MS,
            increment=100, width=7,
        ).grid(row=0, column=1, padx=(4, 16))

        ttk.Label(frame, text="Kirlenme aralığı (sn):").grid(row=0, column=2, sticky="w")
        self.dirt_var = tk.StringVar(value=str(DEFAULT_DIRT_SECONDS))
        ttk.Spinbox(
            frame, textvariable=self.dirt_var, from_=MIN_DIRT_SECONDS, to=MAX_DIRT_SECONDS,
            increment=0.5, width=6,
        ).grid(row=0, column=3, padx=(4, 16))

        ttk.Label(frame, text="Seed (isteğe bağlı):").grid(row=0, column=4, sticky="w")
        self.seed_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.seed_var, width=10).grid(row=0, column=5, padx=(4, 0))

        ttk.Label(frame, text="Satır:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.rows_var = tk.StringVar(value=str(DEFAULT_ROWS))
        self.rows_spin = ttk.Spinbox(
            frame, textvariable=self.rows_var, from_=MIN_GRID_SIZE, to=MAX_GRID_SIZE, width=7,
        )
        self.rows_spin.grid(row=1, column=1, padx=(4, 16), pady=(6, 0))

        ttk.Label(frame, text="Sütun:").grid(row=1, column=2, sticky="w", pady=(6, 0))
        self.cols_var = tk.StringVar(value=str(DEFAULT_COLS))
        self.cols_spin = ttk.Spinbox(
            frame, textvariable=self.cols_var, from_=MIN_GRID_SIZE, to=MAX_GRID_SIZE, width=6,
        )
        self.cols_spin.grid(row=1, column=3, padx=(4, 16), pady=(6, 0))

        ttk.Label(frame, text="Ajan türü:").grid(row=1, column=4, sticky="w", pady=(6, 0))
        self.agent_var = tk.StringVar(value=AGENT_TYPE_TEXT[DEFAULT_AGENT_TYPE])
        self.agent_combo = ttk.Combobox(
            frame, textvariable=self.agent_var, values=list(AGENT_TYPE_TEXT.values()),
            state="readonly", width=20,
        )
        self.agent_combo.grid(row=1, column=5, padx=(4, 0), pady=(6, 0), sticky="w")
        self.agent_var.trace_add("write", lambda *_: self._on_grid_setting_changed())

        # Simülasyon çalışmıyorken boyut değişikliği tuvalde önizlenir.
        self.rows_var.trace_add("write", lambda *_: self._on_grid_setting_changed())
        self.cols_var.trace_add("write", lambda *_: self._on_grid_setting_changed())

        ttk.Label(
            frame,
            text=("Aralıklar çalışırken de değiştirilebilir. Satır/sütun (1–6, en az 2 oda) "
                  "ve ajan türü yalnızca Başlat'ta uygulanır."),
            foreground="#555",
        ).grid(row=2, column=0, columnspan=6, sticky="w", pady=(6, 0))

    def _build_controls(self):
        frame = ttk.Frame(self.root, padding=(10, 4))
        frame.grid(row=1, column=0, sticky="ew")

        # Düğmeler odak almaz; böylece Boşluk tuşu yalnızca kısayol olarak çalışır.
        self.start_button = ttk.Button(frame, text="Başlat", command=self.start, takefocus=False)
        self.pause_button = ttk.Button(frame, text="Duraklat", command=self.toggle_pause, takefocus=False)
        self.stop_button = ttk.Button(frame, text="Durdur", command=self.stop, takefocus=False)
        self.start_button.pack(side="left")
        self.pause_button.pack(side="left", padx=6)
        self.stop_button.pack(side="left")
        self.compare_button = ttk.Button(frame, text="Ajanları Karşılaştır", command=self.open_comparison,
                                         takefocus=False)
        self.compare_button.pack(side="left", padx=(16, 0))

        ttk.Label(frame, text="Kısayollar: Boşluk = Duraklat/Devam, Esc = Durdur", foreground="#555").pack(
            side="right"
        )

    def _build_canvas(self):
        # Gerçek ortam ve iç model iki ayrı panelde. Geniş alanda yan yana,
        # dar ve uzun alanda alt alta yerleştirilir.
        self.board = ttk.Frame(self.root)
        self.board.grid(row=2, column=0, sticky="nsew", padx=10, pady=4)
        self._board_layout = None   # (model görünür mü, yan yana mı)

        self.env_frame = ttk.LabelFrame(self.board, text="Gerçek ortam", padding=2)
        self.canvas = tk.Canvas(
            self.env_frame, width=self.CANVAS_WIDTH, height=self.CANVAS_MIN_HEIGHT,
            background="white", highlightthickness=0,
        )
        self.env_legend = ttk.Label(self.env_frame, text=environment_legend_text(),
                                    foreground="#555", font=("Segoe UI", 8))
        self.env_legend.bind("<Configure>", lambda e: self.env_legend.configure(wraplength=max(120, e.width - 4)))
        self.env_legend.pack(side="bottom", fill="x")
        self.canvas.pack(fill="both", expand=True)

        self.model_frame = ttk.LabelFrame(self.board, text=MODEL_PANEL_TITLE, padding=2)
        self.model_canvas = tk.Canvas(
            self.model_frame, width=self.CANVAS_WIDTH // 2, height=self.CANVAS_MIN_HEIGHT,
            background="white", highlightthickness=0,
        )
        self.model_legend_var = tk.StringVar()
        self.model_legend = ttk.Label(self.model_frame, textvariable=self.model_legend_var,
                                      foreground="#555", font=("Segoe UI", 8))
        self.model_note = ttk.Label(self.model_frame, text=TWO_ROOM_MODEL_NOTE,
                                    foreground="#9a5b13", font=("Segoe UI", 8))
        for label in (self.model_legend, self.model_note):
            label.bind("<Configure>", lambda e, w=label: w.configure(wraplength=max(120, e.width - 4)))
        self.model_legend.pack(side="bottom", fill="x")
        self.model_canvas.pack(side="top", fill="both", expand=True)

        self.env_frame.grid(row=0, column=0, sticky="nsew")
        self.model_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.model_frame.grid_remove()

        # Pencere yeniden boyutlandırıldığında yerleşim ve grid yeniden hesaplanır.
        self.board.bind("<Configure>", lambda _event: self._layout_board())
        self.canvas.bind("<Configure>", lambda _event: self._draw())
        self.model_canvas.bind("<Configure>", lambda _event: self._draw())

    def _layout_board(self):
        """Panelleri yerleştirir.

        Model paneli gizliyse gerçek ortam bütün alanı kullanır. Görünürse
        tahta yeterince genişse yan yana, değilse alt alta dizilir.
        """
        width = self.board.winfo_width()
        model_visible = self.model_frame.winfo_manager() == "grid"
        side_by_side = width >= round(SIDE_BY_SIDE_MIN_WIDTH * self.scale)
        layout = (model_visible, side_by_side)
        if layout == self._board_layout:
            return
        self._board_layout = layout
        for index in range(2):
            self.board.columnconfigure(index, weight=0, minsize=0)
            self.board.rowconfigure(index, weight=0)
        if not model_visible:
            self.board.columnconfigure(0, weight=1)
            self.board.rowconfigure(0, weight=1)
        elif side_by_side:
            self.board.columnconfigure(0, weight=3)
            # Panel başlığı dar pencerede de tam okunabilsin.
            self.board.columnconfigure(1, weight=2, minsize=round(300 * self.scale))
            self.board.rowconfigure(0, weight=1)
            self.model_frame.grid_configure(row=0, column=1, padx=(8, 0), pady=0)
        else:
            self.board.columnconfigure(0, weight=1)
            self.board.rowconfigure(0, weight=3)
            self.board.rowconfigure(1, weight=2)
            self.model_frame.grid_configure(row=1, column=0, padx=0, pady=(6, 0))

    def _build_status(self):
        self.status_var = tk.StringVar()
        label = ttk.Label(self.root, textvariable=self.status_var, padding=(10, 2))
        label.grid(row=3, column=0, sticky="ew")
        # Dar pencerede durum satırı kesilmek yerine alt satıra geçer.
        label.bind("<Configure>", lambda event: label.configure(wraplength=max(200, event.width - 20)))

    def _build_log(self):
        frame = ttk.LabelFrame(self.root, text="Algı ve eylem günlüğü", padding=4)
        frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=(4, 10))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(frame, height=8, wrap="none", font=("Consolas", 10), state="disabled")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
        x_scrollbar = ttk.Scrollbar(frame, orient="horizontal", command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=scrollbar.set, xscrollcommand=x_scrollbar.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")

        self.log_text.tag_configure("dirt", foreground="#9a5b13")
        self.log_text.tag_configure("info", foreground="#1d70b8")
        self.log_text.tag_configure("goal", foreground=COLOR_GOAL)

        # Günlük alanı yeniden boyutlanınca (ör. pencere ya da durum satırı
        # değişince) en son kaydı izleyen görünüm en altta kalır. Kullanıcı
        # kaydırınca takip durumu kullanıcının konumuna göre güncellenir.
        self.log_text.bind("<Configure>", lambda _e: self._keep_log_position())
        for widget, sequences in ((self.log_text, ("<MouseWheel>", "<Prior>", "<Next>", "<Control-End>",
                                                   "<Control-Home>")),
                                  (scrollbar, ("<ButtonRelease-1>",))):
            for sequence in sequences:
                widget.bind(sequence, lambda _e: self.root.after_idle(self._update_log_following), add="+")

    def _update_log_following(self):
        if self.log_text.winfo_exists():
            self._log_following = self.log_text.yview()[1] >= 0.999

    def _keep_log_position(self):
        if self._log_following:
            self.log_text.yview_moveto(1.0)

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

    def _is_active(self):
        return self.simulation is not None and self.simulation.state in (
            SimulationState.RUNNING, SimulationState.PAUSED,
        )

    def on_close(self):
        self._cancel_timers()
        self.root.destroy()

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
        self._append_log(format_record(record))
        self._log_goal_change()
        self._refresh()
        self.step_timer.start(self._read_step_ms())

    def _log_goal_change(self):
        """Hedef değiştiyse ayrı renkli bir bilgi satırı ekler (adım sayılmaz)."""
        if not agent_has_plan(self.simulation.agent_type):
            return
        plan = self.simulation.agent.plan_snapshot()
        if plan.version != self._last_plan_version and plan.target is not None:
            self._append_log(format_goal_change(plan), "goal")
        self._last_plan_version = plan.version

    def _on_dirt_timer(self):
        if self.simulation is None or not self.simulation.is_running:
            return
        record = self.simulation.dirty_tick()
        if record is not None:
            self._append_log(format_record(record), "dirt")
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
    def _append_log(self, line, tag=None):
        """Satır ekler; ekranda en fazla MAX_LOG_LINES kayıt tutar.

        Otomatik kaydırma yalnızca kullanıcı zaten en alttaysa yapılır; geçmiş
        kayıtlara bakan kullanıcının görünümü korunur.
        """
        text = self.log_text
        # Pencere görünür değilken (ör. simge durumunda) kaydırma konumu
        # güvenilir değildir; bu durumda takip sürdürülür.
        at_bottom = not text.winfo_viewable() or text.yview()[1] >= 0.999
        text.configure(state="normal")
        text.insert("end", line + "\n", tag or ())
        self._trim_log()
        text.configure(state="disabled")
        self._log_following = at_bottom
        if at_bottom:
            # see("end") son satır kısmen görünürken kaydırmayabilir; tam alta inilir.
            text.yview_moveto(1.0)

    def _log_line_count(self):
        """Ekrandaki kayıt sayısı (kaldırma bilgisi satırı hariç)."""
        lines = int(self.log_text.index("end-1c").split(".")[0]) - 1
        return lines - (1 if self._log_trimmed else 0)

    def _trim_log(self):
        excess = self._log_line_count() - MAX_LOG_LINES
        if excess <= 0:
            return
        text = self.log_text
        first = 2 if self._log_trimmed else 1    # bilgi satırı en üstte kalır
        text.delete(f"{first}.0", f"{first + excess}.0")
        self._log_trimmed += excess
        notice = LOG_TRIM_NOTICE.format(count=self._log_trimmed) + "\n"
        if first == 2:
            text.delete("1.0", "2.0")
        text.insert("1.0", notice, "info")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self._log_trimmed = 0
        self._log_following = True

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
            text="Devam" if state is SimulationState.PAUSED else "Duraklat",
        )
        self.stop_button.configure(state="normal" if active else "disabled")
        # Grid boyutu çalışırken ve duraklatılmışken değiştirilemez.
        for spin in (self.rows_spin, self.cols_spin):
            spin.configure(state="disabled" if active else "normal")
        # Ajan türü de çalışırken ve duraklatılmışken değiştirilemez.
        self.agent_combo.configure(state="disabled" if active else "readonly")

    def _update_status(self):
        sim = self.simulation
        if sim is None:
            self.status_var.set("Durum: Hazır — başlamak için 'Başlat' düğmesine basın.")
            return
        last = ACTION_TEXT[self._last_action] if self._last_action else "—"
        env = sim.environment
        dirty = sum(1 for status in env.statuses().values() if status is Status.DIRTY)
        known = ""
        if agent_has_model(sim.agent_type):
            known = f"Bilinen oda: {len(sim.agent.model_snapshot().observations)}/{len(env.rooms)}   |   "
        if agent_has_plan(sim.agent_type):
            plan = sim.agent.plan_snapshot()
            if plan.target is not None:
                remaining = f"kalan rota: {len(plan.route)} adım" if plan.route else "hedefe ulaşıldı"
                known += f"Hedef: {plan.target.room} ({GOAL_KIND_TEXT[plan.target.kind]}), {remaining}   |   "
        self.status_var.set(
            f"Durum: {sim.state.value}   |   {AGENT_TYPE_TEXT[sim.agent_type]}   |   "
            f"Ortam: {env.grid.rows}×{env.grid.cols}   |   "
            f"Kirli oda: {dirty}/{len(env.rooms)}   |   {known}Adım: {sim.step_count}   |   "
            f"Temizleme: {sim.clean_count}   |   Hareket: {sim.move_count}   |   "
            f"Süre: {format_elapsed(sim.elapsed)}   |   Son eylem: {last}"
        )

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
                self.model_note.pack(side="bottom", fill="x", before=self.model_legend)
            else:
                self.model_note.pack_forget()
            self._draw_model(grid, self._displayed_snapshot(env), plan)

    def _draw_model(self, grid, snapshot, plan=None):
        """İç modeli çizer. Yalnızca ``snapshot`` ve ``plan`` kopyaları kullanılır; ortam okunmaz."""
        threshold = stale_threshold(grid)
        self.model_legend_var.set(model_legend_text(threshold))
        draw_model(self.model_canvas, grid, snapshot, plan, threshold,
                   (self.CANVAS_WIDTH // 2, self.CANVAS_HEIGHT))

    def _draw_environment(self, grid, env, plan=None):
        draw_environment(self.canvas, grid, env, plan, (self.CANVAS_WIDTH, self.CANVAS_HEIGHT))


def run():
    enable_windows_dpi_awareness()
    root = tk.Tk()
    VacuumApp(root)
    root.mainloop()
