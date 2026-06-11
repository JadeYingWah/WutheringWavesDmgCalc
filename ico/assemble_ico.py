"""Render SVG to individual .ico files and merge into one multi-resolution icon.ico."""
import struct
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIZES = [256, 128, 64, 48, 32, 24, 16]


def render_svg_to_icos():
    """Use Qt SVG renderer to convert Wico.svg to each size .ico"""
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtSvg import QSvgRenderer
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtCore import Qt

    app = QApplication.instance() or QApplication(sys.argv)

    svg_path = os.path.join(HERE, "Wico.svg")
    renderer = QSvgRenderer(svg_path)
    if not renderer.isValid():
        print("ERROR: Failed to load Wico.svg")
        return []

    entries = []
    for sz in SIZES:
        img = QImage(sz, sz, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        renderer.render(painter)
        painter.end()

        # Save as temp PNG
        png_path = os.path.join(HERE, f"_tmp_{sz}.png")
        img.save(png_path, "PNG")

        with open(png_path, "rb") as f:
            png_data = f.read()
        os.remove(png_path)

        # Build ICO with embedded PNG
        w_byte = sz if sz < 256 else 0
        h_byte = sz if sz < 256 else 0
        header = struct.pack("<HHH", 0, 1, 1)
        dir_entry = struct.pack("<BBBBHHII", w_byte, h_byte, 0, 0, 1, 32, len(png_data), 6 + 16)
        ico_data = header + dir_entry + png_data

        ico_path = os.path.join(HERE, f"Wico{sz}.ico")
        with open(ico_path, "wb") as f:
            f.write(ico_data)

        entries.append((sz, sz, png_data))
        print(f"  {sz}x{sz}: {len(png_data)} bytes")

    return entries


def assemble_ico(entries):
    """Merge entries into one multi-resolution icon.ico"""
    total_count = len(entries)
    header = struct.pack("<HHH", 0, 1, total_count)

    dir_bytes = b""
    data_bytes = b""
    offset = 6 + total_count * 16

    for w, h, img_data in entries:
        ew = w if w < 256 else 0
        eh = h if h < 256 else 0
        dir_bytes += struct.pack("<BBBBHHII", ew, eh, 0, 0, 1, 32, len(img_data), offset)
        data_bytes += img_data
        offset += len(img_data)

    out = header + dir_bytes + data_bytes
    out_path = os.path.join(HERE, "icon.ico")
    with open(out_path, "wb") as f:
        f.write(out)
    print(f"\nDone: {out_path}  ({len(out)} bytes, {total_count} sizes)")


if __name__ == "__main__":
    entries = render_svg_to_icos()
    if entries:
        assemble_ico(entries)
