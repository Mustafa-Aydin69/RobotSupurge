"""Açılış ekranı görsellerini referans tasarımdan kırpar ve welcome_assets.py'ye gömer.

Kullanım (proje klasöründe, Pillow kurulu bir ortamda):

    python -m tools.make_welcome_assets

Girdi : assets/welcome/referans.webp (açılış ekranının referans tasarımı)
Çıktı : assets/welcome/*.png      (kırpılmış görseller; inceleme için)
        welcome_assets.py         (aynı PNG'ler base64 olarak; LMS ve EXE için)

Referans görseldeki başlık, açıklama, düğme ve özellik metinleri kırpılmaz;
bunlar arayüzde gerçek bileşenlerle oluşturulur. Yalnızca soldaki
illüstrasyon, sağ üstteki robot simgesi ve alttaki dört özellik simgesi
alınır. Çıktı her çalıştırmada aynıdır (testler bunu denetler).
"""

import base64
import io
import sys
import textwrap
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "welcome" / "referans.webp"
OUT_DIR = ROOT / "assets" / "welcome"
MODULE = ROOT / "welcome_assets.py"

# Arka plan rengi: referans görselin zemini (kenarların yumuşatılması için).
BACKGROUND = (254, 254, 254)

# ad: (kırpma kutusu (sol, üst, sağ, alt), yumuşatılacak kenarlar {kenar: piksel}, beyaz zemin saydam mı)
# En üstteki 42 piksel referanstaki pencere başlık çubuğudur; alınmaz.
CROPS = {
    "illustration": ((0, 46, 740, 790), {"right": 90, "bottom": 110, "top": 24}, False),
    "logo": ((968, 108, 1132, 250), {}, True),
    "feature_agents": ((292, 796, 370, 858), {}, True),
    "feature_rooms": ((590, 796, 666, 858), {}, True),
    "feature_compare": ((890, 796, 966, 858), {}, True),
    "feature_log": ((1200, 796, 1276, 858), {}, True),
}
WHITE_KEY_FLOOR = 12    # beyaza bu kadar yakın pikseller tamamen saydam (zemin gölgesi kalmasın)
WHITE_KEY_RANGE = 60    # bundan sonra bu kadar koyulaşan pikseller tamamen opak


def feather(image, edges):
    """Verilen kenarlarda saydamlığı doğrusal olarak artırır (zemine yumuşak geçiş)."""
    image = image.convert("RGBA")
    width, height = image.size
    alpha = Image.new("L", image.size, 255)
    pixels = alpha.load()
    for y in range(height):
        for x in range(width):
            factor = 1.0
            for edge, size in edges.items():
                distance = {"right": width - 1 - x, "left": x, "bottom": height - 1 - y, "top": y}[edge]
                if distance < size:
                    factor = min(factor, distance / size)
            pixels[x, y] = round(255 * factor)
    image.putalpha(alpha)
    return image


def white_to_alpha(image):
    """Beyaz zemini saydam yapar; kenarlar yumuşak kalır (renk beyazdan ayrıştırılır)."""
    image = image.convert("RGBA")
    pixels = image.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            r, g, b, _ = pixels[x, y]
            darkness = 255 - min(r, g, b)
            alpha = min(1.0, max(0.0, (darkness - WHITE_KEY_FLOOR) / WHITE_KEY_RANGE))
            if alpha <= 0:
                pixels[x, y] = (255, 255, 255, 0)
                continue
            # Görünen renk = alpha * gerçek renk + (1 - alpha) * beyaz
            unblend = [max(0, min(255, round((v - (1 - alpha) * 255) / alpha))) for v in (r, g, b)]
            pixels[x, y] = (*unblend, round(alpha * 255))
    return image


def png_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def crop_assets():
    """Görselleri kırpar: ``{ad: ((genişlik, yükseklik), png baytları)}`` (dosyaya yazmaz)."""
    source = Image.open(SOURCE).convert("RGB")
    assets = {}
    for name, (box, edges, transparent) in CROPS.items():
        image = source.crop(box)
        image = feather(image, edges) if edges else image
        image = white_to_alpha(image) if transparent else image
        assets[name] = (image.size, png_bytes(image))
    return assets


def build():
    assets = crop_assets()
    for name, (_, data) in assets.items():
        (OUT_DIR / f"{name}.png").write_bytes(data)
    MODULE.write_text(render_module(assets), encoding="utf-8", newline="\n")
    return assets


def render_module(assets):
    lines = [
        '"""Açılış ekranı görselleri (PNG, base64).',
        "",
        "Bu dosya tools/make_welcome_assets.py ile assets/welcome/referans.webp",
        "dosyasından üretilir; elle düzenlenmez. Görseller kaynak koda gömülüdür;",
        "böylece yalnızca .py dosyalarından oluşan teslimde ve EXE'de de bulunur.",
        '"""',
        "",
        "# ad: (genişlik, yükseklik)",
        "SIZES = {",
    ]
    for name, (size, _) in assets.items():
        lines.append(f'    "{name}": {size},')
    lines += ["}", "", "# ad: base64 kodlu PNG verisi (tkinter.PhotoImage(data=...) doğrudan okuyabilir)", "PNG = {"]
    for name, (_, data) in assets.items():
        encoded = base64.b64encode(data).decode("ascii")
        lines.append(f'    "{name}": (')
        lines += [f'        "{chunk}"' for chunk in textwrap.wrap(encoded, 96)]
        lines.append("    ),")
    lines += ["}", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    built = build()
    for asset_name, (asset_size, asset_data) in built.items():
        print(f"{asset_name:16} {asset_size[0]}x{asset_size[1]}  {len(asset_data) / 1024:.0f} KB")
    print(f"{MODULE.name}: {MODULE.stat().st_size / 1024:.0f} KB")
    sys.exit(0)
