# DogDoor carrier PCB: engineering review draft

**Do not order this revision.** This is a reproducible design/routing exercise,
not a fabrication-approved or safety-certified door controller. No order is
placed, and no production Gerber ZIP is supplied until the checks below pass.
The existing firmware is unchanged.

## Open the project

Open `generated/dogdoor_review.kicad_pro` in KiCad 7. The project includes an
editable schematic, a placed board, a circuit manifest, and review BOM/placement
CSVs. The schematic uses embedded pin-by-pin review symbols, so it does not
need a downloaded symbol library. Footprints use your installed KiCad libraries.
The board is intentionally roomy: 140 x 100 mm, two copper layers.

## Confirmed requirements and assumptions

- Heltec WiFi Kit 32 V2, two 18-pin rows, USB end toward the top of the PCB.
- Along-row pitch is 2.54 mm (0.1 inch).
- Row separation is your confirmed **22.86 mm center-to-center (0.9 inch)**.
   Print `generated/socket_fit_check.pdf` at 100% and compare the real module
   as a final check before ordering; header sockets still need adequate height.
- Regulated 5 V, 3 A adapter, 2.1 mm center-positive plug.
- Two yellow TT motors, separate electrical outputs, same direction commands.
  They are NOT connected electrically in parallel on this PCB.
- HC-SR501 PIR outputs are assumed to be 3.3 V, not 5 V. Measure them first.
- Factory assembles fitted SMD parts; you solder sockets, connectors, and bulk
  capacitors. Sensor headers can be omitted and wires soldered into their holes.

## Circuit choices

U1/U2 are TI **DRV8876PWPR** HTSSOP MOSFET bridges. PMODE is HIGH for two-input
PWM control, compatible with the existing GPIO25/GPIO26 direction interface.
Both LOW means **coast**, not braking. Never assume the winch holds the door
when power is off: provide mechanical retention and independent obstruction
protection. Driver outputs must never be connected together.

Each bridge has a nominal **1.0 A current limit**, not a 2 A setting. VREF is
nominally 1.65 V from a 10k/10k divider on the Heltec 3.3 V output. A 1.50k
IPROPI resistor and the datasheet's 1100 uA/A current mirror give:

`Itrip = 1.65 / (1500 * 0.0011) = 1.0 A`

This is winding current regulation, not a precise total adapter-current limit.
Sense tolerance, startup overshoot, capacitor inrush, motor loading, and ESP32
Wi-Fi consumption still require bench measurement. Two TT motors can exceed
the 3 A supply at stall without limiting. The limited motors may not lift the
door. Do not raise the limit blindly; measure load and reassess supply/thermal
requirements. The driver's 3.5 A specification is a peak rating, not permission
to run that current continuously on this layout.

IMODE floats intentionally: fixed-off-time chopping with latched-off overcurrent
protection. Do not add a pull-down there. Removing/reclosing the stop loop resets
sleep and can re-enable the outputs if the firmware still commands movement.

J5 is a normally-closed stop-loop connection to nSLEEP. With it open, both
drivers are disabled. This is a bench inhibit, not a certified emergency stop;
it causes coasting and does not cut power. Use a proper motor-power disconnect
and mechanical safety measures for the installed door.

VM is fed through a 3 A fuse. The driver requires **at least 4.5 V at its VM pin**:
your nominal 5 V leaves only 0.5 V for adapter sag, cable, jack, fuse, and traces.
Measure under simultaneous starting and worst permitted load. F1 requires an
inrush/time-current review; it does not regulate current or protect an animal.
There is **no reverse-polarity or wrong-voltage protection** in this draft.
Do not plug an Arduino 9 V/12 V adapter into the same-looking socket.

The controller branch uses SS34 isolation, a low-DCR ferrite, 470 uF, and ceramic
decoupling. It shares the adapter with VM: filtering does not fix sustained supply
sag. JP1 disconnects the Heltec 5 V feed. Remove JP1 before powering by USB;
do not rely on the carrier diode to resolve the Heltec's internal power paths.
Confirm the revision-specific Heltec schematic before simultaneous power sources.

