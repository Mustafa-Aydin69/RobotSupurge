"""Tkinter arayüzü.

Projede Tkinter'ı yalnızca bu modül kullanır. Arayüz simülasyonun mantığını
içermez; ``Simulation`` nesnesini iki bağımsız zamanlayıcıyla sürer:

* adım zamanlayıcısı ``Simulation.step()`` çağırır,
* kirlenme zamanlayıcısı ``Simulation.dirty_tick()`` çağırır.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from environment import ROOMS, Action, Status
from simulation import DirtRecord, Simulation, SimulationState

# ----------------------------------------------------------------------
# Varsayılanlar ve sınırlar
# ----------------------------------------------------------------------
DEFAULT_STEP_MS = 700
MIN_STEP_MS, MAX_STEP_MS = 100, 5000
DEFAULT_DIRT_SECONDS = 3.0
MIN_DIRT_SECONDS, MAX_DIRT_SECONDS = 0.5, 60.0

# ----------------------------------------------------------------------
# Arayüz metinleri (iç adlar İngilizce, ekranda Türkçe)
# ----------------------------------------------------------------------
STATUS_TEXT = {Status.CLEAN: "Temiz", Status.DIRTY: "Kirli"}
ACTION_TEXT = {Action.CLEAN: "Temizle", Action.RIGHT: "Sağa git", Action.LEFT: "Sola git"}

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


class VacuumApp:
    """Robot süpürge simülasyonunun ana penceresi."""

    CANVAS_WIDTH = 560
    CANVAS_HEIGHT = 240
    ROOM_MARGIN = 20

    def __init__(self, root):
        self.root = root
        self.simulation = None
        self._step_job = None
        self._dirt_job = None
        self._step_ms = DEFAULT_STEP_MS
        self._dirt_seconds = DEFAULT_DIRT_SECONDS
        self._last_action = None

        root.title("Robot Süpürge Ajanı")
        root.minsize(620, 600)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_settings()
        self._build_controls()
        self._build_canvas()
        self._build_status()
        self._build_log()

        root.columnconfigure(0, weight=1)
        root.rowconfigure(4, weight=1)

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

        ttk.Label(
            frame,
            text="Aralıklar çalışma sırasında da değiştirilebilir; bir sonraki tetiklemede geçerli olur.",
            foreground="#555",
        ).grid(row=1, column=0, columnspan=6, sticky="w", pady=(6, 0))

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
        self.canvas.grid(row=2, column=0, padx=10, pady=4)

    def _build_status(self):
        self.status_var = tk.StringVar()
        ttk.Label(self.root, textvariable=self.status_var, padding=(10, 2)).grid(row=3, column=0, sticky="w")

    def _build_log(self):
        frame = ttk.LabelFrame(self.root, text="Algı ve eylem günlüğü", padding=4)
        frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=(4, 10))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(frame, height=12, wrap="none", font=("Consolas", 10), state="disabled")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

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

        self._cancel_timers()
        self.simulation = Simulation(seed=seed)
        self._last_action = None
        self._clear_log()

        env = self.simulation.environment
        rooms = ", ".join(f"{room}: {STATUS_TEXT[env.status_of(room)]}" for room in ROOMS)
        seed_text = f" (seed: {seed})" if seed is not None else ""
        self._append_log(f"Simülasyon başladı{seed_text}. Ajan {env.location} odasında; {rooms}", "info")

        self.simulation.start()
        self._schedule_timers()
        self._refresh()

    def toggle_pause(self):
        if self.simulation is None:
            return
        if self.simulation.state is SimulationState.RUNNING:
            self._cancel_timers()
            self.simulation.pause()
            self._append_log("Simülasyon duraklatıldı.", "info")
        elif self.simulation.state is SimulationState.PAUSED:
            self.simulation.resume()
            self._append_log("Simülasyon devam ediyor.", "info")
            self._schedule_timers()
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
    def _schedule_timers(self):
        self._schedule_step()
        self._schedule_dirt()

    def _schedule_step(self):
        self._step_job = self.root.after(self._read_step_ms(), self._on_step_timer)

    def _schedule_dirt(self):
        delay_ms = int(self._read_dirt_seconds() * 1000)
        self._dirt_job = self.root.after(delay_ms, self._on_dirt_timer)

    def _on_step_timer(self):
        self._step_job = None
        if self.simulation is None or not self.simulation.is_running:
            return
        record = self.simulation.step()
        self._last_action = record.action
        self._append_log(format_record(record))
        self._refresh()
        self._schedule_step()

    def _on_dirt_timer(self):
        self._dirt_job = None
        if self.simulation is None or not self.simulation.is_running:
            return
        record = self.simulation.dirty_tick()
        if record is not None:
            self._append_log(format_record(record), "dirt")
            self._refresh()
        self._schedule_dirt()

    def _cancel_timers(self):
        for job in (self._step_job, self._dirt_job):
            if job is not None:
                self.root.after_cancel(job)
        self._step_job = None
        self._dirt_job = None

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

    def _update_status(self):
        sim = self.simulation
        if sim is None:
            self.status_var.set("Durum: Hazır — başlamak için 'Başlat' düğmesine basın.")
            return
        last = ACTION_TEXT[self._last_action] if self._last_action else "—"
        self.status_var.set(
            f"Durum: {sim.state.value}   |   Adım: {sim.step_count}   |   "
            f"Temizleme: {sim.clean_count}   |   Hareket: {sim.move_count}   |   "
            f"Süre: {format_elapsed(sim.elapsed)}   |   Son eylem: {last}"
        )

    def _draw(self):
        c = self.canvas
        c.delete("all")
        margin = self.ROOM_MARGIN
        room_width = (self.CANVAS_WIDTH - margin * (len(ROOMS) + 1)) / len(ROOMS)
        top, bottom = margin, self.CANVAS_HEIGHT - margin

        env = self.simulation.environment if self.simulation else None
        for index, room in enumerate(ROOMS):
            left = margin + index * (room_width + margin)
            right = left + room_width
            status = env.status_of(room) if env else None
            is_current = env is not None and env.location == room

            fill = {Status.CLEAN: COLOR_CLEAN, Status.DIRTY: COLOR_DIRTY}.get(status, "#eeeeee")
            c.create_rectangle(
                left, top, right, bottom, fill=fill,
                outline=COLOR_ACTIVE_BORDER if is_current else "#666",
                width=4 if is_current else 2,
            )
            if status is Status.DIRTY:
                for rx, ry, radius in DIRT_SPOTS:
                    x = left + rx * room_width
                    y = top + ry * (bottom - top)
                    c.create_oval(x - radius, y - radius, x + radius, y + radius, fill=COLOR_DIRT_SPOT, outline="")

            c.create_text((left + right) / 2, top + 18, text=f"{room} Odası", font=("Segoe UI", 13, "bold"))
            status_label = STATUS_TEXT[status] if status else "—"
            c.create_text((left + right) / 2, bottom - 16, text=status_label, font=("Segoe UI", 11))

            if is_current:
                self._draw_robot((left + right) / 2, (top + bottom) / 2 + 6)

    def _draw_robot(self, x, y):
        c = self.canvas
        r = 30
        c.create_oval(x - r, y - r, x + r, y + r, fill=COLOR_ROBOT, outline=COLOR_ROBOT_RING, width=4)
        c.create_oval(x - 8, y - r + 6, x + 8, y - r + 22, fill=COLOR_ROBOT_RING, outline="")
        c.create_text(x, y + 8, text="Robot", fill="white", font=("Segoe UI", 9, "bold"))


def run():
    root = tk.Tk()
    VacuumApp(root)
    root.mainloop()
