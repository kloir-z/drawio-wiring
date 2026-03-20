"""Routing strategies for cable layout in wiring diagrams.

A Router takes a list of queued edges and the XML root element, then emits
mxCell edge elements with waypoints that route cables through a horizontal
lane zone.
"""

import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod

from .ids import nid


class Router(ABC):
    """Base class for edge routing strategies."""

    @abstractmethod
    def route(self, edges, root, route_y_min, route_y_max, obstacles=None,
              parent_ids=None):
        """Emit routed edge cells into *root*.

        Args:
            edges:       List of (src_cx, src_cy, tgt_cx, tgt_cy,
                         src_id, tgt_id, style, label) tuples.
            root:        The <root> ET.Element to append mxCell elements to.
            route_y_min: Top Y of the routing zone.
            route_y_max: Bottom Y of the routing zone.
            obstacles:   Optional list of (x, y, w, h) device bounding boxes.
            parent_ids:  Optional list of parent cell ids (one per edge).
                         When None, all edges use parent="1".
        """


class NaiveRouter(Router):
    """Original routing: sort by midpoint X, assign one lane per edge."""

    def route(self, edges, root, route_y_min, route_y_max, obstacles=None,
              parent_ids=None):
        if not edges:
            return
        n = len(edges)
        pids = parent_ids or ["1"] * n
        route_range = route_y_max - route_y_min
        # Build sort index to preserve parent_id mapping
        indexed = sorted(enumerate(edges), key=lambda ie: (ie[1][0] + ie[1][2]) / 2)
        for rank, (orig_i, edge) in enumerate(indexed):
            src_cx, src_cy, tgt_cx, tgt_cy, src_id, tgt_id, style, label = edge
            lane_y = route_y_min + (rank + 1) * route_range / (n + 1)
            exit_y = 1 if src_cy <= lane_y else 0
            entry_y = 1 if tgt_cy <= lane_y else 0
            eid = nid("e")
            cell = ET.SubElement(root, "mxCell", id=eid, value=label,
                style=(f"edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;"
                       f"jettySize=auto;html=1;fontSize=7;endArrow=none;startArrow=none;"
                       f"exitX=0.5;exitY={exit_y};exitDx=0;exitDy=0;"
                       f"entryX=0.5;entryY={entry_y};entryDx=0;entryDy=0;"
                       f"{style}"),
                edge="1", source=src_id, target=tgt_id, parent=pids[orig_i])
            geo = ET.SubElement(cell, "mxGeometry", relative="1")
            geo.set("as", "geometry")
            arr = ET.SubElement(geo, "Array")
            arr.set("as", "points")
            ET.SubElement(arr, "mxPoint",
                          x=str(round(src_cx, 1)), y=str(round(lane_y, 1)))
            ET.SubElement(arr, "mxPoint",
                          x=str(round(tgt_cx, 1)), y=str(round(lane_y, 1)))


# ---------------------------------------------------------------------------
# Crossing-minimisation helpers
# ---------------------------------------------------------------------------

def _left_edge_lanes(edges):
    """Assign lane indices using left-edge channel assignment.

    Args:
        edges: List of edge tuples (src_cx, src_cy, tgt_cx, tgt_cy, ...).

    Returns:
        (assignments, n_lanes): lane index per edge and total lane count.
    """
    lanes = []
    assignments = []
    for edge in edges:
        src_cx, tgt_cx = edge[0], edge[2]
        x_min = min(src_cx, tgt_cx)
        x_max = max(src_cx, tgt_cx)
        assigned = False
        for li, lr in enumerate(lanes):
            if x_min > lr:
                lanes[li] = x_max
                assignments.append(li)
                assigned = True
                break
        if not assigned:
            assignments.append(len(lanes))
            lanes.append(x_max)
    return assignments, len(lanes)


