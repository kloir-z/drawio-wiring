# -- Color palette ---------------------------------------------------------
# Rich color palette for wiring diagrams. Pick colors from here when scripting.
# Each entry: (edge strokeColor, port fillColor, port strokeColor)
PALETTE = {
    # ── Primary (1系) ──
    "red":         ("#E03030", "#f8cecc", "#b85450"),
    "orange":      ("#FF8000", "#ffe6cc", "#d79b00"),
    "yellow":      ("#D6B656", "#fff2cc", "#d6b656"),
    "lime":        ("#7AB648", "#e6f5d0", "#7AB648"),
    "green":       ("#52A352", "#d5e8d4", "#82b366"),
    "teal":        ("#00A89D", "#ccf2f0", "#00897B"),
    "cyan":        ("#00B0F0", "#ddf4ff", "#0097CC"),
    "blue":        ("#0070C0", "#dae8fc", "#6c8ebf"),
    "navy":        ("#3A5FA0", "#b3cde3", "#3a5fa0"),
    "indigo":      ("#5C4DB1", "#d9d2f0", "#5C4DB1"),
    "purple":      ("#9673A6", "#e1d5e7", "#9673a6"),
    "magenta":     ("#CC3399", "#f5d0e6", "#a8286b"),
    "pink":        ("#F06090", "#fce4ec", "#d84a6e"),
    "brown":       ("#8B5E3C", "#efdbcb", "#795548"),
    "gray":        ("#888888", "#f5f5f5", "#999999"),
    "dark":        ("#444444", "#e0e0e0", "#555555"),
    # ── Light (2系) ──
    "red_lt":      ("#F0A0A0", "#fef0f0", "#d8a0a0"),
    "orange_lt":   ("#FFC888", "#fff6ec", "#e0b870"),
    "yellow_lt":   ("#F0E0A0", "#fffcf0", "#d8d098"),
    "lime_lt":     ("#B8E0A0", "#f4fcec", "#a8d098"),
    "green_lt":    ("#98D898", "#ecf8ec", "#80c080"),
    "teal_lt":     ("#80D8D0", "#e8fcf8", "#68c0b8"),
    "cyan_lt":     ("#80DCF8", "#ecf8ff", "#60c0e0"),
    "blue_lt":     ("#80B8E0", "#ecf4ff", "#90bcd8"),
    "navy_lt":     ("#90A8D0", "#e0e8f4", "#80a0c0"),
    "indigo_lt":   ("#A898D8", "#ece8f8", "#9888c8"),
    "purple_lt":   ("#C8B0D8", "#f4f0f8", "#b8a0c8"),
    "magenta_lt":  ("#E898D0", "#fef0f8", "#d080b0"),
    "pink_lt":     ("#F8B0C8", "#fef4f8", "#e8a0b0"),
    "brown_lt":    ("#C8A890", "#f8f0e8", "#b0a088"),
    "gray_lt":     ("#C0C0C0", "#fcfcfc", "#c8c8c8"),
    "dark_lt":     ("#909090", "#f2f2f2", "#a0a0a0"),
}


# -- Line style presets ----------------------------------------------------
# Name → dashPattern string. None = solid line.
LINE_STYLES = {
    "solid":    None,           # ────────────
    "dashed":   "8 4",          # ── ── ── ──
    "dotted":   "3 1",          # ·· ·· ·· ··
    "dash-dot": "8 3 2 3",      # ──·──·──·──
    "long":     "12 6",         # ———  ———  ——
    "short":    "4 3",          # ─ ─ ─ ─ ─ ─
}


def edge_style(color_name, width=2, line="solid", dashed=False, dash_pattern="8 4"):
    """Generate an edge style string.

    Args:
        color_name: Key in PALETTE.
        width: Stroke width (default 2).
        line: Line style name ("solid","dashed","dotted","dash-dot","long","short").
        dashed: If True, use dashed line (kept for backward compatibility; line= takes priority).
        dash_pattern: Dash pattern when dashed=True (kept for backward compatibility).

    Returns:
        draw.io style string, e.g. "strokeColor=#FF8000;strokeWidth=2;"
    """
    stroke = PALETTE[color_name][0]
    s = f"strokeColor={stroke};strokeWidth={width};"

    # Explicit line= takes priority over legacy dashed= flag
    if line != "solid":
        pattern = LINE_STYLES.get(line)
        if pattern:
            s += f"dashed=1;dashPattern={pattern};"
    elif dashed:
        s += f"dashed=1;dashPattern={dash_pattern};"
    return s


def port_style(color_name, bold=False):
    """Generate a port style string.

    Args:
        color_name: Key in PALETTE.
        bold: If True, use bold font (default False).

    Returns:
        draw.io style string, e.g. "fillColor=#dae8fc;strokeColor=#6c8ebf;"
    """
    fill, stroke = PALETTE[color_name][1], PALETTE[color_name][2]
    s = f"fillColor={fill};strokeColor={stroke};"
    if bold:
        s += "fontStyle=1;"
    return s


# -- Legacy port style constants (kept for backward compatibility) ---------
PORT_BLUE  = port_style("blue")
PORT_NAVY  = port_style("navy", bold=True)
PORT_GREEN = port_style("green")
PORT_RED   = port_style("red")

# -- Legacy edge style constants (kept for backward compatibility) ---------
EDGE_BLUE   = edge_style("blue", width=2)
EDGE_NAVY   = edge_style("navy", width=3)
EDGE_GREEN  = edge_style("green", width=1.5)
EDGE_RED    = edge_style("red", width=2, dashed=True)
EDGE_ACCENT = edge_style("yellow", width=3, dashed=True, dash_pattern="8 8")

# -- Container / misc style constants -------------------------------------
PORT_GRAY  = port_style("gray")
BG_YELLOW  = "fillColor=#fff2cc;strokeColor=#d6b656;"
BG_GREEN   = "fillColor=#d5e8d4;strokeColor=#82b366;"
BG_PURPLE  = "fillColor=#e1d5e7;strokeColor=#9673a6;"
BG_RED     = "fillColor=#f8cecc;strokeColor=#b85450;"
BG_BLUE    = "fillColor=#d4e1f5;strokeColor=#3a5fa0;"
BG_GRAY    = "fillColor=#f5f5f5;strokeColor=#666666;"
CARD_STYLE = "fillColor=#f0f0f0;strokeColor=#aaaaaa;"  # NIC card sub-container
CTRL_STYLE = "fillColor=#e8edf2;strokeColor=#7a8fa6;"  # Controller sub-container
SFP_STYLE  = "fillColor=#b8c4cc;strokeColor=#4a5560;"  # SFP module