The bridges have 22 nF charge-pump flying capacitors, 100 nF VCP-to-VM capacitors,
100 nF VM bypasses, and 10 uF local ceramics. Add 100 nF suppression capacitors
directly at each motor, with short leads and twisted motor wires. The bulk
capacitors do not substitute for short, low-resistance motor power wiring.

GPIO35 receives the combined open-drain fault outputs. GPIO34 and GPIO36 receive
the two current-sense signals. Existing firmware does not read these signals:
do not assume an automatic stop on driver fault or excessive load is implemented.

## Connection table

| Reference | Connection |
| --- | --- |
| J1/J2 | Female Heltec sockets; pin 1 at USB end on each row |
| J3 | CUI PJ-102AH, center-positive 5 V only, 2.1 mm |
| J4 | Alternate power screw terminal: pin 1 +5 V, pin 2 GND; use ONE input |
| J6 | Motor A: pins 1/2 motor leads |
| J7 | Motor B: pins 1/2 motor leads; swap one motor's leads if mechanically opposed |
| J8/J9 | PIR inside/outside: pin 1 +5 V, pin 2 OUT (3.3 V only), pin 3 GND |
| J10/J11 | Open/closed reed: pin 1 switch signal, pin 2 GND; passive contacts only |
| J5 | Normally-closed bench inhibit loop; open = both bridges disabled |
| JP1 | Shunt for carrier-powered Heltec; REMOVE before USB power |

Socket row labels and numbers come from the local V2 pinout PDF, not from a
generic ESP32 DevKit footprint. Vext, OLED pins, and unused module pins are left
unconnected. Only one module 3.3 V header pin feeds the reference/control circuit.

GPIO2 and GPIO12 are boot straps. The fitted R40/R42 zero-ohm links preserve the
current firmware, but cold boots must be tested with PIR HIGH/LOW and reed open/
closed. No external pull-up is added to GPIO12. Before production, prefer moving
PIR_OUT to GPIO22 and LIMIT_CLOSE to GPIO27: remove R40/R42, fit R41/R43, and
change the corresponding firmware constants. Never fit both options at once.

## Generate again

From the workspace root in PowerShell:

```powershell
& 'C:/Program Files/Python311/python.exe' hardware/generate.py --self-test
& 'D:/Program Files/KiCad/7.0/bin/python.exe' hardware/generate.py
& 'D:/Program Files/KiCad/7.0/bin/python.exe' hardware/generate.py --row-spacing 22.86
& 'D:/Program Files/KiCad/7.0/bin/python.exe' hardware/generate.py --route "$env:LOCALAPPDATA/DogDoorPCB/freerouting-2.5.0/freerouting-2.5.0.jar"
& 'C:/Program Files/Python311/python.exe' hardware/review.py
& 'C:/Program Files/Python311/python.exe' hardware/review.py --session hardware/generated/dogdoor_review.ses
& 'D:/Program Files/KiCad/7.0/bin/python.exe' hardware/generate.py --import-routing hardware/generated/dogdoor_review.routing.json
```

**Generation overwrites generated files, including manual PCB edits.** Make a
separate working copy of the project before editing. The generator checks circuit
assignments, KiCad-parsed schematic connectivity, and all assigned PCB pads.
It does not certify analog behavior, footprint fit, component sourcing, or safety.

FreeRouting 2.5.0 was downloaded from the official GitHub release and checked
against its published SHA-256. Its native Windows build crashed on board snapshot
serialization, so use the JAR with a portable Java 25 runtime under local app-data.
The generator discovers that runtime automatically; `--java` can override it.
Your existing system Java installation is unchanged.

## Routing and remaining PCB work