def _count_vhv_crossings(edges, lane_indices):
    """Count crossings in VHV (vertical-horizontal-vertical) routing.

    A crossing occurs when a vertical leg of one edge passes through
    the horizontal segment of another edge on a different lane.

    When edge i is above edge j (lane_i < lane_j):
      - j's source vertical at src_xj may cross i's horizontal span
      - i's target vertical at tgt_xi may cross j's horizontal span
    """
    n = len(edges)
    total = 0
    for i in range(n):
        li = lane_indices[i]
        src_xi, tgt_xi = edges[i][0], edges[i][2]
        x_lo_i = min(src_xi, tgt_xi)
        x_hi_i = max(src_xi, tgt_xi)
        for j in range(i + 1, n):
            lj = lane_indices[j]
            if li == lj:
                continue
            src_xj, tgt_xj = edges[j][0], edges[j][2]
            x_lo_j = min(src_xj, tgt_xj)
            x_hi_j = max(src_xj, tgt_xj)
            if li < lj:                          # i above j
                if x_lo_i < src_xj < x_hi_i:    # j src-vert ∩ i horiz
                    total += 1
                if x_lo_j < tgt_xi < x_hi_j:    # i tgt-vert ∩ j horiz
                    total += 1
            else:                                # j above i
                if x_lo_j < src_xi < x_hi_j:    # i src-vert ∩ j horiz
                    total += 1
                if x_lo_i < tgt_xj < x_hi_i:    # j tgt-vert ∩ i horiz
                    total += 1
    return total


def _minimize_crossing_order(indexed_edges):
    """Reorder edges to minimise VHV crossings.

    Uses adjacent-swap hill climbing with bidirectional passes from
    multiple initial orderings (barycenter, left-endpoint, right-endpoint).
    For small edge counts (≤ 16), also applies insertion refinement.
    """
    n = len(indexed_edges)
    if n <= 1:
        return list(indexed_edges)

    def _evaluate(order):
        eo = [e for _, e in order]
        la, _ = _left_edge_lanes(eo)
        return _count_vhv_crossings(eo, la)

    def _swap_pass(order, best):
        """Adjacent-swap passes (forward + backward) until no improvement."""
        improved = True
        while improved:
            improved = False
            for i in range(len(order) - 1):
                order[i], order[i + 1] = order[i + 1], order[i]
                c = _evaluate(order)
                if c < best:
                    best = c
                    improved = True
                    if best == 0:
                        return best
                else:
                    order[i], order[i + 1] = order[i + 1], order[i]
            for i in range(len(order) - 2, -1, -1):
                order[i], order[i + 1] = order[i + 1], order[i]
                c = _evaluate(order)
                if c < best:
                    best = c
                    improved = True
                    if best == 0:
                        return best
                else:
                    order[i], order[i + 1] = order[i + 1], order[i]
        return best

    # Try multiple initial orderings
    by_bary = list(indexed_edges)
    by_left = sorted(indexed_edges,
                     key=lambda ie: min(ie[1][0], ie[1][2]))
    by_right = sorted(indexed_edges,
                      key=lambda ie: max(ie[1][0], ie[1][2]))

    best_order = list(by_bary)
    best_cost = _evaluate(best_order)
    if best_cost == 0:
        return best_order

    for candidate in (by_bary, by_left, by_right):
        order = list(candidate)
        cost = _swap_pass(order, _evaluate(order))
        if cost < best_cost:
            best_cost = cost
            best_order = list(order)
            if best_cost == 0:
                return best_order

    # Insertion refinement only for small edge counts
    if n <= 16:
        improved = True
        while improved:
            improved = False
            for i in range(len(best_order)):
                item = best_order.pop(i)
                current_best_pos = i
                for j in range(len(best_order) + 1):
                    if j == i:
                        continue
                    best_order.insert(j, item)
                    c = _evaluate(best_order)
                    if c < best_cost:
                        best_cost = c
                        current_best_pos = j
                        improved = True
                        if best_cost == 0:
                            return best_order
                    best_order.pop(j)
                best_order.insert(current_best_pos, item)

    return best_order


