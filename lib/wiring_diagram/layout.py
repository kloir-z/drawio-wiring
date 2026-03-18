"""Layout algorithms for automatic device placement.

Implements a Sugiyama-inspired layered layout:
1. Layer assignment (user-specified or longest-path)
2. X-coordinate placement with barycenter ordering
3. Routing zone computation between adjacent layers
"""


def _estimate_card_width(card, port_w, card_pad_x=6, port_spacing=4):
    """Estimate the pixel width of a single card."""
    n = len(card.ports)
    return card_pad_x * 2 + n * port_w + max(0, n - 1) * port_spacing


def _estimate_device_width(node, port_w, port_h):
    """Estimate the pixel width of a device based on its ports/cards."""
    if node.is_3level:
        card_pad_x = 6
        port_spacing = 4
        card_gap = 8
        ctrl_pad_x = 8
        ctrl_gap = 12
        dev_pad_x = 8
        total = dev_pad_x * 2
        for ctrl in node.controllers:
            ctrl_w = ctrl_pad_x * 2
            for card in ctrl.cards:
                ctrl_w += _estimate_card_width(card, port_w, card_pad_x, port_spacing)
            ctrl_w += max(0, len(ctrl.cards) - 1) * card_gap
            total += ctrl_w
        total += max(0, len(node.controllers) - 1) * ctrl_gap
        return total
    elif node.is_carded:
        card_pad_x = 6
        port_spacing = 4
        card_gap = 8
        dev_pad_x = 8
        total = dev_pad_x * 2
        for card in node.cards:
            total += _estimate_card_width(card, port_w, card_pad_x, port_spacing)
        total += max(0, len(node.cards) - 1) * card_gap
        return total
    else:
        pad_x = 8
        port_spacing = 3
        n = len(node.ports)
        return pad_x * 2 + n * port_w + max(0, n - 1) * port_spacing


def _dev_label_height(label, container_w):
    """Compute device label height accounting for text wrapping."""
    import math
    char_w = 11 * 0.65
    avail_w = max(1, container_w - 16)
    n_lines = 0
    for line in label.split('\n'):
        line_w = len(line) * char_w
        n_lines += max(1, math.ceil(line_w / avail_w))
    return n_lines * 14 + 6


def _estimate_device_height(node, port_w, port_h):
    """Estimate the pixel height of a device."""
    dev_w = _estimate_device_width(node, port_w, port_h)

    sfp_side_pad = 4
    sfp_h = 6
    sfp_gap = 1
    label_side_pad = 18
    card_h = sfp_side_pad + sfp_h + sfp_gap + port_h + label_side_pad

    if node.is_3level:
        ctrl_label_h = 18
        ctrl_pad_top = 4
        ctrl_pad_bottom = 6
        dev_label_h = _dev_label_height(node.label, dev_w)
        dev_inner_pad = 4
        dev_pad_bottom = 6
        ctrl_h = ctrl_pad_top + card_h + ctrl_label_h + ctrl_pad_bottom
        return dev_inner_pad + ctrl_h + dev_label_h + dev_pad_bottom
    elif node.is_carded:
        dev_label_h = _dev_label_height(node.label, dev_w)
        dev_inner_pad = 4
        dev_pad_bottom = 6
        return dev_inner_pad + card_h + dev_label_h + dev_pad_bottom
    else:
        pad_top = 34
        pad_x = 8
        return pad_top + port_h + pad_x


def _assign_layers(topology):
    """Assign layer indices to devices.

    Uses user-specified layers where available, then longest-path for
    unassigned devices.

    Returns:
        dict: device_id -> layer_index (0 = topmost)
    """
    layers = {}
    unassigned = []

    for dev_id, node in topology.devices.items():
        if node.layer is not None:
            layers[dev_id] = node.layer
        else:
            unassigned.append(dev_id)

    if not unassigned:
        return layers

    # Build adjacency for longest-path assignment
    # Cables go from "upper" to "lower" — use assigned layers as anchors
    adj = {dev_id: [] for dev_id in topology.devices}
    for cable in topology.cables:
        adj[cable.src_device].append(cable.dst_device)
        adj[cable.dst_device].append(cable.src_device)

    # BFS from assigned nodes to propagate layers
    from collections import deque
    queue = deque()
    for dev_id, layer in layers.items():
        queue.append(dev_id)

    while queue:
        dev_id = queue.popleft()
        for neighbor in adj[dev_id]:
            if neighbor not in layers:
                # Place neighbor one layer below
                layers[neighbor] = layers[dev_id] + 1
                queue.append(neighbor)

    # Any still unassigned (disconnected) go to layer 0
    for dev_id in unassigned:
        if dev_id not in layers:
            layers[dev_id] = 0

    return layers