The generator exports DSN and FreeRouting produces SES. In PCB Editor, use
**File > Import > Specctra Session** to import `dogdoor_review.ses`, then save.
The autorouter is a layout assistant, not electrical sign-off.

1. **Fit first.** Print a 1:1 board drawing with scaling disabled; verify the
   printed 2.54 mm pitch and row spacing with a ruler, then compare your module.
   Measure pin centers, not outside edges. Both rows must enter female sockets
   without bending pins. Verify USB overhang/access and antenna position.
2. **Power paths.** Highlight INPUT_5V, VM, MOTOR_A1/A2, and MOTOR_B1/B2. Their
   draft net class requests 1.2 mm tracks and larger vias; the tiny HTSSOP pads
   need short 0.3 mm escape sections. Review actual copper width, neck-down
   length, via ampacity, voltage drop, and temperature, not only net-class names.
   Use wider copper pours for the 3 A feeder where practical. Route each motor's
   return through the driver/ground plane, not through the module/sensor area.
3. **Ground and heat.** Add continuous GND pours on both layers and refill with
   B. Connect U1/U2 exposed pads and nearby ground pins to substantial copper,
   with thermal vias and stitching. Do not make the ESP32 ground path the sole
   motor return. Confirm copper area against TI's layout/thermal guidance. The
   standard footprint includes 0.2 mm thermal drills: confirm fabricator support
   and solder-wicking/paste requirements with the assembly house.
4. **Critical capacitors.** Inspect C10/C20 (CPH-CPL), C11/C21 (VCP-VM), and
   C12/C22 (VM-GND). Short direct loops matter; fix router detours around these
   pins. R10/R20 should connect directly to IPROPI and local quiet ground. Keep
   VREF/current-sense signals away from motor switching paths.
5. **Antenna.** Confirm the actual antenna outline. The draft bottom-of-module
   keep-out excludes copper/tracks/vias on both layers. Expand or move it to the
   module maker's required region; avoid nearby metal, motors, and enclosure walls.
6. **Rules and labels.** Run Inspect > Design Rules Checker. Fix every clearance,
   short, unrouted connection, courtyard conflict, and edge violation; review
   warnings individually. Do not blindly exclude errors. Move silk away from pads,
   enlarge illegible labels, and mark polarity/pin 1 clearly. Check the socket's
   female numbering versus the view in the PDF, not only 3D appearance.
7. **Schematic checks.** Run schematic ERC manually (KiCad 7 has no CLI ERC here).
   The embedded review symbols use passive pins and therefore do not catch all
   electrical-type mistakes; independently review the TI PWP pinout and every
   power/control connection. Do not update the PCB from a generic replacement
   symbol without checking pin mapping and footprint association.

## Actual routing result and repairs

**Latest manually repaired board:** `generated/dogdoor_review_routed.kicad_pcb`.
The saved `generated/DRC.rpt` dated 2026-10-12 reports zero DRC violations,
zero unconnected pads, and zero footprint errors. The following routing counts
describe the initial autorouter output, before those manual repairs. Clean DRC
does not approve motor-current capacity, thermal layout, sourcing, or safety.
Do not regenerate or reimport the old routing session over the repaired board.

Open `generated/dogdoor_review_routed.kicad_pro` for the routed draft. The placed
project is separate. Regeneration overwrites both, so make a copy before manual
layout work. `review.py` requires PyMuPDF and sexpdata in system Python, while
`generate.py` uses KiCad's bundled Python.

The Java FreeRouting run completed three passes and reported 12 unrouted items
with no router-rule violations. The imported KiCad board contains 43 vias.
KiCad's independent `generated/routed_drc.txt` identifies **8 missing connections,
50 minimum-track-width errors, and 12 dangling-track/via warnings**. No clearance,
short-circuit, or footprint errors were reported. This is not a clean DRC result.

In PCB Editor, run Inspect > Design Rules Checker, click each item to locate it,
and use Highlight Net to follow the intended connection. Route with X from the
existing pad/track endpoint, not from an approximate point on the drawing.

