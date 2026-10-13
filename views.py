"""Tuval çizimleri: gerçek ortam, ajanın iç modeli, hedef ve rota.

Bu modüldeki fonksiyonlar yalnızca kendilerine verilen nesneleri okur ve
verilen tuvale çizer:

* ``draw_environment`` gerçek ortamı (ve yalnızca ajanın hedef işaretini),
* ``draw_model`` ajanın salt okunur iç model kopyasını,
* ``draw_plan`` ajanın salt okunur plan kopyasını (hedef ve rota).

Hiçbiri ajana ya da simülasyona yazmaz; görselleştirme ajanın davranışını
etkilemez.
"""

from types import MappingProxyType

from agents import SOURCE_INFERENCE, ModelSnapshot
from environment import Status

# ----------------------------------------------------------------------
# Metinler ve renkler
# ----------------------------------------------------------------------
STATUS_TEXT = {Status.CLEAN: "Temiz", Status.DIRTY: "Kirli"}

COLOR_CLEAN = "#cdeac0"
COLOR_DIRTY = "#c8a27a"
COLOR_DIRT_SPOT = "#7a5230"
COLOR_ROBOT = "#2f3e4e"
COLOR_ROBOT_RING = "#5fa8d3"
COLOR_ACTIVE_BORDER = "#1d70b8"

# Hedef ve rota rengi
COLOR_GOAL = "#7b3fbf"

# İç model paneli renkleri
COLOR_MODEL_UNKNOWN = "#e2e2e2"
COLOR_MODEL_STALE = "#f2e3a0"
COLOR_STALE_HATCH = "#b8962e"     # eskimiş bilginin çizgili deseni

# İç model kategorileri ve ekrandaki adları
MODEL_UNKNOWN, MODEL_CLEAN, MODEL_INFERRED, MODEL_STALE, MODEL_DIRTY = (
    "unknown", "clean", "inferred", "stale", "dirty",
)
MODEL_CATEGORY_TEXT = {
    MODEL_UNKNOWN: "?",
    MODEL_CLEAN: "Temiz",
    MODEL_INFERRED: "Çıkarım",
    MODEL_STALE: "Eski",
    MODEL_DIRTY: "Kirli",
}
MODEL_CATEGORY_FILL = {
    MODEL_UNKNOWN: COLOR_MODEL_UNKNOWN,
    MODEL_CLEAN: COLOR_CLEAN,
    MODEL_INFERRED: COLOR_CLEAN,
    MODEL_STALE: COLOR_MODEL_STALE,
    MODEL_DIRTY: COLOR_DIRTY,
}
MODEL_PANEL_TITLE = "Ajanın iç modeli (gerçek durum değil)"

# Kirli odadaki lekelerin oda içindeki göreli konumları (x, y, yarıçap)
DIRT_SPOTS = [(0.18, 0.30, 9), (0.70, 0.22, 7), (0.32, 0.72, 11), (0.82, 0.66, 8), (0.55, 0.45, 6)]


# ----------------------------------------------------------------------
# Yardımcılar
# ----------------------------------------------------------------------
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


def stale_threshold(grid):
    """Bilginin arayüzde "eskimiş" gösterileceği yaş (ajan adımı).

    Yalnızca görselleştirme içindir; ajanın kararlarını etkilemez.
    """
    return max(4, grid.rows * grid.cols)


def model_category(observation, age, threshold):
    """İç modeldeki bir odanın gösterim kategorisi."""
    if observation is None:
        return MODEL_UNKNOWN
    if observation.status is Status.DIRTY:
        return MODEL_DIRTY
    if age >= threshold:
        return MODEL_STALE
    if observation.source == SOURCE_INFERENCE:
        return MODEL_INFERRED
    return MODEL_CLEAN


def empty_snapshot():
    """Simülasyon başlamadan önce gösterilen boş model (her oda bilinmiyor)."""
    return ModelSnapshot(0, None, MappingProxyType({}))


def model_legend_text(threshold):
    """İç model panelinin lejantı."""
    return (
        "?  gri: bilinmiyor · yeşil: temiz (algı) · kesikli kenar: temiz (çıkarım) · "
        f"sarı + çizgili, \"Eski\": eskimiş bilgi (yaş ≥ {threshold}) · kahverengi: kirli\n"
        "● mavi nokta: ajanın bildiği konumu · □ mor çerçeve ve ok: hedef ve rota. "
        "Yaş, son bilgiden bu yana geçen ajan adımıdır; gerçek süre değildir."
    )


