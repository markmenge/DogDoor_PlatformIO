"""Generate a review-only KiCad 7 carrier for a two-motor dog-door winch."""

import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent
NAME = "dogdoor_review"
KICAD = Path(r"D:\Program Files\KiCad\7.0")
LIBRARIES = KICAD / "share/kicad/footprints"
OUTPUT = ROOT / "generated"
ROW_SPACING_MM = 22.86
CURRENT_REFERENCE_V = 1.65
CURRENT_RESISTANCE_OHM = 1500
CURRENT_MIRROR_A_PER_A = 0.0011
PARTS = []
POWER_NETS = {"INPUT_5V", "VM", "MOTOR_A1", "MOTOR_A2", "MOTOR_B1", "MOTOR_B2"}


def component(reference, value, footprint, position, pins, names=None,
              assembly="SMD", mpn="REVIEW_REQUIRED", rotation=0, fitted=True):
    part = dict(reference=reference, value=value, footprint=footprint,
                position=position, pins={str(number): net for number, net in pins.items()},
                names={str(number): label for number, label in (names or {}).items()},
                assembly=assembly, mpn=mpn, rotation=rotation, fitted=fitted)
    PARTS.append(part)
    return part


def passive(reference, value, first, second, position, kind="R", fitted=True):
    libraries = {"R": "Resistor_SMD:R_0805_2012Metric",
                 "C": "Capacitor_SMD:C_0805_2012Metric",
                 "FB": "Inductor_SMD:L_1206_3216Metric"}
    return component(reference, value, libraries[kind], position,
                     {1: first, 2: second}, fitted=fitted)