def _optimize_lane_permutation(edges, lane_indices, n_lanes):
    """Permute lane Y-order to further reduce VHV crossings.

    For small lane counts (≤ 8), tries all permutations exhaustively.
    For larger counts, uses adjacent-swap hill climbing.
    """
    if n_lanes <= 1:
        return list(lane_indices)

    best_mapped = list(lane_indices)
    best_cost = _count_vhv_crossings(edges, best_mapped)
    if best_cost == 0:
        return best_mapped

    if n_lanes <= 8:
        # Exhaustive search over all permutations (≤ 40320)
        from itertools import permutations
        for perm in permutations(range(n_lanes)):
            mapped = [perm[l] for l in lane_indices]
            c = _count_vhv_crossings(edges, mapped)
            if c < best_cost:
                best_cost = c
                best_mapped = mapped
                if best_cost == 0:
                    return best_mapped
    else:
        # Adjacent-swap hill climbing for larger lane counts
        perm = list(range(n_lanes))
        improved = True
        while improved:
            improved = False
            for i in range(n_lanes - 1):
                perm[i], perm[i + 1] = perm[i + 1], perm[i]
                mapped = [perm[l] for l in lane_indices]
                c = _count_vhv_crossings(edges, mapped)
                if c < best_cost:
                    best_cost = c
                    best_mapped = mapped
                    improved = True
                    if best_cost == 0:
                        return best_mapped
                else:
                    perm[i], perm[i + 1] = perm[i + 1], perm[i]

    return best_mapped

    return [perm[l] for l in lane_indices]


class LeftEdgeRouter(Router):
    """Left-edge channel assignment with barycenter crossing minimisation.

    1. Sort edges by barycenter (weighted average of src/tgt X) to reduce
       crossings.
    2. Compute each edge's X interval [min(src_x, tgt_x), max(src_x, tgt_x)].
    3. Assign lanes using the left-edge algorithm: reuse a lane when the new
       edge's interval does not overlap any edge already in that lane.
    4. Space lanes evenly within the routing zone.
    """

    def route(self, edges, root, route_y_min, route_y_max, obstacles=None,
              parent_ids=None):
        if not edges:
            return
        pids = parent_ids or ["1"] * len(edges)
        route_range = route_y_max - route_y_min

        # Step 1: barycenter sort + crossing minimisation
        indexed = sorted(enumerate(edges), key=lambda ie: (ie[1][0] + ie[1][2]) / 2)
        indexed = _minimize_crossing_order(indexed)

        # Step 2: left-edge lane assignment + lane permutation
        edges_ordered = [e for _, e in indexed]
        lane_assignments, n_lanes = _left_edge_lanes(edges_ordered)
        lane_assignments = _optimize_lane_permutation(
            edges_ordered, lane_assignments, n_lanes)

        # Step 3: emit edges
        for (orig_i, edge), lane_idx in zip(indexed, lane_assignments):
            src_cx, src_cy, tgt_cx, tgt_cy, src_id, tgt_id, style, label = edge
            lane_y = route_y_min + (lane_idx + 1) * route_range / (n_lanes + 1)

            exit_y = 1 if src_cy <= lane_y else 0
            entry_y = 1 if tgt_cy <= lane_y else 0

            eid = nid("e")
            cell = ET.SubElement(root, "mxCell", id=eid, value=label,
                style=(f"edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;"
                       f"jettySize=auto;html=1;fontSize=7;endArrow=none;startArrow=none;"
                       f"exitX=0.5;exitY={exit_y};exitDx=0;exitDy=0;"
                       f"entryX=0.5;entryY={entry_y};entryDx=0;entryDy=0;"
                       f"{style}"),
                edge="1", source=src_id, target=tgt_id, parent=pids[orig_i])
            geo = ET.SubElement(cell, "mxGeometry", relative="1")
            geo.set("as", "geometry")
            arr = ET.SubElement(geo, "Array")
            arr.set("as", "points")
            ET.SubElement(arr, "mxPoint",
                          x=str(round(src_cx, 1)), y=str(round(lane_y, 1)))
            ET.SubElement(arr, "mxPoint",
                          x=str(round(tgt_cx, 1)), y=str(round(lane_y, 1)))


# ---------------------------------------------------------------------------
# Obstacle-avoidance helpers
# ---------------------------------------------------------------------------