def environment_legend_text():
    """Gerçek ortam panelinin lejantı."""
    return ("Yeşil, T: temiz · Kahverengi lekeli, K: kirli · Mavi çerçeve ve robot: "
            "robotun odası · ◆ mor elmas: ajanın hedefi (amaç tabanlı ajan)")


def _draw_hatch(canvas, left, top, right, bottom, spacing, tags):
    """Dikdörtgenin içine çapraz çizgili tarama deseni çizer (renk dışı ipucu)."""
    width, height = right - left, bottom - top
    offset = spacing
    while offset < width + height:
        # Sol kenar/üst kenar boyunca başlayıp sağ kenar/alt kenarda biten çizgi.
        x0, y0 = left + max(0.0, offset - height), top + min(offset, height)
        x1, y1 = left + min(offset, width), top + max(0.0, offset - width)
        canvas.create_line(x0, y0, x1, y1, fill=COLOR_STALE_HATCH, tags=tags)
        offset += spacing


def _font(points, *style):
    """Tuval yazı tipi; boyut piksel cinsinden verilir.

    Değerler 96 DPI'daki punto karşılığıdır (1 punto = 4/3 piksel). Piksel
    kullanılması, yüksek DPI ölçeklemede yazıların hücre boyutlarıyla orantılı
    kalmasını sağlar; %100 ölçekte görünüm değişmez.
    """
    return ("Segoe UI", -max(1, round(points * 4 / 3)), *style)


def _canvas_size(canvas, default_width, default_height):
    width = canvas.winfo_width() if canvas.winfo_width() > 1 else default_width
    height = canvas.winfo_height() if canvas.winfo_height() > 1 else default_height
    return width, height


# ----------------------------------------------------------------------
# İç model ve plan
# ----------------------------------------------------------------------
def draw_model(canvas, grid, snapshot, plan, threshold, default_size):
    """İç modeli çizer. Yalnızca ``snapshot`` ve ``plan`` kopyaları kullanılır; ortam okunmaz."""
    c = canvas
    c.delete("all")
    width, height = _canvas_size(c, *default_size)

    left0, top0, cell_w, cell_h, gap = compute_layout(width, height, grid.rows, grid.cols)
    size = min(cell_w, cell_h)
    title_font = _font(max(7, min(12, int(size * 0.13))), "bold")
    info_font = _font(max(7, min(10, int(size * 0.10))))
    for room in grid.rooms:
        row, col = grid.position_of(room)
        left = left0 + col * (cell_w + gap)
        top = top0 + row * (cell_h + gap)
        right, bottom = left + cell_w, top + cell_h
        observation = snapshot.observations.get(room)
        age = snapshot.age_of(room)
        category = model_category(observation, age, threshold)
        is_current = snapshot.location == room

        c.create_rectangle(
            left, top, right, bottom, fill=MODEL_CATEGORY_FILL[category],
            outline=COLOR_ACTIVE_BORDER if is_current else "#666",
            width=3 if is_current else 1,
            dash=(4, 3) if observation is not None and observation.source == SOURCE_INFERENCE else (),
            tags=("model-room", f"model:{room}", f"category:{category}"),
        )
        if category == MODEL_STALE:
            _draw_hatch(c, left + 1, top + 1, right - 1, bottom - 1, max(6.0, size / 6),
                        ("stale-pattern", f"stale:{room}"))
        center_x, center_y = (left + right) / 2, (top + bottom) / 2
        c.create_text(center_x, top + max(8, size * 0.14), text=room, font=title_font)
        if category == MODEL_UNKNOWN:
            if size >= 24:
                c.create_text(center_x, center_y + size * 0.08, text="?", fill="#777",
                              font=_font(max(8, int(size * 0.3)), "bold"))
        else:
            if size >= 50:
                c.create_text(center_x, center_y, text=MODEL_CATEGORY_TEXT[category], font=info_font)
            if size >= 26:
                # Küçük hücrede ayrı etiket sığmadığı için eskilik yaş satırında belirtilir.
                age_text = f"eski {age}" if category == MODEL_STALE and size < 50 else f"yaş {age}"
                c.create_text(center_x, bottom - max(7, size * 0.14), text=age_text, font=info_font)
        if is_current:
            # Ajanın kendi konum bilgisi: sağ üst köşede küçük işaret.
            r = max(2.5, min(7.0, size * 0.07))
            c.create_oval(right - 3 * r, top + r, right - r, top + 3 * r,
                          fill=COLOR_ACTIVE_BORDER, outline="", tags=("model-agent",))

    if plan is not None and plan.target is not None:
        draw_plan(c, grid, plan, left0, top0, cell_w, cell_h, gap)


