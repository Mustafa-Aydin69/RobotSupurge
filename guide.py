"""Etkileşimli "Nasıl Oynanır?" rehberi.

Rehber gerçek simülasyon ekranının (``gui.VacuumApp``) üzerinde çalışır:

* Ana pencerenin üstüne yarı saydam lacivert bir karartma katmanı konur.
  Vurgulanan bileşenin çevresi bu katmanda saydam bir "delik" olarak
  bırakılır; bileşen net görünür.
* Deliğin kenarında opak, mavi bir vurgu çerçevesi bulunur.
* Açıklama kutusu ayrı, kenarlıksız bir penceredir; adım numarası, başlık,
  kısa açıklama ve Geri / İleri / Ana Menü düğmelerini içerir. Kutunun yeri
  ``place_card`` ile hedefi kapatmayacak biçimde hesaplanır.
* Rehber süresince ekranın bütün bileşenleri ``VacuumApp`` kilidiyle
  etkileşime kapalıdır; simülasyon zamanlayıcıları çalışmaz.

Saydamlık desteklenmeyen sistemlerde karartma katmanı kullanılmaz; vurgu
çerçevesi ve açıklama kutusu yine gösterilir.

Klavye: Sağ ok / Enter = İleri, Sol ok = Geri, Esc = Ana Menü.
"""

import tkinter as tk
from tkinter import ttk

import theme
from welcome import HOME_TEXT, PLAY_TEXT, GuideNavigator

DIM_ALPHA = 0.55                # karartma katmanının saydamlığı (0 = görünmez, 1 = opak)
DIM_COLOR = "#0b1a33"           # lacivert karartma rengi
HOLE_KEY = "#ff00fe"            # katmanda tamamen saydam bırakılan renk (vurgu deliği)
HOLE_PAD = 9                    # deliğin hedefin çevresindeki payı (iki çerçeve bu payın içinde)
RING_WIDTH = 3                  # vurgu çerçevesinin kalınlığı
RING_COLOR = "#2f80ff"
GLOW_WIDTH = 3                  # dış çerçevenin içindeki açık mavi ikinci çerçeve
GLOW_COLOR = "#a8c9ff"          # soluk (devre dışı) bileşenlerde de vurgu belirgin kalır
CARD_GAP = 14                   # açıklama kutusu ile hedef arasındaki boşluk
WINDOW_MARGIN = 12              # açıklama kutusunun pencere kenarına en yakın uzaklığı
CARD_WIDTHS = (400, 340, 280)   # sırayla denenen kutu genişlikleri (%100 ölçekte)
REPOSITION_DELAY_MS = 40        # pencere değişikliğinden sonra yeniden yerleşim gecikmesi
FINISH_HOME_TEXT = "Ana Menü'ye Dön"
KEY_SEQUENCES = ("<Right>", "<Return>", "<KP_Enter>", "<Left>", "<Escape>")


# ----------------------------------------------------------------------
# Yerleşim hesabı (arayüzden bağımsız, test edilebilir)
# ----------------------------------------------------------------------
def intersects(a, b):
    """İki dikdörtgen ``(x0, y0, x1, y1)`` kesişiyor mu? (Kenar teması kesişme sayılmaz.)"""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def overlap_area(a, b):
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    return max(0, width) * max(0, height)


def place_card(target, window, card, gap=CARD_GAP, margin=WINDOW_MARGIN):
    """Açıklama kutusunu hedefi kapatmadan pencereye yerleştirir.

    ``target``: hedefin pencere içindeki dikdörtgeni ``(x0, y0, x1, y1)``,
    ``window``: pencere boyutu ``(genişlik, yükseklik)``, ``card``: kutu boyutu.
    Sırayla hedefin altı, üstü, sağı ve solu denenir. Uygun konum varsa
    ``(x, y, taraf)`` döner; hiçbiri uygun değilse ``None``.
    """
    tx0, ty0, tx1, ty1 = target
    width, height = window
    card_w, card_h = card

    def clamp(value, low, high):
        return low if high < low else max(low, min(value, high))

    center_x = clamp((tx0 + tx1) / 2 - card_w / 2, margin, width - margin - card_w)
    center_y = clamp((ty0 + ty1) / 2 - card_h / 2, margin, height - margin - card_h)
    candidates = (
        ("below", center_x, ty1 + gap),
        ("above", center_x, ty0 - gap - card_h),
        ("right", tx1 + gap, center_y),
        ("left", tx0 - gap - card_w, center_y),
    )
    for side, x, y in candidates:
        rect = (x, y, x + card_w, y + card_h)
        inside = x >= margin and y >= margin and rect[2] <= width - margin and rect[3] <= height - margin
        if inside and not intersects(rect, target):
            return round(x), round(y), side
    return None