def _find_blocking(x, y_from, y_to, obstacles, exclude_xy, margin):
    """Find obstacle boxes that block a vertical segment.

    Args:
        x:          X coordinate of the vertical line.
        y_from:     Start Y of the segment.
        y_to:       End Y of the segment.
        obstacles:  List of (ox, oy, ow, oh) bounding boxes.
        exclude_xy: (x, y) point whose containing box is excluded
                    (the source or target device).
        margin:     Clearance pixels for the X-overlap check.

    Returns:
        List of (ox, oy, ow, oh) boxes that block the segment.
    """
    y_min, y_max = min(y_from, y_to), max(y_from, y_to)
    blocking = []
    for (ox, oy, ow, oh) in obstacles:
        if not (ox - margin < x < ox + ow + margin):
            continue
        if not (oy < y_max and oy + oh > y_min):
            continue
        ex, ey = exclude_xy
        if ox <= ex <= ox + ow and oy <= ey <= oy + oh:
            continue
        blocking.append((ox, oy, ow, oh))
    return blocking


def _compute_clear_x(x, blocking, margin, detour_pitch, detour_usage):
    """Compute the clear_x for a detour, applying fan-out for repeated use.

    Args:
        x:              Cable X coordinate.
        blocking:       List of blocking obstacle boxes.
        margin:         Clearance pixels around obstacles.
        detour_pitch:   Spacing between successive detour lines.
        detour_usage:   Dict mapping (combined_left, combined_right, side)
                        to usage count (mutated in place).

    Returns:
        (clear_x, fan_index) tuple — clear_x offset by fan-out,
        fan_index is the 0-based usage count for Y fan-out.
    """
    combined_left = min(ox for ox, _, _, _ in blocking)
    combined_right = max(ox + ow for ox, _, ow, _ in blocking)

    dist_left = x - combined_left
    dist_right = combined_right - x
    if dist_left <= dist_right:
        side = "left"
        base_clear_x = combined_left - margin
    else:
        side = "right"
        base_clear_x = combined_right + margin

    key = (combined_left, combined_right, side)
    n = detour_usage.get(key, 0)
    detour_usage[key] = n + 1

    if side == "left":
        return (base_clear_x - n * detour_pitch, n)
    else:
        return (base_clear_x + n * detour_pitch, n)


def _detour_waypoints(x, y_from, y_to, blocking, margin, clear_x,
                      fan_index=0, detour_pitch=6):
    """Compute detour waypoints around blocking obstacles.

    Merges all blocking boxes into one combined bounding box and generates
    a single rectangular detour using the provided clear_x.  When the
    obstacle extends past the segment end, the return jog is omitted and
    the cable stays at clear_x.

    Args:
        x:             Cable X coordinate.
        y_from:        Start Y of the segment.
        y_to:          End Y of the segment.
        blocking:      List of blocking obstacle boxes.
        margin:        Clearance pixels (used for Y clearance).
        clear_x:       Pre-computed X coordinate for the detour line.
        fan_index:     0-based index for Y fan-out (spreads horizontal
                       segments outward by fan_index * detour_pitch).
        detour_pitch:  Spacing between successive fan-out lines (px).

    Returns:
        List of (wx, wy) waypoints to insert between y_from and y_to.
    """
    going_down = y_from <= y_to
    y_seg_min = min(y_from, y_to)
    y_seg_max = max(y_from, y_to)

    combined_top = min(oy for _, oy, _, _ in blocking)
    combined_bottom = max(oy + oh for _, oy, _, oh in blocking)

    y_fan = fan_index * detour_pitch
    top_y = max(combined_top - margin - y_fan, y_seg_min)
    bot_y = min(combined_bottom + margin + y_fan, y_seg_max)

    # Check if obstacle is fully contained within segment (with margin + fan)
    fully_contained = (combined_top - margin - y_fan >= y_seg_min and
                       combined_bottom + margin + y_fan <= y_seg_max)

    if going_down:
        if fully_contained:
            return [
                (x, top_y), (clear_x, top_y),
                (clear_x, bot_y), (x, bot_y),
            ]
        else:
            return [
                (x, top_y), (clear_x, top_y),
                (clear_x, bot_y),
            ]
    else:
        if fully_contained:
            return [
                (x, bot_y), (clear_x, bot_y),
                (clear_x, top_y), (x, top_y),
            ]
        else:
            return [
                (x, bot_y), (clear_x, bot_y),
                (clear_x, top_y),
            ]