| Unfinished net | Starting point / repair target |
| --- | --- |
| CLOSE | R5 pad 1 to the existing CLOSE route |
| FAULT | U2 pad 4 to the existing shared FAULT route |
| GND | Join the driver-area ground islands with properly reviewed ground copper |
| MOTOR_A2 | U1 OUT2/pad 10 escape to J6 pad 2 |
| MOTOR_B2 | U2 OUT2/pad 10 escape to J7 pad 2 |
| VM (three gaps) | Connect both VM/pad 11 escapes, local C11/C21 VM pads, and the shared motor supply |

FreeRouting necked down some routes to **0.15 mm**, narrower than the board's
**0.25 mm minimum**. Reroute/widen those sections; do not just lower the rule or
exclude the errors. Motor/power copper needs the wider 1.2 mm nominal route
outside short pad escapes, with further voltage-drop/thermal review as above.
Some preplaced escape stubs are locked: unlock only the affected track before
editing, preserving the IC pin-to-net connection. Remove genuinely unused stub
ends and one-layer-only vias after completing their nets, then rerun DRC.

## Factory assembly and ordering gate

The review BOM deliberately says REVIEW_REQUIRED for unselected supplier parts.
It is **not an upload-ready JLCPCB BOM**. Choose an assembly house, reserve actual
stock, and verify exact manufacturer part numbers, packages, voltage ratings,
capacitor DC-bias derating, ferrite DCR/current rating, jack current rating, and
connector hole sizes. Confirm DRV8876PWPR, not a different QFN package.

The placement CSV uses a bottom-left board origin with positive Y upward, top
side only. Factory rotation conventions vary: verify every pin-1/polarity preview,
especially the ICs and diode. Through-hole connectors and electrolytics are
marked HAND, and R41/R43 are DNP. Match the approved board version to BOM/CPL.

Only after independent electrical/layout review, fit checks, BOM review, and
zero unresolved manufacturing DRC errors should you plot Gerbers and Excellon
drills from the approved board. Inspect them in GerbView and the manufacturer's
preview. Request a small prototype batch, not a production run. This exercise
does not include paying for or submitting an order.

## First prototype bring-up

1. Keep the door mechanism disconnected. Remove the module, both motors, JP1,
   and the J5 inhibit loop. Inspect solder/polarity and check for power shorts.
2. Use a current-limited bench supply for first power-on; verify VM and filtered
   5 V before inserting the module. The ordinary 3 A adapter is not a substitute
   for a bench current limit during initial fault finding.
3. Power off, insert the module in the confirmed orientation, and enable its
   selected power path. Check 3.3 V, VREF (~1.65 V), nSLEEP LOW with J5 open,
   and output coasting. Leave the motor terminals unconnected for logic testing.
4. Connect one unloaded motor, enable J5, and pulse a direction briefly. Verify
   polarity, stop-loop behavior, sense current, and supply minimum voltage.
   Repeat for the other motor before running both. Do not deliberately hold a
   motor stalled to test the limit; use controlled load equipment.
5. Add suppression capacitors at the motors, verify both drive the drum in the
   same mechanical direction, then measure simultaneous-start and loaded current.
   Monitor IC/fuse/connector temperature and ESP32 reset behavior. Stop if the
   VM supply drops below specification or the assembly heats excessively.
6. Verify all cold-boot sensor states, both limits, wire-break cases, inhibit,
   OTA, Wi-Fi loss, and power-off behavior. Current firmware has no debug run
   timeout and ignores the new current/fault inputs; fix the safety behavior
   before connecting a working door. PIRs are not obstruction safety sensors.

## References

- Local `../WIFI_Kit_32_pinoutDiagram_V2.pdf` and V2 schematic.
- TI DRV8876 datasheet: https://www.ti.com/lit/ds/symlink/drv8876.pdf
- FreeRouting releases: https://github.com/freerouting/freerouting/releases