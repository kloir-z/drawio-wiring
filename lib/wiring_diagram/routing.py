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
            if src_cy <= tgt_cy:
                exit_y, entry_y = 1, 0
            else:
                exit_y, entry_y = 0, 1
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

        # Step 1: barycenter sort (reduces crossings)
        indexed = sorted(enumerate(edges), key=lambda ie: (ie[1][0] + ie[1][2]) / 2)

        # Step 2+3: left-edge lane assignment
        lanes = []  # list of rightmost-x values
        lane_assignments = []

        for _, edge in indexed:
            src_cx, _, tgt_cx = edge[0], edge[1], edge[2]
            x_min = min(src_cx, tgt_cx)
            x_max = max(src_cx, tgt_cx)

            assigned = False
            for lane_idx, lane_right in enumerate(lanes):
                if x_min > lane_right:
                    lanes[lane_idx] = x_max
                    lane_assignments.append(lane_idx)
                    assigned = True
                    break
            if not assigned:
                lane_assignments.append(len(lanes))
                lanes.append(x_max)

        n_lanes = len(lanes)

        # Step 4: emit edges
        for (orig_i, edge), lane_idx in zip(indexed, lane_assignments):
            src_cx, src_cy, tgt_cx, tgt_cy, src_id, tgt_id, style, label = edge
            lane_y = route_y_min + (lane_idx + 1) * route_range / (n_lanes + 1)

            if src_cy <= tgt_cy:
                exit_y, entry_y = 1, 0
            else:
                exit_y, entry_y = 0, 1

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


def _spread_vertical_segments(edge_data, pitch, x_tolerance=3):
    """Spread vertical segments whose X and Y ranges both overlap.

    Each edge has up to two vertical segments:
      - Source side: X=src_cx, Y from src_cy to lane_y
      - Target side: X=tgt_cx, Y from lane_y to tgt_cy

    Only segments whose X values are within *x_tolerance* pixels AND
    whose Y ranges overlap are grouped and offset.

    Mutates waypoints in place.

    Args:
        edge_data:   List of (waypoints, src_id, tgt_id, style, label,
                     exit_y, entry_y, src_cx, tgt_cx, src_cy, tgt_cy,
                     lane_y) tuples.
        pitch:       Pixels between adjacent vertical segments.
        x_tolerance: Max X distance to consider segments overlapping.
    """
    # Extract all vertical segments: (x, y_min, y_max, edge_index, side,
    #                                  [waypoint_indices_at_this_x])
    segments = []
    for ei, (waypoints, _, _, _, _, _, _, src_cx, tgt_cx,
             src_cy, tgt_cy, lane_y, *_rest) in enumerate(edge_data):
        # Source side vertical segment
        src_y_min = min(src_cy, lane_y)
        src_y_max = max(src_cy, lane_y)
        src_wp_idx = [i for i, (wx, _) in enumerate(waypoints)
                      if abs(wx - src_cx) < 0.5]
        if src_wp_idx:
            segments.append((src_cx, src_y_min, src_y_max, ei, "src",
                             src_wp_idx))

        # Target side vertical segment
        tgt_y_min = min(tgt_cy, lane_y)
        tgt_y_max = max(tgt_cy, lane_y)
        tgt_wp_idx = [i for i, (wx, _) in enumerate(waypoints)
                      if abs(wx - tgt_cx) < 0.5]
        if tgt_wp_idx:
            segments.append((tgt_cx, tgt_y_min, tgt_y_max, ei, "tgt",
                             tgt_wp_idx))

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
            # Y ranges overlap?
            if yi_min < yj_max and yj_min < yi_max:
                union(i, j)

    # Collect groups
    groups = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(i)

    # Apply offsets to groups with 2+ members
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
            _, _, _, ei, _, wp_indices = segments[si]
            waypoints = edge_data[ei][0]
            for wi in wp_indices:
                wx, wy = waypoints[wi]
                waypoints[wi] = (wx + offset, wy)


class ObstacleRouter(Router):
    """LeftEdgeRouter with vertical detours to avoid device bounding boxes.

    Uses left-edge channel assignment with barycenter sorting (identical to
    LeftEdgeRouter), then checks each edge's vertical legs for intersections
    with device boxes and inserts orthogonal detour waypoints where needed.
    """

    MARGIN = 8           # clearance around obstacles for detour waypoints (px)
    DETECT_MARGIN = 0    # X-overlap margin for blocking detection (strict interior)
    DETOUR_PITCH = 6     # spacing between successive detour lines (px)
    VERTICAL_PITCH = 4   # X offset between overlapping vertical segments (px)

    def route(self, edges, root, route_y_min, route_y_max, obstacles=None,
              parent_ids=None):
        if not edges:
            return
        pids = parent_ids or ["1"] * len(edges)
        route_range = route_y_max - route_y_min
        margin = self.MARGIN
        detect_margin = self.DETECT_MARGIN
        detour_pitch = self.DETOUR_PITCH
        vert_pitch = self.VERTICAL_PITCH

        # Step 1: barycenter sort (keep original index for parent_id mapping)
        indexed = sorted(enumerate(edges), key=lambda ie: (ie[1][0] + ie[1][2]) / 2)

        # Step 2+3: left-edge lane assignment
        lanes = []
        lane_assignments = []

        for _, edge in indexed:
            src_cx, _, tgt_cx = edge[0], edge[1], edge[2]
            x_min = min(src_cx, tgt_cx)
            x_max = max(src_cx, tgt_cx)

            assigned = False
            for lane_idx, lane_right in enumerate(lanes):
                if x_min > lane_right:
                    lanes[lane_idx] = x_max
                    lane_assignments.append(lane_idx)
                    assigned = True
                    break
            if not assigned:
                lane_assignments.append(len(lanes))
                lanes.append(x_max)

        n_lanes = len(lanes)
        obs = obstacles or []
        detour_usage = {}

        # Step 4: build waypoints for each edge
        edge_data = []  # list of (waypoints, src_id, tgt_id, style, label,
                        #          exit_y, entry_y, src_cx, tgt_cx,
                        #          src_cy, tgt_cy, lane_y, parent_id)
        for (orig_i, edge), lane_idx in zip(indexed, lane_assignments):
            src_cx, src_cy, tgt_cx, tgt_cy, src_id, tgt_id, style, label = edge
            lane_y = route_y_min + (lane_idx + 1) * route_range / (n_lanes + 1)

            if src_cy <= tgt_cy:
                exit_y, entry_y = 1, 0
            else:
                exit_y, entry_y = 0, 1

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

        # Step 5: spread overlapping vertical segments
        _spread_vertical_segments(edge_data, vert_pitch)

        # Step 6: emit edges
        for (waypoints, src_id, tgt_id, style, label,
             exit_y, entry_y, _, _, _, _, _, parent_id) in edge_data:
            _emit_edge(root, waypoints, src_id, tgt_id, style, label,
                       exit_y, entry_y, parent_id=parent_id)