def _emit_edge(root, waypoints, src_id, tgt_id, style, label,
               exit_y, entry_y, parent_id="1"):
    """Emit an mxCell edge element with the given waypoints."""
    eid = nid("e")
    cell = ET.SubElement(root, "mxCell", id=eid, value=label,
        style=(f"edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;"
               f"jettySize=auto;html=1;fontSize=7;endArrow=none;startArrow=none;"
               f"exitX=0.5;exitY={exit_y};exitDx=0;exitDy=0;"
               f"entryX=0.5;entryY={entry_y};entryDx=0;entryDy=0;"
               f"{style}"),
        edge="1", source=src_id, target=tgt_id, parent=parent_id)
    geo = ET.SubElement(cell, "mxGeometry", relative="1")
    geo.set("as", "geometry")
    arr = ET.SubElement(geo, "Array")
    arr.set("as", "points")
    for wx, wy in waypoints:
        ET.SubElement(arr, "mxPoint",
                      x=str(round(wx, 1)), y=str(round(wy, 1)))


def _spread_vertical_segments(edge_data, pitch, x_tolerance=3,
                              min_y_overlap=20):
    """Spread vertical segments whose X and Y ranges both overlap.

    Builds the full path (port → waypoints → port) for each edge and
    extracts every vertical segment (consecutive points with matching X
    and differing Y).  Only movable waypoints are offset — port endpoints
    are fixed.

    Only segments from *different* edges whose X values are within
    *x_tolerance* pixels AND whose Y ranges overlap by at least
    *min_y_overlap* pixels are grouped and offset.  Small overlaps
    (e.g. near bend corners) are ignored because they don't cause
    visible overlap.

    Mutates waypoints in place.

    Args:
        edge_data:   List of (waypoints, src_id, tgt_id, style, label,
                     exit_y, entry_y, src_cx, tgt_cx, src_cy, tgt_cy,
                     lane_y) tuples.
        pitch:       Pixels between adjacent vertical segments.
        x_tolerance: Max X distance to consider segments overlapping.
        min_y_overlap: Minimum Y overlap (px) to trigger spreading.
                       Segments with less overlap are left as-is.
    """
    # Extract all vertical segments from full paths.
    # Each segment: (avg_x, y_min, y_max, edge_index, [waypoint_indices])
    segments = []
    for ei, (waypoints, _, _, _, _, _, _, src_cx, tgt_cx,
             src_cy, tgt_cy, _lane_y, *_rest) in enumerate(edge_data):
        n_wp = len(waypoints)
        # full_path[0] = port (immovable), [1..n_wp] = waypoints, [n_wp+1] = port
        full_path = [(src_cx, src_cy)] + list(waypoints) + [(tgt_cx, tgt_cy)]
        for k in range(len(full_path) - 1):
            x1, y1 = full_path[k]
            x2, y2 = full_path[k + 1]
            # Skip non-vertical segments
            if abs(x1 - x2) > 0.5 or abs(y1 - y2) < 0.5:
                continue
            avg_x = (x1 + x2) / 2
            y_min = min(y1, y2)
            y_max = max(y1, y2)
            # Collect movable waypoint indices (k maps to full_path index;
            # waypoint index = full_path_index - 1, valid when 1..n_wp)
            wp_idx = []
            if 1 <= k <= n_wp:
                wp_idx.append(k - 1)
            if 1 <= k + 1 <= n_wp:
                wp_idx.append(k)
            if wp_idx:
                segments.append((avg_x, y_min, y_max, ei, wp_idx))

    # Group segments with overlapping X and Y using union-find
    n = len(segments)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    for i in range(n):
        xi, yi_min, yi_max = segments[i][0], segments[i][1], segments[i][2]
        for j in range(i + 1, n):
            xj, yj_min, yj_max = segments[j][0], segments[j][1], segments[j][2]
            # Same edge, skip
            if segments[i][3] == segments[j][3]:
                continue
            # X close enough?
            if abs(xi - xj) > x_tolerance:
                continue
            # Y ranges overlap enough?
            overlap = min(yi_max, yj_max) - max(yi_min, yj_min)
            if overlap >= min_y_overlap:
                union(i, j)

    # Collect groups
    groups = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(i)

    # Apply offsets to groups with 2+ members, preventing double-adjustment
    adjusted = set()  # (edge_index, waypoint_index)
    for members in groups.values():
        if len(members) <= 1:
            continue
        # Sort by original X for stable ordering
        members.sort(key=lambda i: segments[i][0])
        k = len(members)
        for rank, si in enumerate(members):
            offset = (rank - (k - 1) / 2) * pitch
            if offset == 0:
                continue
            _, _, _, ei, wp_indices = segments[si]
            waypoints = edge_data[ei][0]
            for wi in wp_indices:
                if (ei, wi) not in adjusted:
                    adjusted.add((ei, wi))
                    wx, wy = waypoints[wi]
                    waypoints[wi] = (wx + offset, wy)