def _order_within_layers(topology, layer_groups, layers):
    """Reorder devices within each layer using barycenter heuristic.

    Args:
        topology:     The Topology object.
        layer_groups: dict: layer_index -> [device_id, ...]
        layers:       dict: device_id -> layer_index

    Returns:
        dict: layer_index -> [device_id, ...] (reordered)
    """
    # Build neighbor map
    neighbors = {dev_id: [] for dev_id in topology.devices}
    for cable in topology.cables:
        neighbors[cable.src_device].append(cable.dst_device)
        neighbors[cable.dst_device].append(cable.src_device)

    sorted_layers = sorted(layer_groups.keys())

    # Initial ordering: preserve insertion order
    ordered = {layer: list(devs) for layer, devs in layer_groups.items()}

    # Barycenter iterations (top-down then bottom-up, 2 passes)
    for _ in range(2):
        # Top-down
        for layer in sorted_layers[1:]:
            devs = ordered[layer]
            if not devs:
                continue
            # Previous layer positions
            prev_layer = layer - 1
            if prev_layer not in ordered:
                continue
            prev_pos = {d: i for i, d in enumerate(ordered[prev_layer])}

            def barycenter(dev_id):
                nbrs = [n for n in neighbors[dev_id] if n in prev_pos]
                if not nbrs:
                    return float('inf')
                return sum(prev_pos[n] for n in nbrs) / len(nbrs)

            ordered[layer] = sorted(devs, key=barycenter)

        # Bottom-up
        for layer in reversed(sorted_layers[:-1]):
            devs = ordered[layer]
            if not devs:
                continue
            next_layer = layer + 1
            if next_layer not in ordered:
                continue
            next_pos = {d: i for i, d in enumerate(ordered[next_layer])}

            def barycenter_rev(dev_id):
                nbrs = [n for n in neighbors[dev_id] if n in next_pos]
                if not nbrs:
                    return float('inf')
                return sum(next_pos[n] for n in nbrs) / len(nbrs)

            ordered[layer] = sorted(devs, key=barycenter_rev)

    return ordered


def _estimate_port_x(node, port_label, device_x, port_w):
    """Estimate the absolute X center of a port within a device.

    Args:
        node:        DeviceNode.
        port_label:  The port label to locate.
        device_x:    The device's left X coordinate.
        port_w:      Port width.

    Returns:
        float: Estimated absolute X center of the port.
    """
    if node.is_3level:
        card_pad_x = 6
        port_spacing = 4
        card_gap = 8
        ctrl_pad_x = 8
        ctrl_gap = 12
        dev_pad_x = 8
        cur_x = device_x + dev_pad_x
        for ctrl in node.controllers:
            cur_x += ctrl_pad_x
            for card in ctrl.cards:
                cur_x += card_pad_x
                for i, p in enumerate(card.ports):
                    px = cur_x + i * (port_w + port_spacing) + port_w / 2
                    if p.label == port_label:
                        return px
                cur_x += len(card.ports) * port_w + max(0, len(card.ports) - 1) * port_spacing
                cur_x += card_pad_x + card_gap
            cur_x -= card_gap  # remove trailing card_gap
            cur_x += ctrl_pad_x + ctrl_gap
    elif node.is_carded:
        card_pad_x = 6
        port_spacing = 4
        card_gap = 8
        dev_pad_x = 8
        cur_x = device_x + dev_pad_x
        for card in node.cards:
            cur_x += card_pad_x
            for i, p in enumerate(card.ports):
                px = cur_x + i * (port_w + port_spacing) + port_w / 2
                if p.label == port_label:
                    return px
            cur_x += len(card.ports) * port_w + max(0, len(card.ports) - 1) * port_spacing
            cur_x += card_pad_x + card_gap
    else:
        pad_x = 8
        port_spacing = 3
        cur_x = device_x + pad_x
        for i, p in enumerate(node.ports):
            px = cur_x + i * (port_w + port_spacing) + port_w / 2
            if p.label == port_label:
                return px
    # Fallback: center of device
    w = _estimate_device_width(node, port_w, 12)
    return device_x + w / 2


