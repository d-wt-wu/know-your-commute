"""Render the existing geometric K mark as app PNGs. Optional authoring tool: Pillow.

No image service, downloaded stock art or new runtime dependency is required.
The committed PNGs are the inputs to an ordinary app build.
"""
from pathlib import Path

from PIL import Image, ImageDraw

destination = Path(__file__).resolve().parents[1] / "web/public"
for filename, size in [("icon-192.png", 192), ("icon-512.png", 512), ("apple-touch-icon.png", 180)]:
    scale = size * 4 / 40
    image = Image.new("RGB", (size * 4, size * 4), "#202523")
    draw = ImageDraw.Draw(image)
    width = round(3 * scale)
    lines = [[(12, 11), (12, 29)], [(12, 20), (21, 20), (28, 11)], [(21, 20), (28, 29)]]
    for points in lines:
        pixels = [(round(x * scale), round(y * scale)) for x, y in points]
        draw.line(pixels, fill="#edb95d", width=width, joint="curve")
        for x, y in pixels:
            radius = width / 2
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="#edb95d")
    image.resize((size, size), Image.Resampling.LANCZOS).save(destination / filename, optimize=True)