def _straighten_port_entry(edge_data, margin=10, x_threshold=15):
    """Insert waypoints so cables enter ports vertically (no kink).

    After spreading, the first/last waypoint X may differ from the port X
    (src_cx / tgt_cx).  draw.io's orthogonalEdgeStyle would then add a
    small horizontal jog near the port, which looks ugly.

    This function inserts extra waypoints to create an explicit horizontal
    jog *away* from the port, keeping the final approach vertical.

    The jog direction is determined by exit_y / entry_y so the jog is
    always on the cable side of the port (beyond the port cell edge).
    The margin must exceed half the port height (typically 6–7 px) to
    avoid placing the jog inside the port cell.

    Small X offsets (≤ x_threshold) are left to draw.io's built-in
    orthogonal routing, which handles them cleanly.  Only larger offsets
    (e.g. from detours) get explicit jog waypoints.

    Args:
        edge_data: List of edge_data tuples (mutated in place — waypoints
                   list is replaced).
        margin:    Vertical distance from the port centre at which the jog
                   occurs.  Must be > port_h / 2 (default 10 covers the
                   standard port heights of 12–14 px).
        x_threshold: Minimum X offset to trigger a jog (default 15 px).
                     Offsets from vertical spreading are typically < 15 px
                     and look fine without explicit jogs.
    """
    for i, (waypoints, src_id, tgt_id, style, label,
            exit_y, entry_y, src_cx, tgt_cx,
            src_cy, tgt_cy, lane_y, *rest) in enumerate(edge_data):
        new_wps = list(waypoints)

        # Source side: if first waypoint X is far from src_cx, insert jog
        if new_wps:
            fx, fy = new_wps[0]
            if abs(fx - src_cx) > x_threshold:
                # Large offset (detour): jog near port on the exit side.
                if exit_y == 1:
                    jog_y = src_cy + margin
                else:
                    jog_y = src_cy - margin
                new_wps.insert(0, (fx, jog_y))
                new_wps.insert(0, (src_cx, jog_y))
            # Small offsets (≤ x_threshold, from spreading) are left to
            # draw.io's orthogonal routing — no extra waypoints needed.

        # Target side: if last waypoint X is far from tgt_cx, insert jog
        if new_wps:
            lx, ly = new_wps[-1]
            if abs(lx - tgt_cx) > x_threshold:
                # Large offset: jog near port on the entry side.
                if entry_y == 0:
                    jog_y = tgt_cy - margin
                else:
                    jog_y = tgt_cy + margin
                new_wps.append((lx, jog_y))
                new_wps.append((tgt_cx, jog_y))

        if len(new_wps) != len(waypoints):
            edge_data[i] = (new_wps, src_id, tgt_id, style, label,
                            exit_y, entry_y, src_cx, tgt_cx,
                            src_cy, tgt_cy, lane_y, *rest)