def _compute_gap_expansions(topology, ordered, sizes, layers, cables,
                            device_gap, port_w, cable_pitch=6):
    """Compute per-gap expansion based on transit cable count.

    For each gap between adjacent devices in a layer, count how many cables
    from non-adjacent layers have a vertical leg passing through that gap,
    then expand accordingly.

    Args:
        topology:    Topology object.
        ordered:     dict: layer -> [device_id, ...] (ordered).
        sizes:       dict: device_id -> (w, h).
        layers:      dict: device_id -> layer_index.
        cables:      list of Cable objects.
        device_gap:  Base gap between devices.
        port_w:      Port width for X estimation.
        cable_pitch: Extra pixels per transit cable.

    Returns:
        dict: (layer, gap_index) -> expanded_gap_width
    """
    # First pass: compute initial device X positions (uniform gap) to estimate
    # port X coordinates.
    sorted_layers = sorted(ordered.keys())

    # Compute max_width for centering
    layer_widths = {}
    for layer, devs in ordered.items():
        total_w = sum(sizes[d][0] for d in devs) + max(0, len(devs) - 1) * device_gap
        layer_widths[layer] = total_w
    max_width = max(layer_widths.values()) if layer_widths else 800
    page_w_margin = 60

    # Preliminary X positions
    prelim_x = {}
    for layer in sorted_layers:
        devs = ordered[layer]
        total_w = layer_widths[layer]
        start_x = (max_width - total_w) / 2 + page_w_margin / 2
        cur_x = start_x
        for dev_id in devs:
            prelim_x[dev_id] = cur_x
            cur_x += sizes[dev_id][0] + device_gap

    # Build gap intervals per layer: list of (left_dev_right_x, right_dev_left_x)
    # and corresponding gap keys
    gap_info = {}  # layer -> [(gap_left_x, gap_right_x, gap_index), ...]
    for layer in sorted_layers:
        devs = ordered[layer]
        gaps = []
        for gi in range(len(devs) - 1):
            left_dev = devs[gi]
            right_dev = devs[gi + 1]
            left_x_end = prelim_x[left_dev] + sizes[left_dev][0]
            right_x_start = prelim_x[right_dev]
            gaps.append((left_x_end, right_x_start, gi))
        gap_info[layer] = gaps

    # Count transits per gap
    transit_counts = {}  # (layer, gap_index) -> count
    for layer in sorted_layers:
        for _, _, gi in gap_info[layer]:
            transit_counts[(layer, gi)] = 0

    for cable in cables:
        src_layer = layers.get(cable.src_device)
        dst_layer = layers.get(cable.dst_device)
        if src_layer is None or dst_layer is None:
            continue
        if abs(src_layer - dst_layer) <= 1:
            continue  # adjacent layers: no intermediate transit

        lo_layer = min(src_layer, dst_layer)
        hi_layer = max(src_layer, dst_layer)

        # Estimate target port X (the vertical leg descends/ascends to this X)
        dst_node = topology.devices[cable.dst_device]
        dst_x = prelim_x.get(cable.dst_device, 0)
        tgt_x = _estimate_port_x(dst_node, cable.dst_port, dst_x, port_w)

        src_node = topology.devices[cable.src_device]
        src_x = prelim_x.get(cable.src_device, 0)
        src_px = _estimate_port_x(src_node, cable.src_port, src_x, port_w)

        # Check intermediate layers
        for m in range(lo_layer + 1, hi_layer):
            if m not in gap_info:
                continue
            gaps = gap_info[m]
            devs = ordered[m]

            # For each vertical leg (src and dst), check which gaps it transits
            for leg_x in (src_px, tgt_x):
                # Find if leg_x falls inside any device in this layer
                hit_dev = None
                for dev_id in devs:
                    dx = prelim_x[dev_id]
                    dw = sizes[dev_id][0]
                    if dx <= leg_x <= dx + dw:
                        hit_dev = dev_id
                        break

                if hit_dev is not None:
                    # Leg overlaps a device; attribute to the nearest gap
                    dev_idx = devs.index(hit_dev)
                    dx = prelim_x[hit_dev]
                    dw = sizes[hit_dev][0]
                    mid = dx + dw / 2
                    if leg_x <= mid and dev_idx > 0:
                        transit_counts[(m, dev_idx - 1)] = \
                            transit_counts.get((m, dev_idx - 1), 0) + 1
                    elif dev_idx < len(devs) - 1:
                        transit_counts[(m, dev_idx)] = \
                            transit_counts.get((m, dev_idx), 0) + 1
                    elif dev_idx > 0:
                        transit_counts[(m, dev_idx - 1)] = \
                            transit_counts.get((m, dev_idx - 1), 0) + 1

                elif gaps:
                    # Leg falls in a gap — find which one
                    for gap_left, gap_right, gi in gaps:
                        if gap_left <= leg_x <= gap_right:
                            transit_counts[(m, gi)] = \
                                transit_counts.get((m, gi), 0) + 1
                            break

    # Compute expanded gap widths
    expanded_gaps = {}
    for key, count in transit_counts.items():
        expanded_gaps[key] = max(device_gap, device_gap + count * cable_pitch)

    return expanded_gaps


