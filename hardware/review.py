"""Create a full-size socket fitting PDF and inspect a FreeRouting session."""

import argparse
import json
from pathlib import Path

import pymupdf
import sexpdata


ROOT = Path(__file__).resolve().parent / "generated"


def fit_template():
    doc = pymupdf.open()
    page = doc.new_page(width=595.28, height=841.89)
    scale = 72 / 25.4
    page.insert_text((40, 35), "Heltec V2 SOCKET FIT CHECK - print Actual size / 100%", fontsize=12)
    page.insert_text((40, 54), "Compare PIN CENTERS. Do not order until both rows fit without bending.", fontsize=10)
    for spacing, xpos in [(22.86, 25)]:
        page.insert_text((xpos * scale, 95), f"Row centers: {spacing:.2f} mm", fontsize=11)
        page.insert_text((xpos * scale, 112), "USB end / pin 1", fontsize=10)
        for row in range(2):
            for index in range(18):
                center = pymupdf.Point((xpos + row * spacing) * scale, (48 + index * 2.54) * scale)
                page.draw_circle(center, 0.5 * scale, color=(0, 0, 0), width=0.5)
        page.insert_text((xpos * scale, 285), "18 pins, 2.54 mm pitch", fontsize=10)
    start, end = pymupdf.Point(25 * scale, 120 * scale), pymupdf.Point(125 * scale, 120 * scale)
    page.draw_line(start, end, width=0.8)
    for xpos in [25, 125]:
        page.draw_line(pymupdf.Point(xpos * scale, 118 * scale), pymupdf.Point(xpos * scale, 122 * scale))
    page.insert_text((start.x, start.y + 20), "This calibration line MUST measure 100.00 mm on paper.", fontsize=10)
    page.insert_text((40, 405), "First check print scale. The diagram does not certify module dimensions.", fontsize=10)
    ROOT.mkdir(exist_ok=True)
    doc.save(ROOT / "socket_fit_check.pdf")
    print("Created:", ROOT / "socket_fit_check.pdf")


def children(node, name):
    return [item for item in node if isinstance(item, list) and item and str(item[0]) == name]


def decode_session(path):
    tree = sexpdata.loads(path.read_text(encoding="utf-8"))
    assert str(tree[0]) == "session"
    routes = children(tree, "routes")[0]
    resolution = children(routes, "resolution")[0]
    unit, precision = str(resolution[1]), float(resolution[2])
    factor = {"um": 0.001, "mm": 1, "mil": 0.0254, "inch": 25.4}[unit] / precision
    network = children(routes, "network_out")[0]
    tracks, vias = [], []
    for net in children(network, "net"):
        name = str(net[1])
        for wire in children(net, "wire"):
            for route in children(wire, "path"):
                points = [[float(route[index]) * factor, -float(route[index + 1]) * factor]
                          for index in range(3, len(route), 2)]
                tracks.append(dict(net=name, layer=str(route[1]), width=float(route[2]) * factor, points=points))
        for via in children(net, "via"):
            vias.append(dict(net=name, padstack=str(via[1]),
                             position=[float(via[2]) * factor, -float(via[3]) * factor]))
    data = dict(tracks=tracks, vias=vias)
    assert tracks, "Session contains no routed tracks"
    output = path.with_suffix(".routing.json")
    output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Decoded {len(tracks)} wire paths and {len(vias)} vias to {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path)
    args = parser.parse_args()
    fit_template()
    if args.session:
        decode_session(args.session)


if __name__ == "__main__":
    main()