class ObstacleRouter(Router):
    """LeftEdgeRouter with vertical detours to avoid device bounding boxes.

    Uses left-edge channel assignment with barycenter sorting (identical to
    LeftEdgeRouter), then checks each edge's vertical legs for intersections
    with device boxes and inserts orthogonal detour waypoints where needed.
    """

    MARGIN = 8           # clearance around obstacles for detour waypoints (px)
    DETECT_MARGIN = 0    # X-overlap margin for blocking detection (strict interior)
    DETOUR_PITCH = 6     # spacing between successive detour lines (px)
    VERTICAL_PITCH = 6   # X offset between overlapping vertical segments (px)
    VERTICAL_TOLERANCE = 2   # X tolerance for grouping vertical segments (px)

    def build_edge_data(self, edges, route_y_min, route_y_max,
                        obstacles=None, parent_ids=None):
        """Build waypoints for each edge (lane assignment + obstacle avoidance).

        Returns a list of edge_data tuples without emitting XML or spreading.
        This is used by flush_edges() for cross-zone spreading.
        """
        if not edges:
            return []
        pids = parent_ids or ["1"] * len(edges)
        route_range = route_y_max - route_y_min
        margin = self.MARGIN
        detect_margin = self.DETECT_MARGIN
        detour_pitch = self.DETOUR_PITCH

        # Step 1: barycenter sort + crossing minimisation
        indexed = sorted(enumerate(edges), key=lambda ie: (ie[1][0] + ie[1][2]) / 2)
        indexed = _minimize_crossing_order(indexed)

        # Step 2: left-edge lane assignment + lane permutation
        edges_ordered = [e for _, e in indexed]
        lane_assignments, n_lanes = _left_edge_lanes(edges_ordered)
        lane_assignments = _optimize_lane_permutation(
            edges_ordered, lane_assignments, n_lanes)
        obs = obstacles or []
        detour_usage = {}

        # Step 3: build waypoints for each edge
        edge_data = []
        for (orig_i, edge), lane_idx in zip(indexed, lane_assignments):
            src_cx, src_cy, tgt_cx, tgt_cy, src_id, tgt_id, style, label = edge
            lane_y = route_y_min + (lane_idx + 1) * route_range / (n_lanes + 1)

            exit_y = 1 if src_cy <= lane_y else 0
            entry_y = 1 if tgt_cy <= lane_y else 0

            waypoints = []

            # Source vertical leg: port → lane
            src_blocking = _find_blocking(
                src_cx, src_cy, lane_y, obs, (src_cx, src_cy), detect_margin)
            if src_blocking:
                clear_x, fan_index = _compute_clear_x(
                    src_cx, src_blocking, margin, detour_pitch, detour_usage)
                waypoints.extend(_detour_waypoints(
                    src_cx, src_cy, lane_y, src_blocking, margin, clear_x,
                    fan_index=fan_index, detour_pitch=detour_pitch))

            # Horizontal lane
            waypoints.append((src_cx, lane_y))
            waypoints.append((tgt_cx, lane_y))

            # Target vertical leg: lane → port
            tgt_blocking = _find_blocking(
                tgt_cx, lane_y, tgt_cy, obs, (tgt_cx, tgt_cy), detect_margin)
            if tgt_blocking:
                clear_x, fan_index = _compute_clear_x(
                    tgt_cx, tgt_blocking, margin, detour_pitch, detour_usage)
                waypoints.extend(_detour_waypoints(
                    tgt_cx, lane_y, tgt_cy, tgt_blocking, margin, clear_x,
                    fan_index=fan_index, detour_pitch=detour_pitch))

            edge_data.append((waypoints, src_id, tgt_id, style, label,
                              exit_y, entry_y, src_cx, tgt_cx,
                              src_cy, tgt_cy, lane_y, pids[orig_i]))

        return edge_data

    @staticmethod
    def emit_edge_data(edge_data, root):
        """Emit edge_data as mxCell elements into *root*."""
        for (waypoints, src_id, tgt_id, style, label,
             exit_y, entry_y, _, _, _, _, _, parent_id) in edge_data:
            _emit_edge(root, waypoints, src_id, tgt_id, style, label,
                       exit_y, entry_y, parent_id=parent_id)

    def route(self, edges, root, route_y_min, route_y_max, obstacles=None,
              parent_ids=None):
        edge_data = self.build_edge_data(
            edges, route_y_min, route_y_max, obstacles, parent_ids)
        if not edge_data:
            return
        _spread_vertical_segments(edge_data, self.VERTICAL_PITCH)
        self.emit_edge_data(edge_data, root)
