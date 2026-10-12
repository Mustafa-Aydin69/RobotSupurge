"""Ajan karşılaştırma penceresi.

Ölçümleri ``comparison.ComparisonJob`` yapar; bu pencere yalnızca ayarları
alır, işi Tkinter ana döngüsünde küçük zaman dilimleriyle ilerletir ve
sonuçları tablo ve çubuk grafik olarak gösterir. Ana simülasyonla hiçbir
nesne paylaşmaz; pencerenin açılması, iptali ya da kapanması ana simülasyonu
etkilemez.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from agents import AGENT_TYPES
from comparison import AGENT_KEYS, ComparisonJob, ComparisonSettings

SLICE_BUDGET_SECONDS = 0.015    # her ana döngü diliminde en fazla bu kadar hesaplama
SLICE_GAP_MS = 1                # dilimler arasında arayüze bırakılan süre

AGENT_COLORS = {"reflex": "#8c8c8c", "model": "#2e7dbf", "goal": "#7b3fbf"}
MODE_TEXT = {"common": "Ortak", "independent": "Bağımsız"}

METHOD_TEXT = (
    "Ölçüm yöntemi\n"
    "• Aynı seed, üç ajana da aynı başlangıç odasını ve oda durumlarını verir.\n"
    "• Kapsama adımı: kirlenme kapalıyken bütün odaların ilk kez algılandığı adım "
    "(başlangıç odası 1. adımda algılanır). Adım sınırı içinde tamamlanmayan koşular "
    "ayrıca sayılır; değerleri bilinmediği için ortalamaya katılmaz, ortalama yerine "
    "\"≥\" ile bir alt sınır gösterilir.\n"
    "• Temiz oda oranı: kirlenme açıkken her adımdan sonra ölçülen temiz oda oranının "
    "ortalaması; ± seed'ler arası standart sapma.\n"
    "• Hareket / temizleme: bir temizlik için yapılan hareket sayısı; hiç temizlik "
    "yapılmayan koşuda tanımsızdır ve ayrıca sayılır.\n"
    "• Ortak kirlenme: her tetiklemede her oda için ajandan bağımsız bir sayı çekilir; "
    "üç ajan aynı kirlenme denemeleriyle karşılaşır. Kirli odaya deneme etkisiz kaldığı "
    "için gerçekleşen kirlenmeler yine ajanların temizliklerine göre farklılaşabilir.\n"
    "• Bağımsız kirlenme: simülasyonun kendi mekanizması; ajanlar farklı hareket ettiği "
    "için karşılaştıkları kirlenmeler aynı olmaz.\n"
    "Sonuçlar ölçüldüğü gibi gösterilir; bir ajanın üstünlüğü varsayılmaz."
)


# ----------------------------------------------------------------------
# Biçimlendirme (saf fonksiyonlar)
# ----------------------------------------------------------------------
def format_number(value, digits=1):
    return f"{value:.{digits}f}".replace(".", ",")


def format_coverage(coverage):
    """Kapsama özetini (ortalama, ortanca, en kötü, tamamlanan) metne çevirir."""
    cap = coverage.cap
    if coverage.mean is not None:
        mean = format_number(coverage.mean)
    else:
        mean = f"≥ {format_number(coverage.mean_lower_bound)}"
    median = format_number(coverage.median) if coverage.median is not None else f"> {cap}"
    worst = str(coverage.worst) if coverage.worst is not None else f"> {cap}"
    total = coverage.completed + coverage.incomplete
    completed = f"{coverage.completed}/{total}"
    return mean, median, worst, completed


def format_clean_ratio(summary):
    text = format_number(summary.clean_ratio_mean, 3)
    if summary.clean_ratio_stdev is not None:
        text += f" ± {format_number(summary.clean_ratio_stdev, 3)}"
    return text


def format_moves_per_clean(summary):
    if summary.moves_per_clean_mean is None:
        return "tanımsız"
    text = format_number(summary.moves_per_clean_mean, 2)
    if summary.moves_per_clean_undefined:
        text += f" ({summary.moves_per_clean_undefined} koşuda tanımsız)"
    return text


def parse_settings(values):
    """Metin alanlarını ComparisonSettings'e çevirir; hata mesajları Türkçe."""
    labels = {"rows": "Satır", "cols": "Sütun", "seed_start": "İlk seed", "seed_count": "Seed sayısı",
              "steps": "Adım sayısı", "dirt_every": "Kirlenme sıklığı"}
    numbers = {}
    for key, label in labels.items():
        try:
            numbers[key] = int(str(values[key]).strip())
        except ValueError:
            raise ValueError(f"{label} bir tam sayı olmalıdır.") from None
    return ComparisonSettings(dirt_mode=values["dirt_mode"], **numbers).validate()


