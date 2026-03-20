"""High-level topology model for automatic diagram layout.

Users build a Topology (devices + cables), then call to_diagram() to get
a Diagram with coordinates automatically computed.

Example::

    from wiring_diagram import Topology, LeftEdgeRouter
    from wiring_diagram import BG_YELLOW, BG_BLUE, PORT_BLUE, EDGE_BLUE

    T = Topology()

    # Switch (flat port row)
    T.add_device("sw1", label="Switch-1", layer=0, style=BG_YELLOW,
                 ports=[("1/0/1", PORT_BLUE), ("1/0/2", PORT_BLUE)])

    # Server (carded structure)
    T.add_device("srv1", label="Server-1", layer=1, style=BG_BLUE,
                 cards=[
                     ("NIC", [("eth0", True, PORT_BLUE),
                              ("eth1", False, PORT_BLUE)]),
                 ])

    T.add_cable("sw1", "1/0/1", "srv1", "eth0", style=EDGE_BLUE)

    D = T.to_diagram()
    D.save("output.drawio")
"""

from dataclasses import dataclass, field


@dataclass
class PortDef:
    """Port definition within a flat device."""
    label: str
    style: str


@dataclass
class CardPortDef:
    """Port definition within a NIC card."""
    label: str
    has_sfp: bool
    style: str


@dataclass
class CardDef:
    """NIC card definition for carded devices."""
    label: str
    ports: list  # list of CardPortDef


@dataclass
class ControllerDef:
    """Controller definition for 3-level devices (chassis → controller → card → port)."""
    label: str
    cards: list  # list of CardDef


@dataclass
class DeviceNode:
    """A device in the topology graph.

    Attributes:
        id:           Unique device identifier (used as mxCell id).
        label:        Display label.
        layer:        Y-layer index (0 = top). None for auto-assignment.
        style:        Background style string (BG_YELLOW, BG_BLUE, etc.).
        ports:        List of PortDef (flat device) — mutually exclusive with cards/controllers.
        cards:        List of CardDef (carded device) — mutually exclusive with ports/controllers.
        controllers:  List of ControllerDef (3-level) — mutually exclusive with ports/cards.
        cable_side:   For carded devices: "top" or "bottom" (default "top").
        device_kwargs: Extra keyword arguments passed to device() or device_carded().
    """
    id: str
    label: str
    layer: int = None
    style: str = ""
    ports: list = field(default_factory=list)        # list of PortDef
    cards: list = field(default_factory=list)         # list of CardDef
    controllers: list = field(default_factory=list)   # list of ControllerDef
    cable_side: str = "top"
    device_kwargs: dict = field(default_factory=dict)

    @property
    def is_carded(self):
        return len(self.cards) > 0 or len(self.controllers) > 0

    @property
    def is_3level(self):
        return len(self.controllers) > 0

    @property
    def port_labels(self):
        """All port labels across ports, cards, or controllers."""
        if self.is_3level:
            return [p.label for ctrl in self.controllers
                    for c in ctrl.cards for p in c.ports]
        if self.cards:
            return [p.label for c in self.cards for p in c.ports]
        return [p.label for p in self.ports]


@dataclass
class Cable:
    """A cable connecting two ports on two devices."""
    src_device: str
    src_port: str
    dst_device: str
    dst_port: str
    style: str
    label: str = ""
    layer: str = None
    style_name: str = None


@dataclass
class SimpleLink:
    """A direct edge without routing (e.g. StackWise)."""
    src_device: str
    dst_device: str
    label: str
    style: str
    layer: str = None


