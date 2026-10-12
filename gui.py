"""Tkinter arayüzü.

Projede Tkinter'ı yalnızca bu modül kullanır. Arayüz simülasyonun mantığını
içermez; ``Simulation`` nesnesini iki bağımsız zamanlayıcıyla sürer:

* adım zamanlayıcısı ``Simulation.step()`` çağırır,
* kirlenme zamanlayıcısı ``Simulation.dirty_tick()`` çağırır.

Zamanlayıcılar duraklatıldığında kalan sürelerini korur ve devam edildiğinde
o süreden devam eder.
"""

import time
import tkinter as tk
from tkinter import messagebox, ttk

from agents import AGENT_TYPES, DEFAULT_AGENT_TYPE
from environment import MAX_GRID_SIZE, MIN_GRID_SIZE, Action, Grid, Status
from simulation import DirtRecord, Simulation, SimulationState

# ----------------------------------------------------------------------
# Varsayılanlar ve sınırlar
# ----------------------------------------------------------------------
DEFAULT_STEP_MS = 700
MIN_STEP_MS, MAX_STEP_MS = 100, 5000
DEFAULT_DIRT_SECONDS = 3.0
MIN_DIRT_SECONDS, MAX_DIRT_SECONDS = 0.5, 60.0
DEFAULT_ROWS, DEFAULT_COLS = 1, 2

# ----------------------------------------------------------------------
# Arayüz metinleri (iç adlar İngilizce, ekranda Türkçe)
# ----------------------------------------------------------------------
STATUS_TEXT = {Status.CLEAN: "Temiz", Status.DIRTY: "Kirli"}
AGENT_TYPE_TEXT = {key: cls.name for key, cls in AGENT_TYPES.items()}
AGENT_TYPE_BY_TEXT = {text: key for key, text in AGENT_TYPE_TEXT.items()}
ACTION_TEXT = {
    Action.CLEAN: "Temizle",
    Action.RIGHT: "Sağa git",
    Action.LEFT: "Sola git",
    Action.UP: "Yukarı git",
    Action.DOWN: "Aşağı git",
}

# ----------------------------------------------------------------------
# Renkler
# ----------------------------------------------------------------------
COLOR_CLEAN = "#cdeac0"
COLOR_DIRTY = "#c8a27a"
COLOR_DIRT_SPOT = "#7a5230"
COLOR_ROBOT = "#2f3e4e"
COLOR_ROBOT_RING = "#5fa8d3"
COLOR_ACTIVE_BORDER = "#1d70b8"

# Kirli odadaki lekelerin oda içindeki göreli konumları (x, y, yarıçap)
DIRT_SPOTS = [(0.18, 0.30, 9), (0.70, 0.22, 7), (0.32, 0.72, 11), (0.82, 0.66, 8), (0.55, 0.45, 6)]


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


def compute_layout(width, height, rows, cols):
    """Odaları verilen tuval alanına sığdıran yerleşimi hesaplar.

    ``(left, top, cell_w, cell_h, gap)`` döndürür. Grid tuvalin ortasına
    yerleştirilir; boşluklar grid büyüdükçe küçülür.
    """
    gap = max(6.0, min(20.0, 60.0 / max(rows, cols)))
    cell_w = max(1.0, (width - gap * (cols + 1)) / cols)
    cell_h = max(1.0, (height - gap * (rows + 1)) / rows)
    # Çok uzun ya da çok yassı odalar oluşmasın.
    cell_w = min(cell_w, cell_h * 1.6)
    cell_h = min(cell_h, cell_w * 1.2)
    grid_w = cols * cell_w + (cols - 1) * gap
    grid_h = rows * cell_h + (rows - 1) * gap
    return (width - grid_w) / 2, (height - grid_h) / 2, cell_w, cell_h, gap


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