# ----------------------------------------------------------------------
# Pencere
# ----------------------------------------------------------------------
class CompareWindow:
    """Üç ajanı aynı koşullarda karşılaştıran ayrı pencere."""

    def __init__(self, master, rows=4, cols=4):
        self.window = tk.Toplevel(master)
        self.window.title("Ajan Karşılaştırması")
        self.window.minsize(720, 640)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.job = None
        self._job_after = None
        self.closed = False

        self._build_settings(rows, cols)
        self._build_controls()
        self._build_table()
        self._build_chart()
        self._build_method()
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(3, weight=1)
        self._update_buttons()

    # ------------------------------------------------------------------
    def _build_settings(self, rows, cols):
        frame = ttk.LabelFrame(self.window, text="Ayarlar", padding=8)
        frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        self.vars = {}
        fields = [
            ("rows", "Satır:", rows, 0, 0), ("cols", "Sütun:", cols, 0, 2),
            ("seed_start", "İlk seed:", 0, 0, 4), ("seed_count", "Seed sayısı:", 20, 0, 6),
            ("steps", "Adım sayısı:", 3000, 1, 0), ("dirt_every", "Kirlenme: her", 4, 1, 2),
        ]
        self.entries = []
        for key, label, default, row, col in fields:
            ttk.Label(frame, text=label).grid(row=row, column=col, sticky="w", pady=2)
            var = tk.StringVar(value=str(default))
            entry = ttk.Entry(frame, textvariable=var, width=7)
            entry.grid(row=row, column=col + 1, sticky="w", padx=(4, 14), pady=2)
            self.vars[key] = var
            self.entries.append(entry)
        ttk.Label(frame, text="adımda %30").grid(row=1, column=4, sticky="w")

        self.vars["dirt_mode"] = tk.StringVar(value="common")
        mode_frame = ttk.Frame(frame)
        mode_frame.grid(row=1, column=5, columnspan=3, sticky="w")
        ttk.Label(mode_frame, text="Kirlenme biçimi:").pack(side="left")
        self.mode_buttons = []
        for mode in ("common", "independent"):
            button = ttk.Radiobutton(mode_frame, text=MODE_TEXT[mode], value=mode,
                                     variable=self.vars["dirt_mode"])
            button.pack(side="left", padx=(6, 0))
            self.mode_buttons.append(button)

    def _build_controls(self):
        frame = ttk.Frame(self.window, padding=(10, 4))
        frame.grid(row=1, column=0, sticky="ew")
        self.start_button = ttk.Button(frame, text="Başlat", command=self.start)
        self.cancel_button = ttk.Button(frame, text="İptal", command=self.cancel)
        self.start_button.pack(side="left")
        self.cancel_button.pack(side="left", padx=6)
        self.progress = ttk.Progressbar(frame, length=220, mode="determinate")
        self.progress.pack(side="left", padx=(10, 6))
        self.status_var = tk.StringVar(value="Ayarları seçip Başlat'a basın.")
        ttk.Label(frame, textvariable=self.status_var).pack(side="left")

    def _build_table(self):
        columns = ("agent", "completed", "mean", "median", "worst", "ratio", "moves")
        headings = ("Ajan", "Tamamlanan kapsama", "Kapsama ort.", "Kapsama ortanca", "Kapsama en kötü",
                    "Temiz oda oranı (± ss)", "Hareket / temizleme")
        widths = (150, 120, 95, 110, 105, 140, 170)
        self.table = ttk.Treeview(self.window, columns=columns, show="headings", height=3)
        for column, heading, width in zip(columns, headings, widths):
            self.table.heading(column, text=heading)
            self.table.column(column, width=width, anchor="center", stretch=True)
        self.table.grid(row=2, column=0, sticky="ew", padx=10, pady=4)

    def _build_chart(self):
        self.chart = tk.Canvas(self.window, height=210, background="white", highlightthickness=0)
        self.chart.grid(row=3, column=0, sticky="nsew", padx=10, pady=4)
        self.chart.bind("<Configure>", lambda _e: self._draw_chart())

    def _build_method(self):
        label = ttk.Label(self.window, text=METHOD_TEXT, foreground="#444", justify="left",
                          font=("Segoe UI", 8))
        label.grid(row=4, column=0, sticky="ew", padx=10, pady=(4, 10))
        label.bind("<Configure>", lambda e: label.configure(wraplength=max(200, e.width - 4)))

    # ------------------------------------------------------------------
    def settings_values(self):
        return {key: var.get() for key, var in self.vars.items()}

    def start(self):
        if self.job is not None and not self.job.finished and not self.job.cancelled:
            return
        try:
            settings = parse_settings(self.settings_values())
            self.job = ComparisonJob(settings)
        except ValueError as exc:
            messagebox.showerror("Geçersiz ayar", str(exc), parent=self.window)
            return
        self._clear_results()
        self.progress.configure(maximum=self.job.total, value=0)
        self.status_var.set(f"Hesaplanıyor… 0/{self.job.total}")
        self._update_buttons()
        self._job_after = self.window.after(SLICE_GAP_MS, self._tick)

    def _tick(self):
        self._job_after = None
        if self.job is None or self.job.cancelled:
            return
        finished = self.job.advance(SLICE_BUDGET_SECONDS)
        self.progress.configure(value=self.job.done)
        if finished:
            self.status_var.set(
                f"Tamamlandı: {self.job.total} koşu "
                f"(en uzun hesaplama dilimi {self.job.longest_slice * 1000:.0f} ms)."
            )
            self._show_results()
            self._update_buttons()
            return
        self.status_var.set(f"Hesaplanıyor… {self.job.done}/{self.job.total}")
        self._job_after = self.window.after(SLICE_GAP_MS, self._tick)

    def cancel(self):
        """Yeni dilim planlanmaz, bekleyen dilim iptal edilir, kısmi sonuç gösterilmez."""
        if self._job_after is not None:
            self.window.after_cancel(self._job_after)
            self._job_after = None
        if self.job is not None and not self.job.finished:
            self.job.cancel()
            self._clear_results()
            self.status_var.set("İptal edildi; kısmi sonuçlar gösterilmiyor.")
        self._update_buttons()

    def close(self):
        self.cancel()
        self.closed = True
        self.window.destroy()

    @property
    def running(self):
        return self.job is not None and not self.job.finished and not self.job.cancelled

    def _update_buttons(self):
        running = self.running
        self.start_button.configure(state="disabled" if running else "normal")
        self.cancel_button.configure(state="normal" if running else "disabled")
        for widget in self.entries + self.mode_buttons:
            widget.configure(state="disabled" if running else "normal")

    # ------------------------------------------------------------------
    def _clear_results(self):
        for item in self.table.get_children():
            self.table.delete(item)
        self._summaries = None
        self._draw_chart()

    def _show_results(self):
        self._summaries = self.job.summary()
        for summary in self._summaries:
            mean, median, worst, completed = format_coverage(summary.coverage)
            self.table.insert("", "end", iid=summary.agent_type, values=(
                AGENT_TYPES[summary.agent_type].name, completed, mean, median, worst,
                format_clean_ratio(summary), format_moves_per_clean(summary),
            ))
        self._draw_chart()

    def _draw_chart(self):
        c = self.chart
        c.delete("all")
        summaries = getattr(self, "_summaries", None)
        width = max(c.winfo_width(), 400)
        height = max(c.winfo_height(), 180)
        if not summaries:
            c.create_text(width / 2, height / 2, text="Sonuçlar burada çubuk grafik olarak gösterilecek.",
                          fill="#777")
            return
        half = width / 2
        self._draw_bar_group(
            0, half, height, "Kapsama ortanca adımı (kısa daha hızlı)",
            [(s.agent_type, s.coverage.median, f"> {s.coverage.cap}") for s in summaries],
            maximum=max([s.coverage.cap if s.coverage.median is None else s.coverage.median
                         for s in summaries] + [1]),
            fmt=lambda v: format_number(v),
        )
        self._draw_bar_group(
            half, width, height, "Ortalama temiz oda oranı (yüksek daha temiz)",
            [(s.agent_type, s.clean_ratio_mean, None) for s in summaries],
            maximum=1.0, fmt=lambda v: format_number(v, 3),
        )

    def _draw_bar_group(self, x0, x1, height, title, items, maximum, fmt):
        c = self.chart
        c.create_text((x0 + x1) / 2, 14, text=title, font=("Segoe UI", 9, "bold"))
        top, bottom = 34, height - 34
        slot = (x1 - x0 - 40) / len(items)
        for index, (agent_type, value, unknown_text) in enumerate(items):
            left = x0 + 20 + index * slot + slot * 0.2
            right = left + slot * 0.6
            known = value is not None
            bar_value = value if known else maximum
            bar_top = bottom - (bottom - top) * min(1.0, bar_value / maximum)
            c.create_rectangle(left, bar_top, right, bottom, fill=AGENT_COLORS[agent_type],
                               outline="", stipple="" if known else "gray50",
                               tags=("bar", f"bar:{agent_type}"))
            c.create_text((left + right) / 2, bar_top - 9, text=fmt(value) if known else unknown_text,
                          font=("Segoe UI", 8))
            c.create_text((left + right) / 2, bottom + 12, text=AGENT_TYPES[agent_type].name,
                          font=("Segoe UI", 8))
        c.create_line(x0 + 15, bottom, x1 - 15, bottom, fill="#999")
