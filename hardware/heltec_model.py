"""Generate a visual-only Heltec WiFi Kit 32 V2 assembly for KiCad."""

import argparse
from pathlib import Path


OUTPUT = Path(__file__).resolve().parent / "Heltec_WiFi_Kit_32_V2.wrl"
ROW_SPACING = 22.86
PITCH = 2.54
SOCKET_HEIGHT = 8.5
WHITE = (0.88, 0.90, 0.87)
BLACK = (0.025, 0.028, 0.03)
METAL = (0.65, 0.67, 0.70)
GOLD = (0.78, 0.57, 0.16)
CYAN = (0.05, 0.65, 0.95)


def box(center, size, color):
    position = " ".join(f"{value / 2.54:.6f}" for value in center)
    dimensions = " ".join(f"{value / 2.54:.6f}" for value in size)
    rgb = " ".join(str(value) for value in color)
    return (
        f"Transform {{ translation {position} children [ Shape {{ "
        f"appearance Appearance {{ material Material {{ diffuseColor {rgb} }} }} "
        f"geometry Box {{ size {dimensions} }} }} ] }}"
    )


def geometry(row_spacing=ROW_SPACING):
    middle = row_spacing / 2
    shapes = []
    for xpos in (0, row_spacing):
        shapes.append(box((xpos, -21.59, SOCKET_HEIGHT / 2),
                          (2.54, 45.72, SOCKET_HEIGHT), BLACK))
        for index in range(18):
            shapes.append(box((xpos, -index * PITCH, 5.5), (0.64, 0.64, 13), GOLD))
            shapes.append(box((xpos, -index * PITCH, 10.13), (1.6, 1.6, 0.06), GOLD))
    shapes.append(box((middle, -22, 9.3), (row_spacing + 3.2, 50, 1.6), WHITE))
    shapes.append(box((middle, -24.5, 10.65), (21.5, 28, 1.1), BLACK))
    shapes.append(box((middle, -24.5, 11.65), (20.5, 27, 0.9), METAL))
    shapes.append(box((middle, -24.5, 12.2), (20, 26.5, 0.5), BLACK))
    shapes.append(box((middle, -25, 12.49), (17.8, 23.5, 0.08), (0.005, 0.012, 0.02)))
    shapes.append(box((middle, -24.5, 10.9), (7, 29, 0.25), (0.82, 0.39, 0.08)))
    shapes.append(box((middle, 0.2, 11.4), (7.6, 5.8, 2.6), METAL))
    shapes.append(box((middle, 3.12, 11.4), (6.3, 0.12, 1.5), BLACK))
    shapes.append(box((middle, 3.2, 11.25), (4.8, 0.1, 0.45), (0.4, 0.4, 0.42)))
    for xpos in (4.2, row_spacing - 4.2):
        shapes.append(box((xpos, -2, 10.7), (3.5, 4.5, 1.2), METAL))
        shapes.append(box((xpos, -2, 11.5), (2, 2.8, 0.6), BLACK))
    for xpos, ypos in ((5, -7), (18, -7), (8, -8.5), (15, -9)):
        shapes.append(box((xpos, ypos, 10.55), (2.5, 3, 0.9), BLACK))
    shapes.append(box((middle, -43.5, 10.4), (12, 4.5, 0.5), (0.1, 0.42, 0.25)))
    for index in range(5):
        shapes.append(box((middle - 4 + index * 2, -43.5, 10.7), (0.35, 3.5, 0.08), GOLD))
    glyphs = {
        "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
        "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
        "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
        "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
        "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    }
    for letter_index, letter in enumerate("HELTEC"):
        for row_index, row in enumerate(glyphs[letter]):
            for column_index, pixel in enumerate(row):
                if pixel == "1":
                    shapes.append(box((middle + 2 - row_index * 0.6,
                                       -14.8 - (letter_index * 6 + column_index) * 0.6,
                                       12.55), (0.54, 0.54, 0.03), CYAN))
    return "#VRML V2.0 utf8\n" + "\n".join(shapes) + "\n"


def write_model(row_spacing=ROW_SPACING):
    OUTPUT.write_text(geometry(row_spacing), encoding="ascii")
    return OUTPUT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--row-spacing", type=float, default=ROW_SPACING)
    args = parser.parse_args()
    print("Created:", write_model(args.row_spacing))


if __name__ == "__main__":
    main()