class VacuumApp:
    """Robot süpürge simülasyonunun ana penceresi."""

    CANVAS_WIDTH = 560    # başlangıç boyutu; pencereyle birlikte büyür
    CANVAS_HEIGHT = 240

    def __init__(self, root):
        self.root = root
        self.simulation = None
        self.step_timer = PausableTimer(root, self._on_step_timer)
        self.dirt_timer = PausableTimer(root, self._on_dirt_timer)
        self._step_ms = DEFAULT_STEP_MS
        self._dirt_seconds = DEFAULT_DIRT_SECONDS
        self._last_action = None

        root.title("Robot Süpürge Ajanı")
        root.geometry("820x800")
        root.minsize(680, 620)
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
        root.rowconfigure(4, weight=2)

        root.bind("<space>", self._on_space_key)
        root.bind("<Escape>", self._on_escape_key)

        self._update_buttons()
        self._draw()

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

        ttk.Label(frame, text="Kısayollar: Boşluk = Duraklat/Devam, Esc = Durdur", foreground="#555").pack(
            side="right"
        )

    def _build_canvas(self):
        self.canvas = tk.Canvas(
            self.root, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT,
            background="white", highlightthickness=0,
        )
        self.canvas.grid(row=2, column=0, sticky="nsew", padx=10, pady=4)
        # Pencere yeniden boyutlandırıldığında grid yeniden hesaplanır.
        self.canvas.bind("<Configure>", lambda _event: self._draw())

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
        self.simulation = Simulation(seed=seed, rows=rows, cols=cols, agent_type=self.selected_agent_type())
        self._last_action = None
        self._clear_log()
        self._append_log(self._start_message(seed), "info")

        self.simulation.start()
        # Yeni simülasyonda iki zamanlayıcı da tam aralıktan başlar.
        self.step_timer.start(self._read_step_ms())
        self.dirt_timer.start(self._read_dirt_ms())
        self._refresh()

    def toggle_pause(self):
        if self.simulation is None:
            return
        if self.simulation.state is SimulationState.RUNNING:
            # Kalan süreler korunur; duraklama boyunca hiçbir tetikleme olmaz.
            self.step_timer.pause()
            self.dirt_timer.pause()
            self.simulation.pause()
            self._append_log("Simülasyon duraklatıldı.", "info")
        elif self.simulation.state is SimulationState.PAUSED:
            self.simulation.resume()
            self._append_log("Simülasyon devam ediyor.", "info")
            self.step_timer.resume()
            self.dirt_timer.resume()
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
        self._refresh()
        self.step_timer.start(self._read_step_ms())

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
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n", tag or ())
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

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
        self.status_var.set(
            f"Durum: {sim.state.value}   |   {AGENT_TYPE_TEXT[sim.agent_type]}   |   "
            f"Ortam: {env.grid.rows}×{env.grid.cols}   |   "
            f"Kirli oda: {dirty}/{len(env.rooms)}   |   Adım: {sim.step_count}   |   "
            f"Temizleme: {sim.clean_count}   |   Hareket: {sim.move_count}   |   "
            f"Süre: {format_elapsed(sim.elapsed)}   |   Son eylem: {last}"
        )

    def _displayed(self):
        """Çizilecek grid ve (varsa) ortam.

        Simülasyon çalışıyor ya da duraklatılmışsa onun ortamı çizilir. Aksi
        halde ayarlardaki boyut önizlenir; durdurulmuş simülasyonun ortamı,
        ayarlar değişmediyse son hâliyle ekranda kalır.
        """
        if self._is_active():
            env = self.simulation.environment
            return env.grid, env
        try:
            grid = Grid(*parse_grid_size(self.rows_var.get(), self.cols_var.get()))
        except ValueError:
            grid = Grid(DEFAULT_ROWS, DEFAULT_COLS)
        if self.simulation is not None and self.simulation.environment.grid == grid:
            return grid, self.simulation.environment
        return grid, None

    def _draw(self):
        c = self.canvas
        c.delete("all")
        width = c.winfo_width() if c.winfo_width() > 1 else self.CANVAS_WIDTH
        height = c.winfo_height() if c.winfo_height() > 1 else self.CANVAS_HEIGHT

        grid, env = self._displayed()
        left0, top0, cell_w, cell_h, gap = compute_layout(width, height, grid.rows, grid.cols)
        size = min(cell_w, cell_h)
        title_font = ("Segoe UI", max(7, min(13, int(size * 0.14))), "bold")
        status_font = ("Segoe UI", max(7, min(11, int(size * 0.11))))
        border = 2 if size >= 50 else 1
        title_y = max(9, size * 0.09)

        for room in grid.rooms:
            row, col = grid.position_of(room)
            left = left0 + col * (cell_w + gap)
            top = top0 + row * (cell_h + gap)
            right, bottom = left + cell_w, top + cell_h
            status = env.status_of(room) if env else None
            is_current = env is not None and env.location == room

            fill = {Status.CLEAN: COLOR_CLEAN, Status.DIRTY: COLOR_DIRTY}.get(status, "#eeeeee")
            c.create_rectangle(
                left, top, right, bottom, fill=fill,
                outline=COLOR_ACTIVE_BORDER if is_current else "#666",
                width=border * 2 if is_current else border,
                tags=("room", f"room:{room}"),
            )
            if status is Status.DIRTY:
                scale = size / 200
                for rx, ry, radius in DIRT_SPOTS:
                    x = left + rx * cell_w
                    # Grid'de lekeler oda adının altındaki bölgeye yerleştirilir.
                    y = top + (ry if grid.is_two_room else 0.3 + ry * 0.6) * cell_h
                    r = max(2.0, radius * scale)
                    y = max(y, top + title_y + 8 + r)  # leke oda adının üstüne binmesin
                    c.create_oval(x - r, y - r, x + r, y + r, fill=COLOR_DIRT_SPOT, outline="", tags=("dirt",))

            title = f"{room} Odası" if grid.is_two_room else room
            c.create_text((left + right) / 2, top + title_y, text=title, font=title_font)
            if size >= 60:
                status_label = STATUS_TEXT[status] if status else "—"
                c.create_text((left + right) / 2, bottom - max(8, size * 0.08), text=status_label, font=status_font)

            if is_current:
                # Küçük odalarda durum yazısı yok; robot oda adından uzaklaşır.
                offset = 0.03 if size >= 60 else 0.18
                self._draw_robot((left + right) / 2, (top + bottom) / 2 + size * offset, size)

    def _draw_robot(self, x, y, size):
        c = self.canvas
        r = max(6.0, min(30.0, size * 0.22))
        ring = max(1, round(r / 7.5))
        c.create_oval(x - r, y - r, x + r, y + r, fill=COLOR_ROBOT, outline=COLOR_ROBOT_RING,
                      width=ring, tags=("robot",))
        eye = r * 0.27
        c.create_oval(x - eye, y - r + r * 0.2, x + eye, y - r + r * 0.2 + 2 * eye,
                      fill=COLOR_ROBOT_RING, outline="", tags=("robot",))
        if r >= 18:
            c.create_text(x, y + r * 0.27, text="Robot", fill="white",
                          font=("Segoe UI", max(7, int(r * 0.3)), "bold"), tags=("robot",))


def run():
    root = tk.Tk()
    VacuumApp(root)
    root.mainloop()
