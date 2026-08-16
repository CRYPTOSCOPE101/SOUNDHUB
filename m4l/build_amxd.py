#!/usr/bin/env python3
"""Build SoundHub.amxd — a Max for Live device for the SoundHub marketplace.

An .amxd file is a gzip-compressed JSON document in the Max patch format.
This script assembles the patch programmatically so the layout stays
reviewable in git, and validates the JSON before writing the device.

Usage: python3 build_amxd.py   (writes ./SoundHub.amxd)
"""

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FONT = {"fontname": "Arial", "fontsize": 11.0, "fontface": 0}

def box(maxclass, objid, rect, text=None, **extra):
    b = {"maxclass": maxclass, "id": objid, "patching_rect": rect}
    if text is not None:
        b["text"] = text
    b.update(extra)
    return b

# --- boxes -------------------------------------------------------------------
# js: two inlets (bang -> refresh, int -> 1 suggest / 2 buy / 3 push), four
# outlets (catalog / status / match / push result)
BOXES = [
    box("newobj", "core", [30.0, 100.0, 220.0, 24.0],
        text="js soundhub-device.js",
        numinlets=2, inlettype=["bang", "int"],
        numoutlets=4, outlettype=["", "", "", ""]),
    box("newobj", "live", [300.0, 40.0, 140.0, 24.0],
        text="live.thisdevice",
        numinlets=1, inlettype=[""], numoutlets=1, outlettype=[""]),
    box("newobj", "ctx", [300.0, 90.0, 180.0, 24.0],
        text="live.object @object live_set",
        numinlets=1, inlettype=[""], numoutlets=1, outlettype=[""]),
    # file writer (auto-import): writes downloaded asset bytes to the User
    # Library. Named so the js script can message it via getnamed().
    box("newobj", "filebox", [300.0, 140.0, 120.0, 24.0],
        text="file @name filebox",
        numinlets=1, inlettype=[""], numoutlets=1, outlettype=[""]),
    # Live file browser: refresh / navigate so imported files appear.
    box("newobj", "browserbox", [300.0, 190.0, 150.0, 24.0],
        text="live.browser @name browserbox",
        numinlets=1, inlettype=[""], numoutlets=1, outlettype=[""]),
    # buttons -> prepend converts bang into an int for the js int inlet
    box("button", "btnLoad", [30.0, 50.0, 30.0, 30.0],
        numoutlets=1, outlettype=["bang"]),
    box("newobj", "mapLoad", [70.0, 50.0, 90.0, 24.0],
        text="prepend bang", numinlets=1, inlettype=[""], numoutlets=1, outlettype=[""]),
    box("button", "btnSuggest", [170.0, 50.0, 30.0, 30.0],
        numoutlets=1, outlettype=["bang"]),
    box("newobj", "mapSuggest", [210.0, 50.0, 90.0, 24.0],
        text="prepend 1", numinlets=1, inlettype=[""], numoutlets=1, outlettype=[""]),
    box("button", "btnBuy", [310.0, 50.0, 30.0, 30.0],
        numoutlets=1, outlettype=["bang"]),
    box("newobj", "mapBuy", [350.0, 50.0, 90.0, 24.0],
        text="prepend 2", numinlets=1, inlettype=[""], numoutlets=1, outlettype=[""]),
    box("button", "btnPush", [450.0, 50.0, 30.0, 30.0],
        numoutlets=1, outlettype=["bang"]),
    box("newobj", "mapPush", [490.0, 50.0, 90.0, 24.0],
        text="prepend 3", numinlets=1, inlettype=[""], numoutlets=1, outlettype=[""]),
    box("comment", "l1", [30.0, 20.0, 60.0, 16.0], text="refresh", **FONT),
    box("comment", "l2", [170.0, 20.0, 70.0, 16.0], text="suggest", **FONT),
    box("comment", "l3", [310.0, 20.0, 50.0, 16.0], text="load", **FONT),
    box("comment", "l5", [450.0, 20.0, 60.0, 16.0], text="push", **FONT),
    box("comment", "l4", [30.0, 140.0, 500.0, 16.0],
        text="SoundHub — don't generate, buy · push current export (needs `snd serve` running)", **FONT),
    box("text", "dispCatalog", [30.0, 160.0, 550.0, 140.0], text="catalog", **FONT),
    box("text", "dispStatus", [30.0, 310.0, 550.0, 60.0], text="status", **FONT),
    box("text", "dispMatch", [30.0, 380.0, 550.0, 40.0], text="match", **FONT),
]

# (src_id, src_outlet, dst_id, dst_inlet)
LINES = [
    ("btnLoad", 0, "mapLoad", 0),
    ("mapLoad", 0, "core", 0),          # bang -> refresh catalog
    ("btnSuggest", 0, "mapSuggest", 0),
    ("mapSuggest", 0, "core", 1),       # int 1 -> suggest for BPM
    ("btnBuy", 0, "mapBuy", 0),
    ("mapBuy", 0, "core", 1),           # int 2 -> buy last suggestion
    ("btnPush", 0, "mapPush", 0),
    ("mapPush", 0, "core", 1),          # int 3 -> push current export
    ("ctx", 0, "core", 1),              # live context -> js int inlet (spare)
    ("core", 0, "dispCatalog", 0),      # catalog json
    ("core", 1, "dispStatus", 0),       # status
    ("core", 2, "dispMatch", 0),        # bpm match tag / push review url
    # core outlet 3 (push JSON contract) is unwired in the patch — available
    # for scripting; the human-readable result already lands on status/match
]


def main() -> int:
    patch = {
        "patcher": {
            "appversion": {"major": 8, "minor": 6, "filename": "Max"},
            "boxes": BOXES,
            "lines": [
                {"source": [src, o], "destination": [dst, i], "order": 0}
                for src, o, dst, i in LINES
            ],
        },
    }
    json.dumps(patch)  # validate
    out = ROOT / "SoundHub.amxd"
    with gzip.open(out, "wt", encoding="utf-8") as f:
        json.dump(patch, f)
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