def circuit():
    PARTS.clear()
    left = ["GND", "+3V3", None, None, "LIMIT_OPEN", "LIMIT_CLOSE",
            None, "ALT_CLOSE_27", "CLOSE", "OPEN", None, None, "FAULT",
            "CURRENT_A", None, None, None, "CURRENT_B"]
    right = ["GND", "HELTEC_5V", None, None, None, None, None, "PIR_OUT",
             None, None, None, "PIR_IN", None, None, None, None, "ALT_PIR_22", None]
    left_labels = ["GND", "3V3", "Vext", "RST", "13", "12", "14", "27",
                   "26", "25", "33", "32", "35", "34", "39", "38", "37", "36"]
    right_labels = ["GND", "5V", "3V3", "Vext", "TX", "RX", "15", "2",
                    "0", "4", "16", "17", "5", "18", "23", "19", "22", "21"]
    for reference, nets, labels, xpos in [("J1", left, left_labels, 60),
                                         ("J2", right, right_labels, 60 + ROW_SPACING_MM)]:
        component(reference, "Heltec V2 " + ("LEFT" if reference == "J1" else "RIGHT"),
                  "Connector_PinSocket_2.54mm:PinSocket_1x18_P2.54mm_Vertical",
                  (xpos, 51), dict(enumerate(nets, 1)), dict(enumerate(labels, 1)), "HAND")
    component("J3", "5V 3A CENTER POSITIVE", "Connector_BarrelJack:BarrelJack_CUI_PJ-102AH_Horizontal",
              (110, 48), {1: "INPUT_5V", 2: "GND", 3: None},
              {1: "CENTER +", 2: "SLEEVE -", 3: "SWITCH NC"}, "HAND", "PJ-102AH")
    component("F1", "3A fuse - inrush review", "Fuse:Fuse_1206_3216Metric",
              (121, 54), {1: "INPUT_5V", 2: "VM"}, mpn="0467003.NR")
    component("D1", "SS34 controller isolation", "Diode_SMD:D_SMA",
              (101, 63), {1: "LOGIC_DIODE", 2: "VM"}, {1: "K", 2: "A"}, mpn="SS34")
    passive("FB1", "Ferrite >=1A low DCR", "LOGIC_DIODE", "LOGIC_5V", (101, 69), "FB")
    component("JP1", "REMOVE FOR USB POWER", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
              (98, 76), {1: "LOGIC_5V", 2: "HELTEC_5V"}, assembly="HAND")
    component("J4", "POWER ALT + GND", "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
              (111, 129), {1: "INPUT_5V", 2: "GND"}, assembly="HAND")
    for reference, net, position in [("C1", "VM", (119, 62)),
                                      ("C2", "LOGIC_5V", (100, 85))]:
        component(reference, "470uF 10V low ESR", "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm",
                  position, {1: net, 2: "GND"}, {1: "+", 2: "-"}, "HAND")
    passive("C3", "100nF 25V X7R", "LOGIC_5V", "GND", (108, 90), "C")
    passive("R1", "10k 1%", "+3V3", "VREF", (108, 98))
    passive("R2", "10k 1%", "VREF", "GND", (108, 102))
    passive("C4", "100nF 25V X7R", "VREF", "GND", (108, 106), "C")
    component("J5", "NC STOP LOOP - OPEN DISABLES BOTH", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
              (98, 113), {1: "+3V3", 2: "ENABLE"}, assembly="HAND")
    passive("R3", "100k", "ENABLE", "GND", (104, 114))
    passive("R4", "47k", "OPEN", "GND", (92, 98))
    passive("R5", "47k", "CLOSE", "GND", (92, 102))
    passive("R6", "10k", "+3V3", "FAULT", (92, 106))
    driver_names = {1: "IN1", 2: "IN2", 3: "nSLEEP", 4: "nFAULT", 5: "VREF",
                    6: "IPROPI", 7: "IMODE", 8: "OUT1", 9: "PGND", 10: "OUT2",
                    11: "VM", 12: "VCP", 13: "CPH", 14: "CPL", 15: "GND",
                    16: "PMODE", 17: "THERMAL PAD"}
    for channel, ypos, index in [("A", 68, 1), ("B", 107, 2)]:
        component("U" + str(index), "DRV8876PWPR", "Package_SO:HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.46x2.31mm_ThermalVias",
                  (139, ypos), {1: "OPEN", 2: "CLOSE", 3: "ENABLE", 4: "FAULT",
                  5: "VREF", 6: "CURRENT_" + channel, 7: None,
                  8: "MOTOR_" + channel + "1", 9: "GND", 10: "MOTOR_" + channel + "2",
                  11: "VM", 12: "VCP_" + channel, 13: "CPH_" + channel,
                  14: "CPL_" + channel, 15: "GND", 16: "+3V3", 17: "GND"},
                  driver_names, mpn="DRV8876PWPR")
        base = index * 10
        passive("C" + str(base), "22nF 25V X7R", "CPH_" + channel,
                "CPL_" + channel, (146, ypos - 3), "C")
        passive("C" + str(base + 1), "100nF 25V X7R", "VCP_" + channel,
                "VM", (146, ypos + 1), "C")
        passive("C" + str(base + 2), "100nF 25V X7R", "VM", "GND", (145, ypos + 5), "C")
        passive("C" + str(base + 3), "10uF 16V X7R", "VM", "GND", (151, ypos + 5), "C")
        passive("R" + str(base), "1.50k 1% ~1A trip", "CURRENT_" + channel,
                "GND", (131, ypos + 4))
        component("J" + str(index + 5), "MOTOR " + channel,
                  "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
                  (165, ypos), {1: "MOTOR_" + channel + "1", 2: "MOTOR_" + channel + "2"},
                  assembly="HAND")
    for index, label, ypos, gpio in [(1, "PIR IN", 108, "PIR_IN"), (2, "PIR OUT", 119, "PIR_OUT_RAW")]:
        component("J" + str(index + 7), label + " 5V OUT GND",
                  "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
                  (47, ypos), {1: "LOGIC_5V", 2: "PIR_RAW_" + str(index), 3: "GND"},
                  {1: "5V", 2: "OUT (3.3V ONLY)", 3: "GND"}, "HAND")
        passive("R" + str(20 + index), "1k", "PIR_RAW_" + str(index), gpio, (55, ypos + 2))
        passive("R" + str(22 + index), "100k", gpio, "GND", (60, ypos + 2))
        passive("C" + str(30 + index), "100nF 25V X7R", gpio, "GND", (65, ypos + 2), "C")
    for index, label, ypos, net in [(1, "OPEN REED", 108, "LIMIT_OPEN"),
                                   (2, "CLOSED REED", 120, "CLOSE_RAW")]:
        component("J" + str(index + 9), label + " SWITCH GND",
                  "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
                  (75, ypos), {1: "REED_RAW_" + str(index), 2: "GND"}, assembly="HAND")
        passive("R" + str(30 + index), "1k", "REED_RAW_" + str(index), net, (83, ypos))
        passive("C" + str(32 + index), "100nF 25V X7R", net, "GND", (83, ypos + 4), "C")
    passive("R40", "0R LEGACY GPIO2", "PIR_OUT_RAW", "PIR_OUT", (68, 125))
    passive("R41", "0R ALT GPIO22 DNP", "PIR_OUT_RAW", "ALT_PIR_22", (68, 129), fitted=False)
    passive("R42", "0R LEGACY GPIO12", "CLOSE_RAW", "LIMIT_CLOSE", (89, 121))
    passive("R43", "0R ALT GPIO27 DNP", "CLOSE_RAW", "ALT_CLOSE_27", (89, 125), fitted=False)
    return PARTS