def draw_plan(canvas, grid, plan, left0, top0, cell_w, cell_h, gap):
    """Model panelinde hedef odayı ve BFS rotasını çizer."""
    c = canvas
    size = min(cell_w, cell_h)

    def center(room):
        row, col = grid.position_of(room)
        return (left0 + col * (cell_w + gap) + cell_w / 2, top0 + row * (cell_h + gap) + cell_h / 2)

    row, col = grid.position_of(plan.target.room)
    left, top = left0 + col * (cell_w + gap), top0 + row * (cell_h + gap)
    inset = max(2.0, size * 0.06)
    c.create_rectangle(left + inset, top + inset, left + cell_w - inset, top + cell_h - inset,
                       outline=COLOR_GOAL, width=max(2, round(size / 25)), tags=("plan-target",))
    if plan.route and plan.origin:
        points = [center(plan.origin)] + [center(room) for room in plan.route_rooms]
        c.create_line(*[v for point in points for v in point], fill=COLOR_GOAL,
                      width=max(2, round(size / 30)), arrow="last",
                      arrowshape=(max(6, size * 0.15), max(8, size * 0.18), max(3, size * 0.06)),
                      tags=("plan-route",))


# ----------------------------------------------------------------------
# Gerçek ortam
# ----------------------------------------------------------------------
def draw_environment(canvas, grid, env, plan, default_size):
    """Gerçek ortamı çizer; plandan yalnızca hedef işareti kullanılır."""
    c = canvas
    c.delete("all")
    width, height = _canvas_size(c, *default_size)

    left0, top0, cell_w, cell_h, gap = compute_layout(width, height, grid.rows, grid.cols)
    size = min(cell_w, cell_h)
    title_font = _font(max(7, min(13, int(size * 0.14))), "bold")
    status_font = _font(max(7, min(11, int(size * 0.11))))
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
        elif status is not None:
            # Küçük hücrede durum yazısı sığmaz: sağ alt köşede T (temiz) / K (kirli).
            mark = "T" if status is Status.CLEAN else "K"
            c.create_text(right - 3, bottom - 2, text=mark, anchor="se",
                          font=_font(max(7, int(size * 0.16)), "bold"),
                          tags=("status-mark", f"mark:{room}:{mark}"))

        if plan is not None and plan.target is not None and plan.target.room == room:
            # Gerçek ortamda yalnızca ajanın hedefi işaretlenir (rota gösterilmez).
            r = max(3.0, min(9.0, size * 0.08))
            x, y = left + 2.2 * r, top + 2.2 * r
            c.create_polygon(x, y - r, x + r, y, x, y + r, x - r, y, fill=COLOR_GOAL,
                             outline="", tags=("env-target",))

        if is_current:
            # Küçük odalarda durum yazısı yok; robot oda adından uzaklaşır.
            offset = 0.03 if size >= 60 else 0.18
            draw_robot(c, (left + right) / 2, (top + bottom) / 2 + size * offset, size)


def draw_logo(canvas, size, background):
    """Başlıktaki robot süpürge simgesi (yandan görünüş)."""
    c = canvas
    c.delete("all")
    c.configure(background=background)
    s = size / 56
    # gövde, üst kapak, ön tampon ve algılayıcı
    c.create_oval(4 * s, 24 * s, 52 * s, 50 * s, fill="#c5d3e3", outline="#2f3e4e", width=max(1, round(2 * s)))
    c.create_oval(4 * s, 14 * s, 52 * s, 42 * s, fill=COLOR_ROBOT, outline="#2f3e4e", width=max(1, round(2 * s)))
    c.create_oval(14 * s, 18 * s, 42 * s, 34 * s, fill="#4a5d72", outline="")
    c.create_oval(24 * s, 21 * s, 32 * s, 27 * s, fill=COLOR_ROBOT_RING, outline="")
    c.create_line(10 * s, 46 * s, 46 * s, 46 * s, fill="#2f3e4e", width=max(1, round(2 * s)))


def draw_robot(canvas, x, y, size):
    c = canvas
    r = max(6.0, min(30.0, size * 0.22))
    ring = max(1, round(r / 7.5))
    c.create_oval(x - r, y - r, x + r, y + r, fill=COLOR_ROBOT, outline=COLOR_ROBOT_RING,
                  width=ring, tags=("robot",))
    eye = r * 0.27
    c.create_oval(x - eye, y - r + r * 0.2, x + eye, y - r + r * 0.2 + 2 * eye,
                  fill=COLOR_ROBOT_RING, outline="", tags=("robot",))
    if r >= 18:
        c.create_text(x, y + r * 0.27, text="Robot", fill="white",
                      font=_font(max(7, int(r * 0.3)), "bold"), tags=("robot",))