def fallback_card(target, window, card, margin=WINDOW_MARGIN):
    """Hiçbir standart konum uygun değilse hedefle en az örtüşen konum: ``(x, y, "overlap")``."""
    width, height = window
    card_w, card_h = card
    xs = (margin, (width - card_w) / 2, width - margin - card_w)
    ys = (margin, (height - card_h) / 2, height - margin - card_h)
    center = ((target[0] + target[2]) / 2, (target[1] + target[3]) / 2)

    def cost(position):
        x, y = position
        rect = (x, y, x + card_w, y + card_h)
        distance = ((x + card_w / 2 - center[0]) ** 2 + (y + card_h / 2 - center[1]) ** 2) ** 0.5
        return overlap_area(rect, target), -distance

    x, y = min(((max(margin, x), max(margin, y)) for x in xs for y in ys), key=cost)
    return round(x), round(y), "overlap"


# ----------------------------------------------------------------------
# Rehber
# ----------------------------------------------------------------------
class GuideTour:
    """Gerçek simülasyon ekranı üzerinde adım adım rehber."""

    def __init__(self, app, steps, on_home=None, on_play=None, scale=1.0, dim=True):
        self.app = app
        self.root = app.root
        self.scale = scale
        self.navigator = GuideNavigator(steps)
        self.on_home = on_home
        self.on_play = on_play
        self.targets = app.guide_targets()
        missing = [step.section for step in self.navigator.steps if step.section not in self.targets]
        if missing:
            raise ValueError(f"Rehber hedefi bulunamadı: {', '.join(missing)}")
        self._job = None
        self._hidden = False
        self.card_side = None
        app.set_interaction_locked(True)

        self.overlay = self._create_overlay() if dim else None
        self.ring = [tk.Frame(self.root, background=RING_COLOR, borderwidth=0, highlightthickness=0,
                              **theme.tk_options()) for _ in range(4)]
        self.glow = [tk.Frame(self.root, background=GLOW_COLOR, borderwidth=0, highlightthickness=0,
                              **theme.tk_options()) for _ in range(4)]
        self._build_card()

        # Pencere taşındığında, boyutlandığında ya da küçültüldüğünde katmanlar izler.
        # Önceki bağlamalar saklanır ve rehber kapanınca aynen geri yüklenir.
        sequences = ("<Configure>", "<Unmap>", "<Map>") + KEY_SEQUENCES
        self._saved_bindings = {sequence: self.root.bind(sequence) for sequence in sequences}
        self.root.bind("<Configure>", self._on_root_configure, add="+")
        self.root.bind("<Unmap>", self._on_root_unmap, add="+")
        self.root.bind("<Map>", self._on_root_map, add="+")
        for widget in (self.root, self.card) + ((self.overlay,) if self.overlay else ()):
            widget.bind("<Right>", lambda _e: self.next())
            widget.bind("<Return>", lambda _e: self.next())
            widget.bind("<KP_Enter>", lambda _e: self.next())
            widget.bind("<Left>", lambda _e: self.back())
            widget.bind("<Escape>", lambda _e: self.home())
        self.show_step(0)

    # ------------------------------------------------------------------
    def _create_overlay(self):
        overlay = tk.Toplevel(self.root, background=DIM_COLOR, **theme.tk_options())
        overlay.withdraw()
        overlay.overrideredirect(True)
        try:
            overlay.attributes("-alpha", DIM_ALPHA)
            overlay.attributes("-transparentcolor", HOLE_KEY)
        except tk.TclError:               # saydamlık desteklenmiyor: karartma kullanılmaz
            overlay.destroy()
            return None
        overlay.transient(self.root)
        self.dim_canvas = tk.Canvas(overlay, background=DIM_COLOR, highlightthickness=0, borderwidth=0,
                                    **theme.tk_options())
        self.dim_canvas.pack(fill="both", expand=True)
        return overlay

    def _build_card(self):
        c = theme.COLORS
        px = self._px
        self.card = tk.Toplevel(self.root, background=c["card"], highlightthickness=1,
                                highlightbackground=c["hero_border"], **theme.tk_options())
        self.card.withdraw()
        self.card.overrideredirect(True)
        self.card.transient(self.root)
        body = ttk.Frame(self.card, style="Card.TFrame", padding=px(18))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)

        top = ttk.Frame(body, style="Card.TFrame")
        top.grid(row=0, column=0, sticky="ew")
        self.position_label = ttk.Label(top, style="CardNote.TLabel")
        self.position_label.pack(side="left")
        self.dots = tk.Canvas(top, height=px(10), background=c["card"], highlightthickness=0, borderwidth=0,
                              **theme.tk_options())
        self.dots.pack(side="right", padx=(px(12), 0))
        self.title_label = ttk.Label(body, style="GuideTitle.TLabel")
        self.title_label.grid(row=1, column=0, sticky="w", pady=(px(8), px(6)))
        self.body_label = ttk.Label(body, style="GuideBody.TLabel", justify="left")
        self.body_label.grid(row=2, column=0, sticky="w")

        buttons = ttk.Frame(body, style="Card.TFrame")
        buttons.grid(row=3, column=0, sticky="ew", pady=(px(14), 0))
        self.back_button = ttk.Button(buttons, text=theme.button_text("back", "Geri"), command=self.back,
                                      takefocus=False, width=-8, **theme.button_options("secondary"))
        next_text = "İleri" if theme.text_only() else f"İleri  {theme.BUTTON_SYMBOLS['next']}"
        self.next_button = ttk.Button(buttons, text=next_text, command=self.next, takefocus=False, width=-8,
                                      **theme.button_options("primary"))
        self.home_button = ttk.Button(buttons, text=HOME_TEXT, command=self.home, takefocus=False, width=-8,
                                      **theme.button_options("outline"))
        self.finish_home_button = ttk.Button(buttons, text=FINISH_HOME_TEXT, command=self.home, takefocus=False,
                                             **theme.button_options("outline"))
        self.play_button = ttk.Button(buttons, text=theme.button_text("start", PLAY_TEXT), command=self.play,
                                      takefocus=False, width=-8, **theme.button_options("primary"))
        self._buttons_frame = buttons

    def _px(self, value):
        return theme.px(value, self.scale)

    # ------------------------------------------------------------------
    # Gezinme
    # ------------------------------------------------------------------
    @property
    def step(self):
        return self.navigator.current

    @property
    def is_last(self):
        return not self.navigator.can_next

    def show_step(self, index):
        self.navigator.index = max(0, min(index, len(self.navigator.steps) - 1))
        step = self.navigator.current
        self.position_label.configure(text=f"Adım {self.navigator.position_text()}")
        self.title_label.configure(text=step.title)
        self.body_label.configure(text=step.body)
        self._draw_dots()
        for button in (self.back_button, self.next_button, self.home_button, self.finish_home_button,
                       self.play_button):
            button.pack_forget()
        if self.is_last:
            self.finish_home_button.pack(side="left")
            self.play_button.pack(side="right")
        else:
            self.back_button.pack(side="left")
            self.next_button.pack(side="left", padx=(self._px(8), 0))
            self.home_button.pack(side="right")
        self.back_button.configure(state="normal" if self.navigator.can_back else "disabled")
        self.reposition()

    def next(self):
        if self.navigator.can_next:
            self.show_step(self.navigator.index + 1)
        return "break"

    def back(self):
        if self.navigator.can_back:
            self.show_step(self.navigator.index - 1)
        return "break"

    def home(self):
        if self.on_home is not None:
            self.on_home()
        return "break"

    def play(self):
        if self.on_play is not None:
            self.on_play()
        return "break"

    def _draw_dots(self):
        c = self.dots
        c.delete("all")
        count = len(self.navigator.steps)
        size, gap = self._px(6), self._px(5)
        c.configure(width=count * size + (count - 1) * gap)
        for index in range(count):
            x = index * (size + gap)
            color = theme.COLORS["primary"] if index == self.navigator.index else theme.COLORS["border"]
            c.create_oval(x, 2, x + size, 2 + size, fill=color, outline="", tags=("dot",))

    # ------------------------------------------------------------------
    # Yerleşim
    # ------------------------------------------------------------------
    def target_widget(self):
        return self.targets[self.step.section]

    def target_rect(self):
        """Hedefin pencere içindeki dikdörtgeni ``(x0, y0, x1, y1)``."""
        widget = self.target_widget()
        x = widget.winfo_rootx() - self.root.winfo_rootx()
        y = widget.winfo_rooty() - self.root.winfo_rooty()
        return x, y, x + widget.winfo_width(), y + widget.winfo_height()

    def hole_rect(self):
        """Aydınlık bırakılan alan: hedef + pay (pencere sınırına kırpılmış)."""
        x0, y0, x1, y1 = self.target_rect()
        pad = self._px(HOLE_PAD)
        width, height = self.root.winfo_width(), self.root.winfo_height()
        return max(0, x0 - pad), max(0, y0 - pad), min(width, x1 + pad), min(height, y1 + pad)

    def card_rect(self):
        """Açıklama kutusunun pencere içindeki dikdörtgeni."""
        x = self.card.winfo_rootx() - self.root.winfo_rootx()
        y = self.card.winfo_rooty() - self.root.winfo_rooty()
        return x, y, x + self.card.winfo_width(), y + self.card.winfo_height()

    def _schedule_reposition(self):
        if self._job is not None:
            self.root.after_cancel(self._job)
        self._job = self.root.after(REPOSITION_DELAY_MS, self._on_reposition_timer)

    def _on_reposition_timer(self):
        self._job = None
        self.reposition()

    def reposition(self):
        """Karartmayı, deliği, vurgu çerçevesini ve açıklama kutusunu günceller."""
        if self._job is not None:
            self.root.after_cancel(self._job)
            self._job = None
        if self._hidden or self.root.state() in ("withdrawn", "iconic"):
            # Ana pencere görünmüyorken rehber pencereleri de gösterilmez.
            for window in (self.overlay, self.card):
                if window is not None:
                    window.withdraw()
            return
        self.root.update_idletasks()
        width, height = self.root.winfo_width(), self.root.winfo_height()
        if width <= 1 or height <= 1:
            return
        root_x, root_y = self.root.winfo_rootx(), self.root.winfo_rooty()
        hole = self.hole_rect()
        if self.overlay is not None:
            self.overlay.geometry(f"{width}x{height}+{root_x}+{root_y}")
            self.dim_canvas.delete("all")
            self.dim_canvas.create_rectangle(*hole, fill=HOLE_KEY, outline="", tags=("hole",))
            self.overlay.deiconify()
            self.overlay.lift()
        self._place_ring(hole)
        x, y, self.card_side = self._card_position(hole, (width, height))
        self.card.geometry(f"+{root_x + x}+{root_y + y}")
        self.card.deiconify()
        self.card.lift()

    def _place_ring(self, hole):
        """Deliğin kenarında mavi çerçeve, hemen içinde açık mavi ikinci çerçeve.

        İkisi de deliğin (hedefin çevresindeki payın) içindedir; karartılmaz ve
        hedefin üstüne binmez.
        """
        x0, y0, x1, y1 = hole
        ring = self._px(RING_WIDTH)
        self._place_frame_ring(self.ring, (x0, y0, x1, y1), ring)
        self._place_frame_ring(self.glow, (x0 + ring, y0 + ring, x1 - ring, y1 - ring), self._px(GLOW_WIDTH))

    @staticmethod
    def _place_frame_ring(frames, rect, w):
        x0, y0, x1, y1 = rect
        for frame, (x, y, width, height) in zip(frames, (
                (x0, y0, x1 - x0, w), (x0, y1 - w, x1 - x0, w), (x0, y0, w, y1 - y0), (x1 - w, y0, w, y1 - y0))):
            frame.place(x=x, y=y, width=max(1, width), height=max(1, height))
            frame.lift()

    def _card_position(self, hole, window):
        """Kutu genişliği sırayla daraltılarak hedefi kapatmayan konum aranır."""
        for width in CARD_WIDTHS:
            self._set_card_width(self._px(width))
            size = (self.card.winfo_reqwidth(), self.card.winfo_reqheight())
            position = place_card(hole, window, size, gap=self._px(CARD_GAP), margin=self._px(WINDOW_MARGIN))
            if position is not None:
                return position
        return fallback_card(hole, window, size, margin=self._px(WINDOW_MARGIN))

    def _set_card_width(self, width):
        inner = width - 2 * self._px(18)
        self.body_label.configure(wraplength=inner)
        self.title_label.configure(wraplength=inner)
        self.card.update_idletasks()

    # ------------------------------------------------------------------
    # Pencere olayları
    # ------------------------------------------------------------------
    def _on_root_configure(self, event):
        if event.widget is self.root:
            self._schedule_reposition()

    def _on_root_unmap(self, event):
        if event.widget is self.root:
            self._hidden = True
            for window in (self.overlay, self.card):
                if window is not None:
                    window.withdraw()

    def _on_root_map(self, event):
        if event.widget is self.root:
            self._hidden = False
            self._schedule_reposition()

    # ------------------------------------------------------------------
    def destroy(self):
        """Rehberi tamamen kaldırır: katmanlar, kilit, kısayollar ve bekleyen tetikleme."""
        if self._job is not None:
            self.root.after_cancel(self._job)
            self._job = None
        for sequence, script in self._saved_bindings.items():
            self.root.bind(sequence, script)
        for frame in self.ring + self.glow:
            frame.destroy()
        for window in (self.card, self.overlay):
            if window is not None:
                window.destroy()
        self.app.set_interaction_locked(False)
