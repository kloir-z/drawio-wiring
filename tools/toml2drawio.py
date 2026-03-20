#!/usr/bin/env python3
"""Convert a TOML wiring-diagram definition to a .drawio file.

Usage:
    python3 tools/toml2drawio.py input.toml [-o output.drawio]

If -o is omitted the output path is derived from the input
(e.g. network.toml → network.drawio).

TOML schema
-----------
See examples/datacenter.toml for a full example and
docs/toml_schema.md for the reference.
"""

import argparse
import os
import sys
import tomllib

# ---------------------------------------------------------------------------
# Resolve library path
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, '..', 'lib'))

from wiring_diagram import (          # noqa: E402
    Topology, edge_style, port_style,
    NaiveRouter, LeftEdgeRouter, ObstacleRouter,
    BG_YELLOW, BG_GREEN, BG_PURPLE, BG_RED, BG_BLUE, BG_GRAY,
)

# ---------------------------------------------------------------------------
# Lookup maps
# ---------------------------------------------------------------------------
_BG_MAP = {
    "yellow": BG_YELLOW, "green": BG_GREEN, "purple": BG_PURPLE,
    "red": BG_RED, "blue": BG_BLUE, "gray": BG_GRAY,
}

_ROUTER_MAP = {
    "naive": NaiveRouter, "left-edge": LeftEdgeRouter,
    "obstacle": ObstacleRouter,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_edge_style(name_or_raw, edge_styles):
    """Return a draw.io style string.

    *name_or_raw* is either a key in *edge_styles* (defined in the TOML
    ``[edge_styles]`` table) or a raw draw.io style string containing ``=``.
    """
    if "=" in name_or_raw:
        return name_or_raw          # raw style passthrough
    if name_or_raw not in edge_styles:
        raise KeyError(f"Unknown edge style '{name_or_raw}'. "
                       f"Define it in [edge_styles].")
    return edge_styles[name_or_raw]


def _resolve_port_style(name_or_raw, port_styles):
    """Return a draw.io port style string."""
    if "=" in name_or_raw:
        return name_or_raw
    if name_or_raw not in port_styles:
        raise KeyError(f"Unknown port style '{name_or_raw}'. "
                       f"Define it in [port_styles].")
    return port_styles[name_or_raw]


def _build_edge_style(spec):
    """Build a draw.io style string from a TOML edge-style spec dict."""
    if isinstance(spec, str) and "=" in spec:
        return spec                 # raw passthrough
    line = spec.get("line", "solid")
    # Extract extra markers (e.g. "solid;double=1" → line="solid", extras="double=1;")
    extras = ""
    if ";" in line:
        parts = line.split(";")
        line = parts[0]
        extras = ";".join(p for p in parts[1:] if p) + ";"
    s = edge_style(
        spec["color"],
        width=spec.get("width", 2),
        line=line,
    )
    return s + extras


def _build_port_style(spec):
    """Build a draw.io port style string from a TOML port-style spec dict."""
    if isinstance(spec, str) and "=" in spec:
        return spec
    return port_style(spec["color"], bold=spec.get("bold", False))


def _resolve_bg(name):
    """Resolve a background style name to a draw.io style string."""
    if "=" in name:
        return name                 # raw passthrough
    if name not in _BG_MAP:
        raise KeyError(f"Unknown background style '{name}'. "
                       f"Choose from: {', '.join(_BG_MAP)}")
    return _BG_MAP[name]


# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------

def load_toml(path):
    """Read and parse a TOML file, returning the dict."""
    with open(path, "rb") as f:
        return tomllib.load(f)


def build_topology(data):
    """Build a Topology from a parsed TOML dict.

    Returns (topology, settings_dict) where settings_dict contains the
    layout / router parameters for to_diagram().
    """
    # -- Resolve style tables --------------------------------------------------
    edge_styles = {}
    for name, spec in data.get("edge_styles", {}).items():
        edge_styles[name] = _build_edge_style(spec)

    port_styles = {}
    for name, spec in data.get("port_styles", {}).items():
        port_styles[name] = _build_port_style(spec)

    # -- Build topology --------------------------------------------------------
    T = Topology()

    for dev in data.get("devices", []):
        dev_id = dev["id"]
        label = dev.get("label", dev_id)
        layer = dev.get("layer")
        bg = _resolve_bg(dev.get("style", "gray"))
        cable_side = dev.get("cable_side", "top")

        if "controllers" in dev:
            # 3-level device
            ctrls = []
            for ctrl in dev["controllers"]:
                cards = []
                for card in ctrl["cards"]:
                    ports = [
                        (p["name"], p.get("sfp", False),
                         _resolve_port_style(p.get("style", "gray"),
                                             port_styles))
                        for p in card["ports"]
                    ]
                    cards.append((card["name"], ports))
                ctrls.append((ctrl["name"], cards))
            T.add_device(dev_id, label=label, style=bg, layer=layer,
                         controllers=ctrls, cable_side=cable_side)

        elif "cards" in dev:
            # Carded device
            cards = []
            for card in dev["cards"]:
                ports = [
                    (p["name"], p.get("sfp", False),
                     _resolve_port_style(p.get("style", "gray"),
                                         port_styles))
                    for p in card["ports"]
                ]
                cards.append((card["name"], ports))
            T.add_device(dev_id, label=label, style=bg, layer=layer,
                         cards=cards, cable_side=cable_side)

        elif "ports" in dev:
            # Flat device
            ports = [
                (p["name"],
                 _resolve_port_style(p.get("style", "gray"), port_styles))
                for p in dev["ports"]
            ]
            T.add_device(dev_id, label=label, style=bg, layer=layer,
                         ports=ports, cable_side=cable_side)
        else:
            raise ValueError(f"Device '{dev_id}' has no ports, cards, "
                             f"or controllers")

    # -- Cables ----------------------------------------------------------------
    for cable in data.get("cables", []):
        style = _resolve_edge_style(cable["style"], edge_styles)
        label = cable.get("label", "")
        layer = cable.get("zone")

        srcs = cable["src"]
        dsts = cable["dst"]
        # Normalise to lists for bulk syntax
        if isinstance(srcs, str):
            srcs = [srcs]
        if isinstance(dsts, str):
            dsts = [dsts]
        if len(srcs) != len(dsts):
            raise ValueError(
                f"cables: src ({len(srcs)}) and dst ({len(dsts)}) "
                f"length mismatch")

        style_name = cable["style"] if "=" not in cable["style"] else None
        for src, dst in zip(srcs, dsts):
            sd, sp = src.rsplit(".", 1)
            dd, dp = dst.rsplit(".", 1)
            T.add_cable(sd, sp, dd, dp, style=style, label=label,
                        layer=layer, style_name=style_name)

    # -- Simple links ----------------------------------------------------------
    for link in data.get("simple_links", []):
        style = _resolve_edge_style(link["style"], edge_styles)
        label = link.get("label", "")
        layer = link.get("zone")
        devs = link["devices"]
        if len(devs) != 2:
            raise ValueError("simple_links.devices must have exactly 2 items")
        T.add_simple_link(devs[0], devs[1], label, style, layer=layer)

    # -- Zone groups -----------------------------------------------------------
    zg_config = {}
    for zg in data.get("zone_groups", []):
        layers = zg["layers"]
        if len(layers) != 2:
            raise ValueError("zone_groups.layers must have exactly 2 items")
        key = (layers[0], layers[1])
        zg_config[key] = zg["groups"]

    # -- Settings --------------------------------------------------------------
    settings = data.get("settings", {})

    return T, settings, edge_styles, zg_config


def topology_to_diagram(T, settings, zone_groups=None):
    """Call T.to_diagram() with parameters from settings dict."""
    router_name = settings.get("router", "obstacle")
    router_cls = _ROUTER_MAP.get(router_name)
    if router_cls is None:
        raise ValueError(f"Unknown router '{router_name}'. "
                         f"Choose from: {', '.join(_ROUTER_MAP)}")

    kwargs = dict(router=router_cls())
    for key in ("layer_gap", "device_gap", "first_layer_y",
                "port_w", "port_h", "page_w", "page_h"):
        if key in settings:
            kwargs[key] = settings[key]
    cl = settings.get("cable_layers", False)
    # Accept true (bool) or "device"/"style" (str)
    if cl is True:
        cl = "device"
    kwargs["cable_layers"] = cl
    if zone_groups:
        kwargs["zone_groups"] = zone_groups

    return T.to_diagram(**kwargs)


def convert(toml_path, output_path=None):
    """End-to-end: TOML file → .drawio file."""
    data = load_toml(toml_path)
    T, settings, edge_styles, zg_config = build_topology(data)
    D = topology_to_diagram(T, settings, zone_groups=zg_config)

    # Legend
    if "legend" in data:
        entries = []
        for entry in data["legend"]:
            style = _resolve_edge_style(entry["style"], edge_styles)
            entries.append((entry["label"], style))
        D.legend(entries)

    if output_path is None:
        output_path = os.path.splitext(toml_path)[0] + ".drawio"
    D.save(output_path)
    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert a TOML wiring-diagram to .drawio")
    parser.add_argument("input", help="Input TOML file")
    parser.add_argument("-o", "--output", default=None,
                        help="Output .drawio file (default: same name as input)")
    args = parser.parse_args()

    out = convert(args.input, args.output)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