def self_test():
    circuit()
    references = [part["reference"] for part in PARTS]
    assert len(references) == len(set(references)), "Duplicate component reference"
    lookup = {part["reference"]: part for part in PARTS}
    for reference in ["U1", "U2"]:
        pins = lookup[reference]["pins"]
        assert pins["1"] == "OPEN" and pins["2"] == "CLOSE"
        assert pins["11"] == "VM" and pins["16"] == "+3V3"
        assert pins["7"] is None, "IMODE must float for fixed-off-time, latched OCP"
        assert pins["9"] == pins["15"] == pins["17"] == "GND"
    assert lookup["U1"]["pins"]["8"] != lookup["U2"]["pins"]["8"]
    assert lookup["J1"]["pins"]["10"] == "OPEN"
    assert lookup["J1"]["pins"]["9"] == "CLOSE"
    assert lookup["J2"]["pins"]["2"] == "HELTEC_5V"
    assert lookup["J3"]["pins"]["1"] == "INPUT_5V"
    assert not lookup["R41"]["fitted"] and not lookup["R43"]["fitted"]
    trip = CURRENT_REFERENCE_V / (CURRENT_RESISTANCE_OHM * CURRENT_MIRROR_A_PER_A)
    assert 0.95 < trip < 1.05
    assert 2 * trip + 0.6 < 3, "Nominal supply budget exceeded"
    print("PASS: unique references, Heltec mapping, PWP pinout, isolated outputs, ~1A/motor nominal limit")


def quoted(value):
    return json.dumps(str(value))


def identifier():
    return str(uuid.uuid4())


def schematic():
    root_uuid = identifier()
    libraries, symbols, connections = [], [], []
    for index, part in enumerate(PARTS):
        ref = part["reference"]
        lib_id = "DogDoor:" + ref
        pin_count = len(part["pins"])
        height = (pin_count + 1) * 2.54
        pins = []
        for pin_index, (number, net) in enumerate(part["pins"].items()):
            pin_y = height / 2 - (pin_index + 1) * 2.54
            label = part["names"].get(number, number)
            pins.append(f'(pin passive line (at -15.24 {pin_y:.4f} 0) (length 2.54) '
                        f'(name {quoted(label)} (effects (font (size 1 1)))) '
                        f'(number {quoted(number)} (effects (font (size 1 1)))))')
        libraries.append(f'(symbol {quoted(lib_id)} (pin_names (offset 0.5)) '
                         f'(in_bom yes) (on_board yes) '
                         f'(property "Reference" {quoted(ref)} (at 0 0 0) (effects (font (size 1.27 1.27)))) '
                         f'(property "Value" {quoted(part["value"])} (at 0 0 0) (effects (font (size 1.27 1.27)))) '
                         f'(symbol {quoted(ref + "_0_1")} (rectangle (start -12.7 {height / 2:.4f}) '
                         f'(end 12.7 {-height / 2:.4f}) (stroke (width 0.254) (type default)) (fill (type background)))) '
                         f'(symbol {quoted(ref + "_1_1")} {" ".join(pins)}))')
        column, row = index % 6, index // 6
        xpos, ypos = 55 + column * 92, 48 + row * 65
        symbols.append(f'(symbol (lib_id {quoted(lib_id)}) (at {xpos} {ypos} 0) (unit 1) '
                       f'(in_bom yes) (on_board yes) (dnp {"no" if part["fitted"] else "yes"}) (uuid {identifier()}) '
                       f'(property "Reference" {quoted(ref)} (at {xpos + 14} {ypos - 3} 0) '
                       f'(effects (font (size 1.27 1.27)) (justify left))) '
                       f'(property "Value" {quoted(part["value"])} (at {xpos + 14} {ypos} 0) '
                       f'(effects (font (size 1 1)) (justify left))) '
                       f'(property "Footprint" {quoted(part["footprint"])} (at {xpos} {ypos} 0) '
                       f'(effects (font (size 1 1)) hide)) '
                       f'(instances (project {quoted(NAME)} (path {quoted("/" + root_uuid)} '
                       f'(reference {quoted(ref)}) (unit 1)))))')
        for pin_index, (number, net) in enumerate(part["pins"].items()):
            pin_y = ypos - height / 2 + (pin_index + 1) * 2.54
            pin_x = xpos - 15.24
            if net:
                connections.append(f'(wire (pts (xy {pin_x:.4f} {pin_y:.4f}) '
                                   f'(xy {pin_x - 5.08:.4f} {pin_y:.4f})) '
                                   f'(stroke (width 0) (type default)) (uuid {identifier()}))')
                connections.append(f'(label {quoted(net)} (at {pin_x - 5.08:.4f} {pin_y:.4f} 0) '
                                   f'(effects (font (size 1 1)) (justify left bottom)) (uuid {identifier()}))')
            else:
                connections.append(f'(no_connect (at {pin_x:.4f} {pin_y:.4f}) (uuid {identifier()}))')
    text = (f'(kicad_sch (version 20230121) (generator eeschema) (uuid {root_uuid}) '
            '(paper "A1") (title_block (title "DogDoor REVIEW ONLY - not fabrication approved") '
            '(rev "0.1") (comment 1 "IMODE intentionally floating; PWM mode; nominal 1A per motor")) '
            f'(lib_symbols {" ".join(libraries)}) {" ".join(symbols)} {" ".join(connections)})')
    (OUTPUT / (NAME + ".kicad_sch")).write_text(text, encoding="utf-8")


