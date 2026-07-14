from __future__ import annotations


GATE_IOS: dict[str, tuple[str, ...]] = {
    # Remaining positional arguments default to input.
    "and": ("output",),
    "buf": ("output",),
    "bufif0": ("output",),
    "bufif1": ("output",),
    "cmos": ("output",),
    "nand": ("output",),
    "nmos": ("output",),
    "nor": ("output",),
    "not": ("output",),
    "notif0": ("output",),
    "notif1": ("output",),
    "or": ("output",),
    "pmos": ("output",),
    "pulldown": ("output",),
    "pullup": ("output",),
    "rcmos": ("output",),
    "rnmos": ("output",),
    "rpmos": ("output",),
    "rtran": ("inout", "inout"),
    "rtranif0": ("inout", "inout"),
    "rtranif1": ("inout", "inout"),
    "tran": ("inout", "inout"),
    "tranif0": ("inout", "inout"),
    "tranif1": ("inout", "inout"),
    "xnor": ("output",),
    "xor": ("output",),
}

GATE_PRIMITIVES = frozenset(GATE_IOS)
