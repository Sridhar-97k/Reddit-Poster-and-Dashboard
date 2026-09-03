"""Generate the app icon from scratch (no external art tools, no extra deps).

Draws a generic, Reddit-flavoured mascot — a rounded orange badge with a
friendly antenna'd face — using Qt's painter, then writes:

    assets/icon.png    (256x256, used as the in-app window/taskbar icon)
    assets/icon.ico    (multi-size Windows icon, used for the built .exe)

Usage:
    python scripts/make_icons.py
"""

import os
import struct
import sys
from pathlib import Path

# Render offscreen so this works without a display/running app.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtGui import QGuiApplication, QImage, QPainter, QColor, QBrush, QPen, QLinearGradient
from PyQt5.QtCore import Qt, QByteArray, QBuffer, QIODevice, QRectF, QPointF

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = REPO_ROOT / "assets"

REDDIT_ORANGE = "#FF4500"
REDDIT_ORANGE_LIGHT = "#FF6314"
WHITE = "#FFFFFF"

ICO_SIZES = [16, 32, 48, 64, 128, 256]


def render(size: int) -> QImage:
    """Draw the icon at the given pixel size and return the QImage."""
    S = float(size)
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)

    # --- rounded badge background (orange gradient) ---
    grad = QLinearGradient(0, 0, 0, S)
    grad.setColorAt(0.0, QColor(REDDIT_ORANGE_LIGHT))
    grad.setColorAt(1.0, QColor(REDDIT_ORANGE))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.NoPen)
    radius = S * 0.22
    p.drawRoundedRect(QRectF(0, 0, S, S), radius, radius)

    cx = S * 0.5
    cy = S * 0.57

    # --- antenna (line + ball) ---
    ball_c = QPointF(cx, S * 0.155)
    head_top = QPointF(cx, cy - S * 0.24)
    pen = QPen(QColor(WHITE))
    pen.setWidthF(S * 0.045)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.drawLine(ball_c, head_top)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(WHITE))
    p.drawEllipse(ball_c, S * 0.058, S * 0.058)

    # --- ears (two white blobs) ---
    ear_r = S * 0.11
    p.drawEllipse(QPointF(cx - S * 0.24, cy - S * 0.16), ear_r, ear_r)
    p.drawEllipse(QPointF(cx + S * 0.24, cy - S * 0.16), ear_r, ear_r)

    # --- head (white) ---
    head_rx, head_ry = S * 0.30, S * 0.26
    p.setBrush(QColor(WHITE))
    p.drawEllipse(QPointF(cx, cy), head_rx, head_ry)

    # --- eyes (orange) ---
    p.setBrush(QColor(REDDIT_ORANGE))
    eye_r = S * 0.05
    eye_y = cy - S * 0.015
    p.drawEllipse(QPointF(cx - S * 0.115, eye_y), eye_r, eye_r)
    p.drawEllipse(QPointF(cx + S * 0.115, eye_y), eye_r, eye_r)

    # --- smile (orange arc) ---
    smile = QPen(QColor(REDDIT_ORANGE))
    smile.setWidthF(S * 0.035)
    smile.setCapStyle(Qt.RoundCap)
    p.setPen(smile)
    p.setBrush(Qt.NoBrush)
    smile_rect = QRectF(cx - S * 0.12, cy + S * 0.02, S * 0.24, S * 0.16)
    # Bottom arc (200 to 340 degrees) = an upward smile
    p.drawArc(smile_rect, 200 * 16, 140 * 16)

    p.end()
    return img


def _png_bytes(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def write_ico(path: Path, sizes):
    """Write a multi-size .ico whose entries are PNG-encoded (Vista+ supported)."""
    entries = [(s, _png_bytes(render(s))) for s in sizes]

    header = struct.pack("<HHH", 0, 1, len(entries))  # reserved, type=icon, count
    offset = len(header) + 16 * len(entries)
    dir_blob = b""
    data_blob = b""
    for size, png in entries:
        w = 0 if size >= 256 else size
        h = 0 if size >= 256 else size
        dir_blob += struct.pack(
            "<BBBBHHII",
            w, h, 0, 0,        # width, height, colors, reserved
            1, 32,             # planes, bit depth
            len(png), offset,  # size of data, offset to data
        )
        data_blob += png
        offset += len(png)

    path.write_bytes(header + dir_blob + data_blob)


def main():
    # A QGuiApplication makes Qt's paint/font subsystems fully available.
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)  # noqa: F841

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    png_path = ASSETS_DIR / "icon.png"
    render(256).save(str(png_path), "PNG")
    print(f"wrote {png_path}")

    ico_path = ASSETS_DIR / "icon.ico"
    write_ico(ico_path, ICO_SIZES)
    print(f"wrote {ico_path}  (sizes: {', '.join(map(str, ICO_SIZES))})")


if __name__ == "__main__":
    main()