def board(pcbnew):
    pcb = pcbnew.BOARD()
    pcb.SetCopperLayerCount(2)
    nets = sorted({net for part in PARTS for net in part["pins"].values() if net})
    net_objects = {}
    for number, name in enumerate(nets, 1):
        net = pcbnew.NETINFO_ITEM(pcb, name, number)
        pcb.Add(net)
        net_objects[name] = net
    settings = pcb.GetDesignSettings().m_NetSettings
    settings.m_DefaultNetClass.SetClearance(pcbnew.FromMM(0.25))
    settings.m_DefaultNetClass.SetTrackWidth(pcbnew.FromMM(0.3))
    settings.m_DefaultNetClass.SetViaDiameter(pcbnew.FromMM(0.8))
    settings.m_DefaultNetClass.SetViaDrill(pcbnew.FromMM(0.4))
    power_class = pcbnew.NETCLASS("Motor")
    power_class.SetClearance(pcbnew.FromMM(0.25))
    power_class.SetTrackWidth(pcbnew.FromMM(1.2))
    power_class.SetViaDiameter(pcbnew.FromMM(1.2))
    power_class.SetViaDrill(pcbnew.FromMM(0.6))
    settings.m_NetClasses["Motor"] = power_class
    for name in POWER_NETS:
        net_objects[name].SetNetClass(power_class)
    footprints = {}
    for part in PARTS:
        library, name = part["footprint"].split(":", 1)
        footprint = pcbnew.FootprintLoad(str(LIBRARIES / (library + ".pretty")), name)
        if footprint is None:
            raise RuntimeError("Missing footprint: " + part["footprint"])
        footprint.SetReference(part["reference"])
        footprint.SetFPID(pcbnew.LIB_ID(library, name))
        footprint.SetValue(part["value"])
        footprint.SetPosition(pcbnew.VECTOR2I(*(pcbnew.FromMM(value) for value in part["position"])))
        footprint.SetOrientationDegrees(part["rotation"])
        footprint.Value().SetVisible(False)
        footprint.Reference().SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.8), pcbnew.FromMM(0.8)))
        footprint.Reference().SetTextThickness(pcbnew.FromMM(0.12))
        pcb.Add(footprint)
        pad_numbers = {pad.GetNumber() for pad in footprint.Pads()}
        assert set(part["pins"]).issubset(pad_numbers), (part["reference"], pad_numbers)
        for pad in footprint.Pads():
            net = part["pins"].get(pad.GetNumber())
            if net:
                pad.SetNet(net_objects[net])
        footprints[part["reference"]] = footprint
    for reference in ["U1", "U2"]:
        footprint = footprints[reference]
        pads = {pad.GetNumber(): pad for pad in footprint.Pads() if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD}
        center = footprint.GetPosition()
        for number in ["9", "15"]:
            track = pcbnew.PCB_TRACK(pcb)
            track.SetStart(pads[number].GetPosition())
            track.SetEnd(pcbnew.VECTOR2I(center.x, pads[number].GetPosition().y))
            track.SetWidth(pcbnew.FromMM(0.3))
            track.SetLayer(pcbnew.F_Cu)
            track.SetNet(net_objects["GND"])
            track.SetLocked(True)
            pcb.Add(track)
        for number in ["8", "10", "11"]:
            pad = pads[number]
            start = pad.GetPosition()
            outward = -1 if start.x < center.x else 1
            track = pcbnew.PCB_TRACK(pcb)
            track.SetStart(start)
            track.SetEnd(pcbnew.VECTOR2I(start.x + pcbnew.FromMM(outward * 2), start.y))
            track.SetWidth(pcbnew.FromMM(0.3))
            track.SetLayer(pcbnew.F_Cu)
            track.SetNet(pad.GetNet())
            track.SetLocked(True)
            pcb.Add(track)
    for start, end in [((40, 40), (180, 40)), ((180, 40), (180, 140)),
                       ((180, 140), (40, 140)), ((40, 140), (40, 40))]:
        shape = pcbnew.PCB_SHAPE()
        shape.SetShape(pcbnew.SHAPE_T_SEGMENT)
        shape.SetLayer(pcbnew.Edge_Cuts)
        shape.SetStart(pcbnew.VECTOR2I(*(pcbnew.FromMM(value) for value in start)))
        shape.SetEnd(pcbnew.VECTOR2I(*(pcbnew.FromMM(value) for value in end)))
        shape.SetWidth(pcbnew.FromMM(0.05))
        pcb.Add(shape)
    for index, position in enumerate([(44, 44), (176, 44), (44, 136), (176, 136)], 1):
        hole = pcbnew.FootprintLoad(str(LIBRARIES / "MountingHole.pretty"), "MountingHole_3.2mm_M3")
        hole.SetReference("H" + str(index))
        hole.SetFPID(pcbnew.LIB_ID("MountingHole", "MountingHole_3.2mm_M3"))
        hole.Reference().SetVisible(False)
        hole.SetPosition(pcbnew.VECTOR2I(*(pcbnew.FromMM(value) for value in position)))
        pcb.Add(hole)
    for text, position, size in [("DOGDOOR - REVIEW ONLY", (110, 43), 1.4),
                                 ("USB END", (71, 47), 1),
                                 ("5V ONLY / CENTER +", (129, 46), 1),
                                 ("NC STOP LOOP", (98, 118), 0.8),
                                 ("ANTENNA KEEP-OUT", (72, 103), 0.8),
                                 ("MOTOR A", (166, 77), 1), ("MOTOR B", (166, 116), 1),
                                 ("5V OUT GND", (49, 103), 0.8),
                                 ("OPEN / GND", (75, 101), 0.8),
                                 ("CLOSE / GND", (75, 115), 0.8)]:
        item = pcbnew.PCB_TEXT(pcb)
        item.SetText(text)
        item.SetPosition(pcbnew.VECTOR2I(*(pcbnew.FromMM(value) for value in position)))
        item.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
        item.SetTextThickness(pcbnew.FromMM(0.12))
        item.SetLayer(pcbnew.F_SilkS)
        pcb.Add(item)
    keepout = pcbnew.ZONE(pcb)
    keepout.SetIsRuleArea(True)
    copper_layers = pcbnew.LSET()
    copper_layers.AddLayer(pcbnew.F_Cu)
    copper_layers.AddLayer(pcbnew.B_Cu)
    keepout.SetLayerSet(copper_layers)
    keepout.SetDoNotAllowTracks(True)
    keepout.SetDoNotAllowVias(True)
    keepout.SetDoNotAllowCopperPour(True)
    outline = keepout.Outline()
    outline.NewOutline()
    for xpos, ypos in [(57, 96), (86, 96), (86, 106), (57, 106)]:
        outline.Append(pcbnew.FromMM(xpos), pcbnew.FromMM(ypos))
    pcb.Add(keepout)
    pcbnew.SaveBoard(str(OUTPUT / (NAME + ".kicad_pcb")), pcb)
    return pcb