class Topology:
    """High-level graph of devices and cables.

    Build the topology with add_device() and add_cable(), then call
    to_diagram() to get an automatically laid-out Diagram.
    """

    def __init__(self):
        self.devices = {}       # id -> DeviceNode
        self.cables = []        # list of Cable
        self.simple_links = []  # list of SimpleLink

    def add_device(self, device_id, *, label, style, layer=None,
                   ports=None, cards=None, controllers=None,
                   cable_side="top", **kwargs):
        """Add a device to the topology.

        Args:
            device_id:    Unique identifier.
            label:        Display label.
            style:        Background style (BG_YELLOW, etc.).
            layer:        Y-layer index (0 = topmost). None for auto-assign.
            ports:        For flat devices: list of (label, style) tuples.
            cards:        For carded devices: list of
                          (card_label, [(port_label, has_sfp, style), ...]) tuples.
            controllers:  For 3-level devices: list of
                          (ctrl_label, [(card_label, [(port_label, has_sfp, style), ...]), ...])
                          tuples. Mutually exclusive with ports and cards.
            cable_side:   For carded devices: "top" or "bottom".
            **kwargs:     Extra args passed to device()/device_carded().
        """
        given = sum(1 for v in (ports, cards, controllers) if v)
        if given > 1:
            raise ValueError("Specify only one of ports, cards, or controllers")

        port_defs = []
        card_defs = []
        ctrl_defs = []

        if ports:
            for p in ports:
                port_defs.append(PortDef(label=p[0], style=p[1]))

        if cards:
            for card_label, card_ports in cards:
                cp = [CardPortDef(label=cp[0], has_sfp=cp[1], style=cp[2])
                      for cp in card_ports]
                card_defs.append(CardDef(label=card_label, ports=cp))

        if controllers:
            for ctrl_label, ctrl_cards in controllers:
                cd = []
                for card_label, card_ports in ctrl_cards:
                    cp = [CardPortDef(label=cp[0], has_sfp=cp[1], style=cp[2])
                          for cp in card_ports]
                    cd.append(CardDef(label=card_label, ports=cp))
                ctrl_defs.append(ControllerDef(label=ctrl_label, cards=cd))

        node = DeviceNode(
            id=device_id, label=label, layer=layer, style=style,
            ports=port_defs, cards=card_defs, controllers=ctrl_defs,
            cable_side=cable_side, device_kwargs=kwargs,
        )
        self.devices[device_id] = node
        return node

    def add_cable(self, src_device, src_port, dst_device, dst_port,
                  style, label="", layer=None, style_name=None):
        """Add a cable between two device ports."""
        cable = Cable(src_device=src_device, src_port=src_port,
                      dst_device=dst_device, dst_port=dst_port,
                      style=style, label=label, layer=layer,
                      style_name=style_name)
        self.cables.append(cable)
        return cable

    def add_simple_link(self, src_device, dst_device, label, style,
                        layer=None):
        """Add a direct link without routing (e.g. StackWise)."""
        link = SimpleLink(src_device=src_device, dst_device=dst_device,
                          label=label, style=style, layer=layer)
        self.simple_links.append(link)
        return link

    def _auto_layer_name(self, cable):
        """Determine auto-assigned layer name for a cable.

        Uses the label of the device with the larger layer index.
        When layer indices are equal, picks the label that sorts later.
        """
        src_node = self.devices[cable.src_device]
        dst_node = self.devices[cable.dst_device]
        src_layer = src_node.layer if src_node.layer is not None else 0
        dst_layer = dst_node.layer if dst_node.layer is not None else 0

        if src_layer > dst_layer:
            return src_node.label
        elif dst_layer > src_layer:
            return dst_node.label
        else:
            return max(src_node.label, dst_node.label)

    @staticmethod
    def _style_layer_name(cable):
        """Return the style_name as a draw.io layer name."""
        return cable.style_name or "other"

    def to_diagram(self, *, page_w=None, page_h=None, router=None,
                   layer_gap=200, device_gap=30, route_zone_height=None,
                   first_layer_y=30, port_w=14, port_h=12,
                   cable_layers=False, zone_groups=None):
        """Compute layout and return a populated Diagram.

        Args:
            page_w:            Page width (auto-calculated if None).
            page_h:            Page height (auto-calculated if None).
            router:            Routing strategy (default: LeftEdgeRouter).
            layer_gap:         Vertical gap between device layers.
            device_gap:        Horizontal gap between devices in the same layer.
            route_zone_height: Height of routing zones between layers.
                               Default: layer_gap * 0.6.
            first_layer_y:     Y offset for the topmost layer.
            port_w:            Default port width.
            port_h:            Default port height.
            cable_layers:      Auto-assign cables to draw.io layers.
                               True or "device": group by lower-layer device label.
                               "style": group by edge style name.
            zone_groups:       Per-layer-pair cable grouping for sub-zone routing.
                               dict mapping (layer_a, layer_b) to a list of
                               style-name groups, e.g.
                               {(0,1): [["core","core2"], ["acc","acc2"]]}.
                               Cables whose style_name is not in any group are
                               collected into an extra catch-all sub-zone.

        Returns:
            Diagram with all devices, cables, and simple links placed.
        """
        from .layout import compute_layout
        from .diagram import Diagram
        from .routing import LeftEdgeRouter

        if router is None:
            router = LeftEdgeRouter()
        if route_zone_height is None:
            route_zone_height = int(layer_gap * 0.6)

        layout = compute_layout(
            self, layer_gap=layer_gap, device_gap=device_gap,
            first_layer_y=first_layer_y, port_w=port_w, port_h=port_h,
            cables=self.cables, zone_groups=zone_groups,
        )

        # Determine page dimensions
        pw = page_w or layout['page_w']
        ph = page_h or layout['page_h']

        # Default routing zone (for the widest gap between layers)
        default_y_min = layout.get('default_route_y_min', 100)
        default_y_max = layout.get('default_route_y_max', 300)

        D = Diagram(page_w=pw, page_h=ph,
                    route_y_min=default_y_min, route_y_max=default_y_max,
                    router=router)

        # Place devices
        port_map = {}  # (device_id, port_label) -> (cell_id, abs_cx, abs_cy)

        for dev_id, placement in layout['devices'].items():
            node = self.devices[dev_id]
            x, y = placement['x'], placement['y']

            if node.is_3level:
                ctrls_arg = []
                for ctrl in node.controllers:
                    cards_for_ctrl = []
                    for card in ctrl.cards:
                        card_ports = [(p.label, f"{dev_id}_{p.label}",
                                       p.has_sfp, p.style)
                                      for p in card.ports]
                        cards_for_ctrl.append((card.label, card_ports))
                    ctrls_arg.append((ctrl.label, cards_for_ctrl))
                result = D.device_carded(
                    dev_id, node.label, x, y, node.style,
                    controllers=ctrls_arg,
                    cable_side=node.cable_side,
                    port_w=port_w, port_h=port_h,
                    **node.device_kwargs,
                )
            elif node.is_carded:
                cards_arg = []
                for card in node.cards:
                    card_ports = [(p.label, f"{dev_id}_{p.label}",
                                   p.has_sfp, p.style)
                                  for p in card.ports]
                    cards_arg.append((card.label, card_ports))
                result = D.device_carded(
                    dev_id, node.label, x, y, node.style, cards_arg,
                    cable_side=node.cable_side,
                    port_w=port_w, port_h=port_h,
                    **node.device_kwargs,
                )
            else:
                ports_arg = [(p.label, f"{dev_id}_{p.label}", p.style)
                             for p in node.ports]
                kw = dict(port_w=port_w, port_h=port_h)
                kw.update(node.device_kwargs)
                result = D.device(
                    dev_id, node.label, x, y, node.style, ports_arg, **kw,
                )

            for plabel, info in result.items():
                port_map[(dev_id, plabel)] = info

        # Build sub-zone lookup from zone_groups config
        # _sub_zones: {(a,b): {style_name: (y_min, y_max)}}
        #
        # Pre-count cables per style_name per layer pair, weighted by
        # line width so thick-line groups get proportionally more space.
        import re as _re

        def _stroke_width(style_str):
            m = _re.search(r'strokeWidth=([0-9.]+)', style_str)
            return float(m.group(1)) if m else 2

        # {(a,b): {style_name: weighted_count}}
        _style_weights = {}
        for cable in self.cables:
            sn = cable.style_name
            src_l = self.devices[cable.src_device].layer
            dst_l = self.devices[cable.dst_device].layer
            if src_l is None or dst_l is None:
                continue
            a, b = min(src_l, dst_l), max(src_l, dst_l)
            pair = (a, a + 1) if a == b else (a, b)
            w = _stroke_width(cable.style)
            bucket = _style_weights.setdefault(pair, {})
            bucket[sn] = bucket.get(sn, 0) + w

        _sub_zones = {}
        zg = zone_groups or {}
        for layer_pair, groups in zg.items():
            base_zone = layout['zones'].get(tuple(layer_pair))
            if not base_zone:
                continue
            y_min, y_max = base_zone
            pair = tuple(layer_pair)
            sw = _style_weights.get(pair, {})

            # Compute weight per group (cable_count * line_width)
            group_weights = []
            assigned_styles = set()
            for group in groups:
                gw = sum(sw.get(sn, 0) for sn in group)
                group_weights.append(max(1, gw))
                assigned_styles.update(group)
            # Catch-all
            catchall_w = sum(v for sn, v in sw.items()
                             if sn not in assigned_styles)
            group_weights.append(max(1, catchall_w))

            total_w = sum(group_weights)
            mapping = {}
            y_cur = y_min
            for gi, group in enumerate(groups):
                span = (y_max - y_min) * group_weights[gi] / total_w
                sub = (y_cur, y_cur + span)
                for sname in group:
                    mapping[sname] = sub
                y_cur += span
            mapping[None] = (y_cur, y_max)
            _sub_zones[pair] = mapping

        # Add cables
        for cable in self.cables:
            src_key = (cable.src_device, cable.src_port)
            dst_key = (cable.dst_device, cable.dst_port)
            if src_key not in port_map or dst_key not in port_map:
                continue  # skip unresolvable cables
            s_pid, s_cx, s_cy = port_map[src_key]
            d_pid, d_cx, d_cy = port_map[dst_key]

            # Determine routing zone from device layers
            src_layer = self.devices[cable.src_device].layer
            dst_layer = self.devices[cable.dst_device].layer
            zone_key = None
            if src_layer is not None and dst_layer is not None:
                a, b = min(src_layer, dst_layer), max(src_layer, dst_layer)
                if a == b:
                    # Same-layer cable: pick zone below or above based on
                    # port Y positions relative to device centre.
                    mid_y = (s_cy + d_cy) / 2
                    dev_placements = layout['devices']
                    src_p = dev_placements[cable.src_device]
                    dev_mid_y = src_p['y'] + src_p['h'] / 2
                    if mid_y >= dev_mid_y:
                        zone = (layout['zones'].get((a, a + 1))
                                or layout['zones'].get((a - 1, a)))
                        zone_pair = (a, a + 1) if (a, a + 1) in layout['zones'] else (a - 1, a)
                    else:
                        zone = (layout['zones'].get((a - 1, a))
                                or layout['zones'].get((a, a + 1)))
                        zone_pair = (a - 1, a) if (a - 1, a) in layout['zones'] else (a, a + 1)
                else:
                    zone = layout['zones'].get((a, b))
                    zone_pair = (a, b)
                    if zone is None:
                        for la in range(a, b):
                            zone = layout['zones'].get((la, la + 1))
                            if zone:
                                zone_pair = (la, la + 1)
                                break
                if zone:
                    # Apply sub-zone if zone_groups configured for this pair
                    if zone_pair in _sub_zones:
                        mapping = _sub_zones[zone_pair]
                        sname = cable.style_name
                        zone_key = mapping.get(sname, mapping[None])
                    else:
                        zone_key = zone

            # Determine draw.io layer
            layer_name = cable.layer
            if layer_name is None and cable_layers:
                if cable_layers == "style":
                    layer_name = self._style_layer_name(cable)
                else:
                    layer_name = self._auto_layer_name(cable)

            D.add_edge(s_cx, s_cy, d_cx, d_cy, s_pid, d_pid,
                       cable.style, cable.label, zone=zone_key,
                       layer=layer_name)

        # Add simple links
        for link in self.simple_links:
            layer_name = link.layer
            if layer_name is None and cable_layers:
                if cable_layers == "style":
                    layer_name = "stack"
                else:
                    layer_name = self._auto_layer_name(link)
            D.simple_edge(link.src_device, link.dst_device,
                          link.label, link.style, layer=layer_name)

        return D
