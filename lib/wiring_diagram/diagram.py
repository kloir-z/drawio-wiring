"""Diagram class — mxGraph XML builder for physical wiring diagrams."""

import math
import xml.etree.ElementTree as ET

from .ids import nid
from .styles import CARD_STYLE, CTRL_STYLE, SFP_STYLE
from .routing import (NaiveRouter, ObstacleRouter,
                      _spread_vertical_segments, _straighten_port_entry)


def _label_h(label, container_w, font_size=11, h_pad=16):
    """Estimate label height accounting for text wrapping in container."""
    char_w = font_size * 0.65
    avail_w = max(1, container_w - h_pad)
    n_lines = 0
    for line in label.split('\n'):
        line_w = len(line) * char_w
        n_lines += max(1, math.ceil(line_w / avail_w))
    return n_lines * (font_size + 3) + 6


class Diagram:
    """mxGraph XML builder for physical wiring diagrams.

    Args:
        page_w:       Page width in pixels.
        page_h:       Page height in pixels.
        route_y_min:  Top Y of the cable routing zone.
        route_y_max:  Bottom Y of the cable routing zone.
        router:       Routing strategy (default: NaiveRouter).
    """

    def __init__(self, page_w: int, page_h: int,
                 route_y_min: float, route_y_max: float,
                 router=None):
        self.route_y_min = route_y_min
        self.route_y_max = route_y_max
        self.route_range = route_y_max - route_y_min
        self.router = router or NaiveRouter()

        self.mxfile = ET.Element("mxfile", host="app.diagrams.net")
        d = ET.SubElement(self.mxfile, "diagram", name="Network", id="p1")
        m = ET.SubElement(d, "mxGraphModel",
            dx=str(page_w), dy=str(page_h),
            grid="1", gridSize="10", guides="1",
            tooltips="1", connect="1", arrows="1", fold="1", page="1",
            pageScale="1", pageWidth=str(page_w), pageHeight=str(page_h))
        self.R = ET.SubElement(m, "root")
        ET.SubElement(self.R, "mxCell", id="0")
        ET.SubElement(self.R, "mxCell", id="1", parent="0")
        self._edge_zones = {}  # (zone, layer) -> list of edge tuples
        self._device_boxes = []  # list of (x, y, w, h) bounding boxes
        self._layers = {}  # layer_name -> cell_id

    # -- backwards compat property --
    @property
    def edges(self):
        return self._edge_zones.setdefault((None, None), [])

    @edges.setter
    def edges(self, value):
        self._edge_zones[(None, None)] = value

    def add_layer(self, name):
        """Add a named layer and return its cell id. Idempotent."""
        return self._get_layer_id(name)

    def _get_layer_id(self, layer_name):
        """Return cell_id for *layer_name*, creating the mxCell if needed."""
        if layer_name is None:
            return "1"
        if layer_name in self._layers:
            return self._layers[layer_name]
        cell_id = f"layer_{nid('ly').split('_', 1)[1]}"
        ET.SubElement(self.R, "mxCell", id=cell_id,
                      value=layer_name, parent="0")
        self._layers[layer_name] = cell_id
        return cell_id

    def container(self, cid, label, x, y, w, h, style,
                  valign="top", parent_id="1", connectable="0",
                  font_size=11, bold=True, spacing_top=2, spacing_bottom=0):
        """Add a rectangular container cell. Returns cid."""
        fstyle = 1 if bold else 0
        sp = f"spacingTop={spacing_top};"
        if spacing_bottom:
            sp += f"spacingBottom={spacing_bottom};"
        c = ET.SubElement(self.R, "mxCell", id=cid, value=label,
            style=(f"rounded=1;whiteSpace=wrap;html=1;container=1;collapsible=0;"
                   f"fontStyle={fstyle};fontSize={font_size};{sp}"
                   f"verticalAlign={valign};{style}"),
            vertex="1", connectable=connectable, parent=parent_id)
        g = ET.SubElement(c, "mxGeometry", x=str(x), y=str(y),
                          width=str(w), height=str(h))
        g.set("as", "geometry")
        return cid

    def device(self, cid, label, x, y, style, ports,
               port_w=16, port_h=14, port_spacing=3,
               pad_x=8, pad_top=34, min_h=None, parent_id="1",
               show_port_labels=True, sublabel=None, sublabel_h=14):
        """Add a device container with ports in a single horizontal row.

        Returns:
            dict: port_label -> (port_id, abs_cx, abs_cy)
        """
        n = len(ports)
        w = pad_x * 2 + n * port_w + max(0, n - 1) * port_spacing
        sub_extra = (sublabel_h + 4) if sublabel else 0
        h = max(min_h or 0, pad_top + port_h + pad_x + sub_extra)
        self._device_boxes.append((x, y, w, h))
        self.container(cid, label, x, y, w, h, style, parent_id=parent_id)
        result = {}
        for i, (plabel, pid, pstyle) in enumerate(ports):
            px = pad_x + i * (port_w + port_spacing)
            cell_label = plabel if show_port_labels else ""
            self.port(pid, cell_label, px, pad_top, cid, pstyle, w=port_w, h=port_h)
            abs_cx = x + px + port_w / 2
            abs_cy = y + pad_top + port_h / 2
            result[plabel] = (pid, abs_cx, abs_cy)
        if sublabel:
            sub_y = pad_top + port_h + 4
            t = ET.SubElement(self.R, "mxCell", id=nid("sub"), value=sublabel,
                style=(f"text;html=1;align=center;verticalAlign=middle;"
                       f"whiteSpace=wrap;fontSize=8;fontColor=#555555;"),
                vertex="1", parent=cid)
            g = ET.SubElement(t, "mxGeometry",
                              x=str(pad_x), y=str(sub_y),
                              width=str(w - pad_x * 2), height=str(sublabel_h))
            g.set("as", "geometry")
        return result

    def device_carded(self, cid, label, x, y, style, cards=None,
                      controllers=None, cable_side="top",
                      port_w=14, port_h=12, port_spacing=4,
                      sfp_w=8, sfp_h=6, sfp_gap=1,
                      card_pad_x=6, card_gap=8,
                      sfp_side_pad=4, label_side_pad=18,
                      dev_pad_x=8, dev_label_h=None, dev_inner_pad=4, dev_pad_bottom=6,
                      ctrl_pad_x=8, ctrl_label_h=18, ctrl_pad_top=4, ctrl_pad_bottom=6,
                      ctrl_gap=12,
                      parent_id="1"):
        """Add a device with NIC-card sub-containers holding ports and SFP modules.

        Args:
            cards:       2-level structure: list of (card_label, port_defs).
                         Mutually exclusive with controllers.
            controllers: 3-level structure: list of (ctrl_label, cards) where
                         cards has the same format as the cards argument.
                         Mutually exclusive with cards.

        Returns:
            dict: port_label -> (conn_id, abs_cx, abs_cy)
        """
        if controllers is not None:
            if dev_label_h is None:
                dev_label_h = self._estimate_3level_label_h(
                    label, controllers, port_w, port_spacing, card_pad_x,
                    card_gap, ctrl_pad_x, ctrl_gap, dev_pad_x)
            return self._device_3level(
                cid, label, x, y, style, controllers, cable_side,
                port_w, port_h, port_spacing, sfp_w, sfp_h, sfp_gap,
                card_pad_x, card_gap, sfp_side_pad, label_side_pad,
                dev_pad_x, dev_label_h, dev_inner_pad, dev_pad_bottom,
                ctrl_pad_x, ctrl_label_h, ctrl_pad_top, ctrl_pad_bottom,
                ctrl_gap, parent_id)

        card_h = sfp_side_pad + sfp_h + sfp_gap + port_h + label_side_pad

        card_widths = [
            card_pad_x * 2 + len(pd) * port_w + max(0, len(pd) - 1) * port_spacing
            for _, pd in cards
        ]

        if dev_label_h is None:
            dev_w = dev_pad_x * 2 + sum(card_widths) + max(0, len(cards) - 1) * card_gap
            dev_label_h = _label_h(label, dev_w)

        dev_w = dev_pad_x * 2 + sum(card_widths) + max(0, len(cards) - 1) * card_gap
        dev_h = dev_inner_pad + card_h + dev_label_h + dev_pad_bottom

        self._device_boxes.append((x, y, dev_w, dev_h))

        if cable_side == "top":
            dev_valign      = "bottom"
            card_y_in_dev   = dev_inner_pad
        else:
            dev_valign      = "top"
            card_y_in_dev   = dev_label_h + dev_inner_pad

        self.container(cid, label, x, y, dev_w, dev_h, style,
                       valign=dev_valign, parent_id=parent_id,
                       spacing_top=4, spacing_bottom=4)

        result = {}
        card_x_in_dev = dev_pad_x
        abs_card_row_y = y + card_y_in_dev

        for (card_label, port_defs), cw in zip(cards, card_widths):
            card_cid = nid("card")
            abs_card_x = x + card_x_in_dev

            if cable_side == "top":
                sfp_rel_y  = sfp_side_pad
                port_rel_y = sfp_side_pad + sfp_h + sfp_gap
                card_valign        = "bottom"
                card_spacing_top   = 0
                card_spacing_bot   = 4
            else:
                port_rel_y = label_side_pad
                sfp_rel_y  = label_side_pad + port_h + sfp_gap
                card_valign        = "top"
                card_spacing_top   = 4
                card_spacing_bot   = 0

            self.container(card_cid, card_label,
                           card_x_in_dev, card_y_in_dev, cw, card_h,
                           CARD_STYLE, valign=card_valign, parent_id=cid,
                           font_size=9, bold=False,
                           spacing_top=card_spacing_top,
                           spacing_bottom=card_spacing_bot)

            for i, (plabel, pid, has_sfp, pstyle) in enumerate(port_defs):
                port_rel_x = card_pad_x + i * (port_w + port_spacing)
                self.port(pid, "", port_rel_x, port_rel_y, card_cid,
                          pstyle, w=port_w, h=port_h)
                port_abs_cx = abs_card_x + port_rel_x + port_w / 2
                port_abs_cy = abs_card_row_y + port_rel_y + port_h / 2

                if has_sfp:
                    sfp_id    = nid("sfp")
                    sfp_rel_x = port_rel_x + (port_w - sfp_w) / 2
                    self.port(sfp_id, "", sfp_rel_x, sfp_rel_y, card_cid,
                              SFP_STYLE, w=sfp_w, h=sfp_h)
                    sfp_abs_cx = abs_card_x + sfp_rel_x + sfp_w / 2
                    sfp_abs_cy = abs_card_row_y + sfp_rel_y + sfp_h / 2
                    result[plabel] = (sfp_id, sfp_abs_cx, sfp_abs_cy)
                else:
                    result[plabel] = (pid, port_abs_cx, port_abs_cy)

            card_x_in_dev += cw + card_gap

        return result

    def _estimate_3level_label_h(self, label, controllers,
                                 port_w, port_spacing, card_pad_x,
                                 card_gap, ctrl_pad_x, ctrl_gap, dev_pad_x):
        """Compute dev_label_h for 3-level device considering text wrap."""
        ctrl_widths = []
        for _, cards in controllers:
            card_widths = [
                card_pad_x * 2 + len(pd) * port_w + max(0, len(pd) - 1) * port_spacing
                for _, pd in cards
            ]
            cw = ctrl_pad_x * 2 + sum(card_widths) + max(0, len(cards) - 1) * card_gap
            ctrl_widths.append(cw)
        dev_w = dev_pad_x * 2 + sum(ctrl_widths) + max(0, len(controllers) - 1) * ctrl_gap
        return _label_h(label, dev_w)

    def _device_3level(self, cid, label, x, y, style, controllers, cable_side,
                       port_w, port_h, port_spacing, sfp_w, sfp_h, sfp_gap,
                       card_pad_x, card_gap, sfp_side_pad, label_side_pad,
                       dev_pad_x, dev_label_h, dev_inner_pad, dev_pad_bottom,
                       ctrl_pad_x, ctrl_label_h, ctrl_pad_top, ctrl_pad_bottom,
                       ctrl_gap, parent_id):
        """Build a 3-level device: chassis → controller → card → port."""
        card_h = sfp_side_pad + sfp_h + sfp_gap + port_h + label_side_pad
        ctrl_h = ctrl_pad_top + card_h + ctrl_label_h + ctrl_pad_bottom

        # Compute width of each controller
        ctrl_widths = []
        for ctrl_label, cards in controllers:
            card_widths = [
                card_pad_x * 2 + len(pd) * port_w + max(0, len(pd) - 1) * port_spacing
                for _, pd in cards
            ]
            cw = ctrl_pad_x * 2 + sum(card_widths) + max(0, len(cards) - 1) * card_gap
            ctrl_widths.append(cw)

        dev_w = dev_pad_x * 2 + sum(ctrl_widths) + max(0, len(controllers) - 1) * ctrl_gap
        dev_h = dev_inner_pad + ctrl_h + dev_label_h + dev_pad_bottom

        self._device_boxes.append((x, y, dev_w, dev_h))

        if cable_side == "top":
            dev_valign = "bottom"
            ctrl_y_in_dev = dev_inner_pad
        else:
            dev_valign = "top"
            ctrl_y_in_dev = dev_label_h + dev_inner_pad

        self.container(cid, label, x, y, dev_w, dev_h, style,
                       valign=dev_valign, parent_id=parent_id,
                       spacing_top=4, spacing_bottom=4)

        result = {}
        ctrl_x_in_dev = dev_pad_x

        for (ctrl_label, cards), c_w in zip(controllers, ctrl_widths):
            ctrl_cid = nid("ctrl")
            abs_ctrl_x = x + ctrl_x_in_dev
            abs_ctrl_y = y + ctrl_y_in_dev

            if cable_side == "top":
                ctrl_valign = "bottom"
                ctrl_spacing_top = 2
                ctrl_spacing_bot = 4
            else:
                ctrl_valign = "top"
                ctrl_spacing_top = 4
                ctrl_spacing_bot = 2

            self.container(ctrl_cid, ctrl_label,
                           ctrl_x_in_dev, ctrl_y_in_dev, c_w, ctrl_h,
                           CTRL_STYLE, valign=ctrl_valign, parent_id=cid,
                           font_size=10, bold=True,
                           spacing_top=ctrl_spacing_top,
                           spacing_bottom=ctrl_spacing_bot)

            # Cards inside controller
            card_x_in_ctrl = ctrl_pad_x
            if cable_side == "top":
                card_y_in_ctrl = ctrl_pad_top
            else:
                card_y_in_ctrl = ctrl_label_h + ctrl_pad_top

            for card_label, port_defs in cards:
                card_cid = nid("card")
                n_ports = len(port_defs)
                card_w = card_pad_x * 2 + n_ports * port_w + max(0, n_ports - 1) * port_spacing

                abs_card_x = abs_ctrl_x + card_x_in_ctrl
                abs_card_y = abs_ctrl_y + card_y_in_ctrl

                if cable_side == "top":
                    sfp_rel_y = sfp_side_pad
                    port_rel_y = sfp_side_pad + sfp_h + sfp_gap
                    card_valign = "bottom"
                    card_spacing_top = 0
                    card_spacing_bot = 4
                else:
                    port_rel_y = label_side_pad
                    sfp_rel_y = label_side_pad + port_h + sfp_gap
                    card_valign = "top"
                    card_spacing_top = 4
                    card_spacing_bot = 0

                self.container(card_cid, card_label,
                               card_x_in_ctrl, card_y_in_ctrl, card_w, card_h,
                               CARD_STYLE, valign=card_valign, parent_id=ctrl_cid,
                               font_size=9, bold=False,
                               spacing_top=card_spacing_top,
                               spacing_bottom=card_spacing_bot)

                for i, (plabel, pid, has_sfp, pstyle) in enumerate(port_defs):
                    port_rel_x = card_pad_x + i * (port_w + port_spacing)
                    self.port(pid, "", port_rel_x, port_rel_y, card_cid,
                              pstyle, w=port_w, h=port_h)
                    port_abs_cx = abs_card_x + port_rel_x + port_w / 2
                    port_abs_cy = abs_card_y + port_rel_y + port_h / 2

                    if has_sfp:
                        sfp_id = nid("sfp")
                        sfp_rel_x = port_rel_x + (port_w - sfp_w) / 2
                        self.port(sfp_id, "", sfp_rel_x, sfp_rel_y, card_cid,
                                  SFP_STYLE, w=sfp_w, h=sfp_h)
                        sfp_abs_cx = abs_card_x + sfp_rel_x + sfp_w / 2
                        sfp_abs_cy = abs_card_y + sfp_rel_y + sfp_h / 2
                        result[plabel] = (sfp_id, sfp_abs_cx, sfp_abs_cy)
                    else:
                        result[plabel] = (pid, port_abs_cx, port_abs_cy)

                card_x_in_ctrl += card_w + card_gap

            ctrl_x_in_dev += c_w + ctrl_gap

        return result

    def port(self, pid, label, x, y, parent_id, pstyle, w=32, h=28):
        """Add a port cell."""
        c = ET.SubElement(self.R, "mxCell", id=pid, value=label,
            style=(f"rounded=1;whiteSpace=wrap;html=1;fontSize=7;"
                   f"verticalAlign=middle;spacing=1;{pstyle}"),
            vertex="1", connectable="1", parent=parent_id)
        g = ET.SubElement(c, "mxGeometry", x=str(x), y=str(y),
                          width=str(w), height=str(h))
        g.set("as", "geometry")

    def text(self, label, x, y, w, h, extra=""):
        """Add a text cell (always parented to root layer "1")."""
        t = ET.SubElement(self.R, "mxCell", id=nid("t"), value=label,
            style=f"text;html=1;align=center;verticalAlign=middle;whiteSpace=wrap;{extra}",
            vertex="1", parent="1")
        g = ET.SubElement(t, "mxGeometry", x=str(x), y=str(y),
                          width=str(w), height=str(h))
        g.set("as", "geometry")

    def add_edge(self, src_cx, src_cy, tgt_cx, tgt_cy,
                 src_id, tgt_id, style, label="", zone=None, layer=None):
        """Queue a waypoint edge for batch emission by flush_edges() / save().

        Args:
            zone:  Optional (y_min, y_max) tuple for multi-channel routing.
                   When omitted, edges use the diagram's default routing zone.
            layer: Optional layer name. Edges are placed in this draw.io layer
                   for visibility toggling. None → default layer.
        """
        edge = (src_cx, src_cy, tgt_cx, tgt_cy, src_id, tgt_id, style, label)
        key = (zone, layer)
        self._edge_zones.setdefault(key, []).append(edge)

    def simple_edge(self, src_id, tgt_id, label, style_extra, layer=None):
        """Add a direct edge without waypoints (e.g. stack links).

        If the style contains ``double=1;`` a double-line effect is rendered
        by drawing a thick outer edge overlaid with a thinner white inner
        edge.
        """
        import re as _re
        parent_id = self._get_layer_id(layer)

        double = "double=1" in style_extra
        if double:
            style_extra = style_extra.replace("double=1;", "").replace("double=1", "")
            # Parse outer width; inner = outer - 2
            wm = _re.search(r"strokeWidth=([0-9.]+)", style_extra)
            outer_w = float(wm.group(1)) if wm else 4
            inner_w = max(1, outer_w - 2)
            inner_style = _re.sub(
                r"strokeColor=#[0-9a-fA-F]+", "strokeColor=#FFFFFF",
                style_extra)
            inner_style = _re.sub(
                r"strokeWidth=[0-9.]+", f"strokeWidth={inner_w}",
                inner_style)

            base = ("rounded=1;orthogonalLoop=1;jettySize=auto;html=1;"
                    "fontSize=7;endArrow=none;startArrow=none;")
            # Outer (coloured thick)
            e1 = ET.SubElement(self.R, "mxCell", id=nid("e"), value="",
                style=f"{base}{style_extra}",
                edge="1", source=src_id, target=tgt_id, parent=parent_id)
            g1 = ET.SubElement(e1, "mxGeometry", relative="1")
            g1.set("as", "geometry")
            # Inner (white thin)
            e2 = ET.SubElement(self.R, "mxCell", id=nid("e"), value=label,
                style=f"{base}{inner_style}",
                edge="1", source=src_id, target=tgt_id, parent=parent_id)
            g2 = ET.SubElement(e2, "mxGeometry", relative="1")
            g2.set("as", "geometry")
            if label:
                offset = ET.SubElement(g2, "mxPoint", y="-10")
                offset.set("as", "offset")
            return

        e = ET.SubElement(self.R, "mxCell", id=nid("e"), value=label,
            style=(f"rounded=1;orthogonalLoop=1;jettySize=auto;html=1;"
                   f"fontSize=7;endArrow=none;startArrow=none;{style_extra}"),
            edge="1", source=src_id, target=tgt_id, parent=parent_id)
        g = ET.SubElement(e, "mxGeometry", relative="1")
        g.set("as", "geometry")
        if label:
            offset = ET.SubElement(g, "mxPoint", y="-10")
            offset.set("as", "offset")

    def flush_edges(self):
        """Route all queued edges through assigned lanes and emit XML."""
        # Group edges by zone for routing, then emit with per-layer parent_id
        zone_groups = {}  # zone -> [(edge, layer_name), ...]
        for (zone, layer_name), edges in self._edge_zones.items():
            for edge in edges:
                zone_groups.setdefault(zone, []).append((edge, layer_name))

        # For ObstacleRouter: two-phase approach to spread verticals
        # across ALL zones before emitting.
        if isinstance(self.router, ObstacleRouter):
            all_edge_data = []
            for zone, edge_layer_pairs in zone_groups.items():
                if not edge_layer_pairs:
                    continue
                edges = [pair[0] for pair in edge_layer_pairs]
                layer_names = [pair[1] for pair in edge_layer_pairs]
                if zone is not None:
                    y_min, y_max = zone
                else:
                    y_min, y_max = self.route_y_min, self.route_y_max
                parent_ids = [self._get_layer_id(ln) for ln in layer_names]
                edge_data = self.router.build_edge_data(
                    edges, y_min, y_max,
                    obstacles=self._device_boxes,
                    parent_ids=parent_ids)
                all_edge_data.extend(edge_data)

            _spread_vertical_segments(
                all_edge_data, self.router.VERTICAL_PITCH,
                x_tolerance=self.router.VERTICAL_TOLERANCE)
            _straighten_port_entry(all_edge_data)
            self.router.emit_edge_data(all_edge_data, self.R)
        else:
            for zone, edge_layer_pairs in zone_groups.items():
                if not edge_layer_pairs:
                    continue
                edges = [pair[0] for pair in edge_layer_pairs]
                layer_names = [pair[1] for pair in edge_layer_pairs]
                if zone is not None:
                    y_min, y_max = zone
                else:
                    y_min, y_max = self.route_y_min, self.route_y_max
                parent_ids = [self._get_layer_id(ln) for ln in layer_names]
                self.router.route(edges, self.R, y_min, y_max,
                                  obstacles=self._device_boxes,
                                  parent_ids=parent_ids)
        self._edge_zones.clear()

    def legend(self, entries, x=None, y=None, title="Legend"):
        """Add a legend box showing cable color/style meanings.

        Args:
            entries: list of (label, edge_style_str) tuples.
            x: Left X of legend box. None = auto (right side).
            y: Top Y of legend box. None = auto (top).
            title: Legend title text.
        """
        row_h = 18
        line_w = 44
        label_w = 120
        pad = 8
        box_w = pad + line_w + 6 + label_w + pad
        box_h = 22 + len(entries) * row_h + pad

        if x is None:
            # Place to the right of all devices, with gap
            if self._device_boxes:
                max_right = max(bx + bw for bx, _, bw, _ in self._device_boxes)
                x = max_right + 30
            else:
                model = self.mxfile.find(".//mxGraphModel")
                pw = int(model.get("pageWidth", "1600"))
                x = pw - box_w - 20
            # Expand page if legend extends past right edge
            model = self.mxfile.find(".//mxGraphModel")
            needed_w = int(x + box_w + 20)
            cur_pw = int(model.get("pageWidth", "1600"))
            if needed_w > cur_pw:
                model.set("pageWidth", str(needed_w))
                model.set("dx", str(needed_w))
        if y is None:
            y = 20

        # Outer container
        lid = nid("leg")
        self.container(lid, title, x, y, box_w, box_h,
                       "fillColor=#ffffff;strokeColor=#cccccc;shadow=1;",
                       valign="top", font_size=10, bold=True, spacing_top=2)

        for i, (label, style_str) in enumerate(entries):
            ry = 22 + i * row_h

            # Line sample
            line_id = nid("ll")
            lx1 = pad
            ly = ry + row_h // 2
            e = ET.SubElement(self.R, "mxCell", id=line_id, value="",
                style=(f"endArrow=none;startArrow=none;html=1;"
                       f"fontSize=1;{style_str}"),
                edge="1", parent=lid)
            g = ET.SubElement(e, "mxGeometry", relative="1")
            g.set("as", "geometry")
            src = ET.SubElement(g, "mxPoint", x=str(lx1), y=str(ly))
            src.set("as", "sourcePoint")
            tgt = ET.SubElement(g, "mxPoint", x=str(lx1 + line_w), y=str(ly))
            tgt.set("as", "targetPoint")

            # Label
            txt_id = nid("lt")
            t = ET.SubElement(self.R, "mxCell", id=txt_id, value=label,
                style=(f"text;html=1;align=left;verticalAlign=middle;"
                       f"whiteSpace=wrap;fontSize=9;fontColor=#333333;"),
                vertex="1", parent=lid)
            tg = ET.SubElement(t, "mxGeometry",
                               x=str(pad + line_w + 6), y=str(ry),
                               width=str(label_w), height=str(row_h))
            tg.set("as", "geometry")

    def save(self, path):
        """Write XML to path. Calls flush_edges() automatically."""
        self.flush_edges()
        tree = ET.ElementTree(self.mxfile)
        ET.indent(tree, space="  ")
        tree.write(path, encoding="unicode", xml_declaration=True)