def compute_layout(topology, *, layer_gap=200, device_gap=30,
                   first_layer_y=30, port_w=14, port_h=12,
                   cables=None, cable_pitch=6):
    """Compute device positions and routing zones.

    Args:
        topology:      Topology object with devices and cables.
        layer_gap:     Vertical distance between layer centers.
        device_gap:    Horizontal gap between devices.
        first_layer_y: Y offset of the topmost layer.
        port_w:        Default port width for size estimation.
        port_h:        Default port height for size estimation.
        cables:        List of Cable objects for transit-aware gap expansion.
                       If None, uses topology.cables.
        cable_pitch:   Extra pixels per transit cable (default 6).

    Returns:
        dict with keys:
            'devices':  {device_id: {'x': int, 'y': int, 'w': int, 'h': int}}
            'zones':    {(layer_a, layer_b): (y_min, y_max)}
            'page_w':   Computed page width.
            'page_h':   Computed page height.
            'default_route_y_min': Default routing zone top.
            'default_route_y_max': Default routing zone bottom.
    """
    if cables is None:
        cables = topology.cables

    # Step 1: Layer assignment
    layers = _assign_layers(topology)

    # Update node layer attributes
    for dev_id, layer in layers.items():
        topology.devices[dev_id].layer = layer

    # Group by layer
    layer_groups = {}
    for dev_id, layer in layers.items():
        layer_groups.setdefault(layer, []).append(dev_id)

    # Step 2: Ordering within layers (barycenter)
    ordered = _order_within_layers(topology, layer_groups, layers)

    # Step 3: Compute device sizes
    sizes = {}
    for dev_id, node in topology.devices.items():
        w = _estimate_device_width(node, port_w, port_h)
        h = _estimate_device_height(node, port_w, port_h)
        sizes[dev_id] = (w, h)

    # Step 4: Compute gap expansions based on cable transit counts
    expanded_gaps = _compute_gap_expansions(
        topology, ordered, sizes, layers, cables,
        device_gap, port_w, cable_pitch,
    )

    # Step 5: Assign X coordinates with per-gap widths
    sorted_layers = sorted(ordered.keys())

    # Compute layer widths with expanded gaps
    layer_widths = {}
    for layer in sorted_layers:
        devs = ordered[layer]
        total_w = sum(sizes[d][0] for d in devs)
        for gi in range(len(devs) - 1):
            gap = expanded_gaps.get((layer, gi), device_gap)
            total_w += gap
        layer_widths[layer] = total_w

    max_width = max(layer_widths.values()) if layer_widths else 800
    page_w_margin = 60

    device_placements = {}

    for layer in sorted_layers:
        devs = ordered[layer]
        total_w = layer_widths[layer]
        # Center-align this layer
        start_x = (max_width - total_w) / 2 + page_w_margin / 2
        cur_x = start_x
        y = first_layer_y + layer * layer_gap

        for i, dev_id in enumerate(devs):
            w, h = sizes[dev_id]
            device_placements[dev_id] = {
                'x': int(cur_x), 'y': int(y), 'w': w, 'h': h,
            }
            if i < len(devs) - 1:
                gap = expanded_gaps.get((layer, i), device_gap)
                cur_x += w + gap
            else:
                cur_x += w

    # Step 5: Compute routing zones between adjacent layers
    zones = {}
    for i in range(len(sorted_layers) - 1):
        layer_a = sorted_layers[i]
        layer_b = sorted_layers[i + 1]

        # Find bottom of layer_a and top of layer_b
        max_bottom_a = 0
        for dev_id in ordered[layer_a]:
            p = device_placements[dev_id]
            bottom = p['y'] + p['h']
            max_bottom_a = max(max_bottom_a, bottom)

        min_top_b = float('inf')
        for dev_id in ordered[layer_b]:
            p = device_placements[dev_id]
            min_top_b = min(min_top_b, p['y'])

        # Routing zone fills the gap with some margin
        margin = 10
        zone_y_min = max_bottom_a + margin
        zone_y_max = min_top_b - margin

        if zone_y_max > zone_y_min:
            zones[(layer_a, layer_b)] = (zone_y_min, zone_y_max)

    # Default routing zone: the largest gap
    default_y_min, default_y_max = 100, 300
    if zones:
        largest = max(zones.values(), key=lambda z: z[1] - z[0])
        default_y_min, default_y_max = largest

    # Page dimensions
    max_bottom = 0
    for p in device_placements.values():
        max_bottom = max(max_bottom, p['y'] + p['h'])

    return {
        'devices': device_placements,
        'zones': zones,
        'page_w': int(max_width + page_w_margin),
        'page_h': int(max_bottom + 60),
        'default_route_y_min': default_y_min,
        'default_route_y_max': default_y_max,
    }