def exports():
    with (OUTPUT / "bom_review.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Reference", "Value", "Footprint", "Assembly", "MPN", "Populate"])
        for part in PARTS:
            writer.writerow([part[key] for key in ["reference", "value", "footprint", "assembly", "mpn", "fitted"]])
    with (OUTPUT / "placement_review.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for part in PARTS:
            if part["assembly"] == "SMD" and part["fitted"]:
                xpos, ypos = part["position"]
                writer.writerow([part["reference"], xpos - 40, 140 - ypos, "Top", part["rotation"]])
    (OUTPUT / "circuit.json").write_text(json.dumps(PARTS, indent=2) + "\n", encoding="utf-8")
    net_classes = [dict(name="Default", clearance=0.25, track_width=0.3,
                       via_diameter=0.8, via_drill=0.4, microvia_diameter=0.3,
                       microvia_drill=0.1, diff_pair_width=0.3, diff_pair_gap=0.25)]
    motor_class = dict(net_classes[0], name="Motor", track_width=1.2,
                       via_diameter=1.2, via_drill=0.6)
    net_classes.append(motor_class)
    (OUTPUT / (NAME + ".kicad_pro")).write_text(json.dumps({
        "meta": {"filename": NAME + ".kicad_pro", "version": 1},
        "net_settings": {"classes": net_classes, "meta": {"version": 3},
                 "netclass_patterns": [{"netclass": "Motor", "pattern": net} for net in sorted(POWER_NETS)]},
        "board": {"design_settings": {"rules": {"min_clearance": 0.25,
                  "min_track_width": 0.25, "min_via_diameter": 0.6,
                  "min_through_hole_diameter": 0.2, "min_copper_edge_clearance": 0.5}}}
    }, indent=2) + "\n", encoding="utf-8")
    libraries = sorted({part["footprint"].split(":")[0] for part in PARTS} | {"MountingHole"})
    table = [f'(lib (name {quoted(name)}) (type KiCad) '
             f'(uri {quoted(str(LIBRARIES / (name + ".pretty")).replace(chr(92), "/"))}) '
             '(options "") (descr "KiCad 7 standard library"))' for name in libraries]
    (OUTPUT / "fp-lib-table").write_text('(fp_lib_table ' + " ".join(table) + ')\n', encoding="utf-8")


def drc_report(board_path, report_path):
    program = ("import sys,pcbnew; "
               "assert pcbnew.GetSettingsManager().LoadProject(sys.argv[1]); "
               "board=pcbnew.LoadBoard(sys.argv[2]); "
               "assert pcbnew.WriteDRCReport(board,sys.argv[3],pcbnew.EDA_UNITS_MILLIMETRES,True)")
    subprocess.run([str(KICAD / "bin/python.exe"), "-c", program,
                    str(board_path.with_suffix(".kicad_pro")), str(board_path),
                    str(report_path)], check=True)


def verify(pcbnew, pcb):
    cli = KICAD / "bin/kicad-cli.exe"
    netlist = OUTPUT / "schematic.net.xml"
    subprocess.run([str(cli), "sch", "export", "netlist", "--format", "kicadxml",
                    "-o", str(netlist), str(OUTPUT / (NAME + ".kicad_sch"))], check=True)
    actual = {}
    for net in ET.parse(netlist).getroot().findall("./nets/net"):
        if net.attrib["name"].startswith("unconnected-"):
            assert len(net.findall("node")) == 1, "An intended NC pin is connected"
            continue
        for node in net.findall("node"):
            actual[(node.attrib["ref"], node.attrib["pin"])] = net.attrib["name"].lstrip("/")
    expected = {(part["reference"], pin): net for part in PARTS for pin, net in part["pins"].items() if net}
    assert actual == expected, "Parsed schematic connectivity differs from circuit model"
    for footprint in pcb.GetFootprints():
        for pad in footprint.Pads():
            key = (footprint.GetReference(), pad.GetNumber())
            assert pad.GetNetname() == expected.get(key, ""), (key, pad.GetNetname())
    drc_report(OUTPUT / (NAME + ".kicad_pcb"), OUTPUT / "placed_drc.txt")
    print("PASS: schematic and every PCB pad match the circuit model")


def import_routing(pcbnew, pcb, path):
    data = json.loads(path.read_text(encoding="utf-8"))
    nets = pcb.GetNetsByName()
    layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    via_sizes = {"Via[0-1]_800:400_um": (0.8, 0.4),
                 "Via[0-1]_1200:600_um": (1.2, 0.6)}
    def point(position):
        return pcbnew.VECTOR2I(*(pcbnew.FromMM(value) for value in position))
    def key(net, layer, width, start, end):
        return (net, layer, width, tuple(sorted(((start.x, start.y), (end.x, end.y)))))
    existing = {key(track.GetNetname(), track.GetLayer(), track.GetWidth(),
                    track.GetStart(), track.GetEnd()) for track in pcb.GetTracks()}
    added = 0
    for route in data["tracks"]:
        layer, width = layers[route["layer"]], pcbnew.FromMM(route["width"])
        for start, end in zip(route["points"], route["points"][1:]):
            start, end = point(start), point(end)
            signature = key(route["net"], layer, width, start, end)
            if max(abs(start.x - end.x), abs(start.y - end.y)) < pcbnew.FromMM(0.001) or signature in existing:
                continue
            track = pcbnew.PCB_TRACK(pcb)
            track.SetStart(start)
            track.SetEnd(end)
            track.SetLayer(layer)
            track.SetWidth(width)
            track.SetNet(nets[route["net"]])
            pcb.Add(track)
            existing.add(signature)
            added += 1
    for item in data["vias"]:
        diameter, drill = via_sizes[item["padstack"]]
        via = pcbnew.PCB_VIA(pcb)
        via.SetPosition(point(item["position"]))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetWidth(pcbnew.FromMM(diameter))
        via.SetDrill(pcbnew.FromMM(drill))
        via.SetNet(nets[item["net"]])
        pcb.Add(via)
    output = OUTPUT / (NAME + "_routed.kicad_pcb")
    project = output.with_suffix(".kicad_pro")
    settings = json.loads((OUTPUT / (NAME + ".kicad_pro")).read_text(encoding="utf-8"))
    settings["meta"]["filename"] = project.name
    project.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    pcbnew.SaveBoard(str(output), pcb)
    drc_report(output, OUTPUT / "routed_drc.txt")
    print(f"Imported {added} track segments and {len(data['vias'])} vias:", output)


def routing(pcbnew, pcb, executable, java):
    design = OUTPUT / (NAME + ".dsn")
    session = OUTPUT / (NAME + ".ses")
    if not pcbnew.ExportSpecctraDSN(pcb, str(design)):
        raise RuntimeError("DSN export failed")
    if session.exists():
        session.unlink()
    if executable.suffix.lower() == ".jar":
        if java is None:
            runtimes = list((Path(os.environ["LOCALAPPDATA"]) / "DogDoorPCB/java").glob("*/bin/java.exe"))
            if len(runtimes) != 1:
                raise RuntimeError("Provide --java with the portable Java 25 executable")
            java = runtimes[0]
        command = [str(java), "-Djava.awt.headless=true", "-jar", str(executable)]
    else:
        command = [str(executable)]
    command += ["-de", str(design), "-do", str(session), "--gui.enabled=false",
               "--router.autorouter.max_passes=3", "-mt", "1", "--router.optimizer.enabled=false",
               "--router.job_timeout=00:01:30"]
    with (OUTPUT / "freerouting.log").open("w", encoding="utf-8") as log:
        try:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=180)
        except subprocess.TimeoutExpired:
            raise RuntimeError("FreeRouting timed out; diagnostic log retained in generated/freerouting.log")
    if result.returncode or not session.exists():
        raise RuntimeError("FreeRouting failed; see generated/freerouting.log")
    print("FreeRouting session produced:", session)
    print("Import the SES in PCB Editor: File > Import > Specctra Session.")


def main():
    global ROW_SPACING_MM
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--route", type=Path)
    parser.add_argument("--java", type=Path)
    parser.add_argument("--import-routing", type=Path)
    parser.add_argument("--row-spacing", type=float, default=ROW_SPACING_MM)
    args = parser.parse_args()
    ROW_SPACING_MM = args.row_spacing
    self_test()
    if args.self_test:
        return
    try:
        import pcbnew
    except ImportError:
        raise SystemExit("Run generation with KiCad's bin/python.exe; system Python can run --self-test only")
    OUTPUT.mkdir(exist_ok=True)
    schematic()
    pcb = board(pcbnew)
    exports()
    verify(pcbnew, pcb)
    if args.route:
        routing(pcbnew, pcb, args.route, args.java)
    if args.import_routing:
        import_routing(pcbnew, pcb, args.import_routing)
    print("Generated REVIEW ONLY project:", OUTPUT / (NAME + ".kicad_pro"))


if __name__ == "__main__":
    main()