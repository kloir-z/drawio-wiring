"""Tests for routing strategies (lane count, crossing minimisation)."""

import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, '/home/user/code/drawio_infra_py/lib')

from wiring_diagram import Diagram, nid, reset_ids, BG_BLUE, PORT_BLUE, EDGE_BLUE
from wiring_diagram.routing import (
    NaiveRouter, LeftEdgeRouter, ObstacleRouter,
    _find_blocking, _detour_waypoints, _compute_clear_x,
)


def _make_edges(intervals):
    """Create edge tuples from a list of (src_x, tgt_x) pairs.

    src_cy=50 (top), tgt_cy=400 (bottom) for all edges.
    """
    edges = []
    for i, (sx, tx) in enumerate(intervals):
        edges.append((sx, 50, tx, 400, f"s{i}", f"t{i}", EDGE_BLUE, ""))
    return edges


def _count_lanes(root):
    """Count distinct Y values among waypoints (= number of lanes used)."""
    ys = set()
    for arr in root.iter("Array"):
        for pt in arr.findall("mxPoint"):
            ys.add(pt.get("y"))
    return len(ys)


def _count_crossings(root):
    """Count edge crossings based on waypoint X pairs.

    Two edges cross if their source and target X ordering is reversed.
    """
    edge_xs = []
    for cell in root.findall("mxCell"):
        if cell.get("edge") != "1":
            continue
        geo = cell.find("mxGeometry")
        if geo is None:
            continue
        arr = geo.find("Array")
        if arr is None:
            continue
        pts = arr.findall("mxPoint")
        if len(pts) >= 2:
            edge_xs.append((float(pts[0].get("x")), float(pts[1].get("x"))))
    crossings = 0
    for i in range(len(edge_xs)):
        for j in range(i + 1, len(edge_xs)):
            s1, t1 = edge_xs[i]
            s2, t2 = edge_xs[j]
            if (s1 - s2) * (t1 - t2) < 0:
                crossings += 1
    return crossings


class TestNaiveRouter(unittest.TestCase):

    def test_lane_count_equals_edge_count(self):
        """NaiveRouter assigns one lane per edge."""
        reset_ids()
        root = ET.Element("root")
        router = NaiveRouter()
        edges = _make_edges([(10, 200), (50, 250), (100, 300)])
        router.route(edges, root, 100, 300)
        self.assertEqual(_count_lanes(root), 3)

    def test_empty_edges(self):
        root = ET.Element("root")
        router = NaiveRouter()
        router.route([], root, 100, 300)
        self.assertEqual(len(root.findall("mxCell")), 0)


class TestLeftEdgeRouter(unittest.TestCase):

    def test_non_overlapping_reuses_lanes(self):
        """Non-overlapping X intervals should share lanes."""
        reset_ids()
        root = ET.Element("root")
        router = LeftEdgeRouter()
        # Three non-overlapping intervals: [10,50], [100,150], [200,250]
        edges = _make_edges([(10, 50), (100, 150), (200, 250)])
        router.route(edges, root, 100, 300)
        self.assertEqual(_count_lanes(root), 1)

    def test_overlapping_uses_more_lanes(self):
        """Overlapping X intervals need separate lanes."""
        reset_ids()
        root = ET.Element("root")
        router = LeftEdgeRouter()
        # All overlap: [10,300], [50,350], [100,400]
        edges = _make_edges([(10, 300), (50, 350), (100, 400)])
        router.route(edges, root, 100, 300)
        self.assertEqual(_count_lanes(root), 3)

    def test_partial_overlap_compression(self):
        """Mix of overlapping and non-overlapping → fewer lanes than edges."""
        reset_ids()
        root = ET.Element("root")
        router = LeftEdgeRouter()
        # [10,100], [50,150], [200,300], [250,350]
        # First two overlap, last two overlap, but groups don't overlap each other
        edges = _make_edges([(10, 100), (50, 150), (200, 300), (250, 350)])
        router.route(edges, root, 100, 400)
        lanes = _count_lanes(root)
        self.assertLess(lanes, 4)
        self.assertGreaterEqual(lanes, 2)

    def test_lane_compression_vs_naive(self):
        """LeftEdgeRouter should use fewer or equal lanes than NaiveRouter."""
        reset_ids()
        intervals = [(10, 50), (100, 150), (200, 250), (20, 300), (60, 180)]
        root_naive = ET.Element("root")
        NaiveRouter().route(_make_edges(intervals), root_naive, 100, 400)
        naive_lanes = _count_lanes(root_naive)

        reset_ids()
        root_left = ET.Element("root")
        LeftEdgeRouter().route(_make_edges(intervals), root_left, 100, 400)
        left_lanes = _count_lanes(root_left)

        self.assertLessEqual(left_lanes, naive_lanes)


class TestMultiZoneRouting(unittest.TestCase):

    def test_zone_edges_routed_independently(self):
        """Edges in different zones should be routed in their respective zones."""
        reset_ids()
        D = Diagram(800, 600, 100, 300)
        # Default zone
        D.add_edge(10, 50, 200, 150, "s1", "t1", EDGE_BLUE)
        # Custom zone
        D.add_edge(10, 350, 200, 500, "s2", "t2", EDGE_BLUE, zone=(300, 500))
        D.flush_edges()

        edge_cells = [c for c in D.R.findall("mxCell") if c.get("edge") == "1"]
        self.assertEqual(len(edge_cells), 2)

        # Extract lane Y values
        lane_ys = []
        for cell in edge_cells:
            geo = cell.find("mxGeometry")
            arr = geo.find("Array")
            pts = arr.findall("mxPoint")
            lane_ys.append(float(pts[0].get("y")))

        # One should be in [100, 300], the other in [300, 500]
        self.assertTrue(100 < lane_ys[0] < 300 or 100 < lane_ys[1] < 300)
        self.assertTrue(300 < lane_ys[0] < 500 or 300 < lane_ys[1] < 500)

    def test_default_zone_backward_compat(self):
        """add_edge() without zone should work as before."""
        reset_ids()
        D = Diagram(800, 600, 100, 300)
        D.add_edge(10, 50, 200, 400, "s1", "t1", EDGE_BLUE)
        D.flush_edges()
        edge_cells = [c for c in D.R.findall("mxCell") if c.get("edge") == "1"]
        self.assertEqual(len(edge_cells), 1)


class TestCrossingCount(unittest.TestCase):

    def test_barycenter_reduces_crossings(self):
        """LeftEdgeRouter with barycenter sort should have ≤ crossings vs naive order."""
        reset_ids()
        # Deliberately crossing pattern: src goes left-to-right,
        # tgt goes right-to-left
        intervals = [(10, 400), (100, 300), (200, 200), (300, 100), (400, 10)]
        root_naive = ET.Element("root")
        NaiveRouter().route(_make_edges(intervals), root_naive, 100, 400)
        naive_crossings = _count_crossings(root_naive)

        reset_ids()
        root_left = ET.Element("root")
        LeftEdgeRouter().route(_make_edges(intervals), root_left, 100, 400)
        left_crossings = _count_crossings(root_left)

        self.assertLessEqual(left_crossings, naive_crossings)


class TestFindBlocking(unittest.TestCase):
    """Unit tests for _find_blocking helper."""

    def test_no_obstacles(self):
        result = _find_blocking(100, 50, 400, [], (100, 50), 8)
        self.assertEqual(result, [])

    def test_obstacle_in_path(self):
        """Obstacle box directly in the vertical segment."""
        obs = [(80, 200, 100, 50)]  # x=80..180, y=200..250
        result = _find_blocking(100, 50, 400, obs, (100, 50), 8)
        self.assertEqual(len(result), 1)

    def test_obstacle_excluded_by_endpoint(self):
        """Obstacle containing the start point is excluded (source device)."""
        obs = [(80, 30, 100, 50)]  # x=80..180, y=30..80 — contains (100, 50)
        result = _find_blocking(100, 50, 400, obs, (100, 50), 8)
        self.assertEqual(result, [])

    def test_obstacle_outside_x(self):
        """Obstacle at different X is not blocking."""
        obs = [(300, 200, 100, 50)]  # x=300..400 — cable at x=100
        result = _find_blocking(100, 50, 400, obs, (100, 50), 8)
        self.assertEqual(result, [])

    def test_obstacle_outside_y(self):
        """Obstacle outside the Y range is not blocking."""
        obs = [(80, 500, 100, 50)]  # y=500..550 — segment is y=50..400
        result = _find_blocking(100, 50, 400, obs, (100, 50), 8)
        self.assertEqual(result, [])

    def test_multiple_blocking(self):
        """Multiple obstacles in the path."""
        obs = [
            (80, 150, 100, 30),  # y=150..180
            (90, 250, 80, 40),   # y=250..290
        ]
        result = _find_blocking(100, 50, 400, obs, (100, 50), 8)
        self.assertEqual(len(result), 2)


class TestDetourWaypoints(unittest.TestCase):
    """Unit tests for _detour_waypoints helper."""

    def test_single_obstacle_fully_contained(self):
        """Detour around an obstacle fully within the segment."""
        blocking = [(80, 200, 100, 50)]  # x=80..180, y=200..250
        clear_x = 72  # left side: 80 - 8
        wps = _detour_waypoints(100, 50, 400, blocking, 8, clear_x)
        self.assertEqual(len(wps), 4)
        self.assertEqual(wps[0], (100, 192))  # above obstacle
        self.assertEqual(wps[1], (72, 192))   # jog left
        self.assertEqual(wps[2], (72, 258))   # below obstacle
        self.assertEqual(wps[3], (100, 258))  # back to cable X

    def test_single_obstacle_going_up(self):
        """Detour around an obstacle, cable going up."""
        blocking = [(80, 200, 100, 50)]
        clear_x = 72
        wps = _detour_waypoints(100, 400, 50, blocking, 8, clear_x)
        self.assertEqual(len(wps), 4)
        # Going up: reversed order
        self.assertEqual(wps[0], (100, 258))
        self.assertEqual(wps[1], (72, 258))
        self.assertEqual(wps[2], (72, 192))
        self.assertEqual(wps[3], (100, 192))

    def test_obstacle_extends_past_segment(self):
        """Obstacle extending past segment end omits return jog."""
        # Segment y=50..225, obstacle y=200..260 (extends 35px past)
        blocking = [(80, 200, 100, 60)]
        clear_x = 72
        wps = _detour_waypoints(100, 50, 225, blocking, 8, clear_x)
        # No return jog: 3 waypoints (clamped bot_y to 225)
        self.assertEqual(len(wps), 3)
        self.assertEqual(wps[0], (100, 192))
        self.assertEqual(wps[1], (72, 192))
        self.assertEqual(wps[2], (72, 225))

    def test_fan_out_y_offsets(self):
        """fan_index=0,1,2 should spread top_y/bot_y by DETOUR_PITCH."""
        blocking = [(80, 200, 100, 50)]  # y=200..250
        clear_x = 72
        pitch = 6
        tops = []
        bots = []
        for fi in range(3):
            wps = _detour_waypoints(100, 50, 400, blocking, 8, clear_x,
                                    fan_index=fi, detour_pitch=pitch)
            self.assertEqual(len(wps), 4)
            tops.append(wps[0][1])  # top_y
            bots.append(wps[2][1])  # bot_y
        # top_y should decrease by pitch each step
        self.assertEqual(tops, [192, 186, 180])
        # bot_y should increase by pitch each step
        self.assertEqual(bots, [258, 264, 270])

    def test_detour_picks_closer_side(self):
        """Detour should pick the side closer to the cable X."""
        # Cable at x=170, obstacle at x=80..180 → dist_right=10 < dist_left=90
        blocking = [(80, 200, 100, 50)]
        clear_x = 188  # right side: 180 + 8
        wps = _detour_waypoints(170, 50, 400, blocking, 8, clear_x)
        # Should jog right
        self.assertEqual(wps[1][0], 188)  # right side + margin


class TestComputeClearX(unittest.TestCase):
    """Unit tests for _compute_clear_x helper (fan-out logic)."""

    def test_fan_out_distinct_x(self):
        """3 cables detouring same obstacle get 3 distinct clear_x values."""
        blocking = [(80, 200, 100, 50)]  # x=80..180
        usage = {}
        xs = []
        fan_indices = []
        for _ in range(3):
            cx, fi = _compute_clear_x(100, blocking, 8, 6, usage)
            xs.append(cx)
            fan_indices.append(fi)
        self.assertEqual(len(set(xs)), 3, f"Expected 3 distinct clear_x, got {xs}")
        # All on the left side (dist_left=20 < dist_right=80)
        # base=72, then 66, then 60
        self.assertEqual(xs, [72, 66, 60])
        self.assertEqual(fan_indices, [0, 1, 2])

    def test_gap_no_detour(self):
        """Cable 3px from device edge should NOT be detected as blocking
        with DETECT_MARGIN=0 (strict interior)."""
        # Device at x=100..200, cable at x=203 (3px from right edge)
        obs = [(100, 200, 100, 50)]
        result = _find_blocking(203, 50, 400, obs, (203, 50), 0)
        self.assertEqual(result, [], "Cable outside edge should not be blocked")

    def test_tight_overlap_still_detours(self):
        """Cable 1px inside device should still be detected as blocking."""
        # Device at x=100..200, cable at x=199 (1px inside right edge)
        obs = [(100, 200, 100, 50)]
        result = _find_blocking(199, 50, 400, obs, (199, 50), 0)
        self.assertEqual(len(result), 1, "Cable 1px inside should be blocked")

    def test_edge_exact_no_detour(self):
        """Cable exactly on device edge should NOT be detected (strict interior)."""
        # Device at x=100..200, cable at x=200 (on right edge)
        obs = [(100, 200, 100, 50)]
        result = _find_blocking(200, 50, 400, obs, (200, 50), 0)
        self.assertEqual(result, [], "Cable on edge should not be blocked")


class TestObstacleRouter(unittest.TestCase):
    """Integration tests for ObstacleRouter."""

    def test_no_obstacles_same_as_left_edge(self):
        """Without obstacles, ObstacleRouter should produce same lane count."""
        reset_ids()
        root_left = ET.Element("root")
        LeftEdgeRouter().route(_make_edges([(10, 200), (50, 250)]),
                               root_left, 100, 300)
        left_lanes = _count_lanes(root_left)

        reset_ids()
        root_obs = ET.Element("root")
        ObstacleRouter().route(_make_edges([(10, 200), (50, 250)]),
                               root_obs, 100, 300, obstacles=[])
        obs_lanes = _count_lanes(root_obs)
        # Lane count should match (Y values in routing zone)
        self.assertEqual(left_lanes, obs_lanes)

    def test_detour_adds_waypoints(self):
        """When an obstacle blocks a vertical leg, extra waypoints are added."""
        reset_ids()
        root = ET.Element("root")
        # Edge from (100, 50) to (100, 400), obstacle at (80, 200, 100, 50)
        edges = [(100, 50, 100, 400, "s0", "t0", EDGE_BLUE, "")]
        obstacles = [(80, 200, 100, 50)]
        ObstacleRouter().route(edges, root, 100, 300, obstacles=obstacles)

        cells = root.findall("mxCell")
        self.assertEqual(len(cells), 1)
        arr = cells[0].find("mxGeometry").find("Array")
        pts = arr.findall("mxPoint")
        # More than the standard 2 waypoints
        self.assertGreater(len(pts), 2)

    def test_excludes_source_device(self):
        """Source device box should not trigger detour."""
        reset_ids()
        root = ET.Element("root")
        # Source at (100, 50) inside box (80, 30, 100, 50) = x=80..180, y=30..80
        edges = [(100, 50, 200, 400, "s0", "t0", EDGE_BLUE, "")]
        obstacles = [(80, 30, 100, 50)]  # source device only
        ObstacleRouter().route(edges, root, 100, 300, obstacles=obstacles)

        cells = root.findall("mxCell")
        arr = cells[0].find("mxGeometry").find("Array")
        pts = arr.findall("mxPoint")
        # Standard 2 waypoints (no detour needed)
        self.assertEqual(len(pts), 2)

    def test_empty_edges(self):
        """Empty edge list should not crash."""
        root = ET.Element("root")
        ObstacleRouter().route([], root, 100, 300, obstacles=[(0, 0, 10, 10)])
        self.assertEqual(len(root.findall("mxCell")), 0)

    def test_09_combined_no_crash(self):
        """Full 09_combined diagram generates without error."""
        import subprocess
        result = subprocess.run(
            ["python3", "sandbox/09_combined/gen_combined.py"],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_vertical_segment_avoids_obstacle(self):
        """Verify that no vertical waypoint segment passes through an obstacle.

        Uses realistic geometry: obstacle is between source port and routing
        zone (not overlapping the zone itself).
        """
        reset_ids()
        root = ET.Element("root")
        # Source at y=50, target at y=500, routing zone at y=100..180
        # Obstacle at y=250..310 (between zone and target, in the target leg)
        edges = [(150, 50, 150, 500, "s0", "t0", EDGE_BLUE, "")]
        obstacle = (100, 250, 100, 60)  # x=100..200, y=250..310
        ObstacleRouter().route(edges, root, 100, 180, obstacles=[obstacle])

        cells = root.findall("mxCell")
        arr = cells[0].find("mxGeometry").find("Array")
        pts = [(float(p.get("x")), float(p.get("y")))
               for p in arr.findall("mxPoint")]

        # Check no vertical segment at x within [100, 200] passes through
        # y=[250, 310]
        ox, oy, ow, oh = obstacle
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            if x1 == x2:  # vertical segment
                if ox < x1 < ox + ow:
                    seg_y_min = min(y1, y2)
                    seg_y_max = max(y1, y2)
                    overlaps = seg_y_min < oy + oh and seg_y_max > oy
                    self.assertFalse(overlaps,
                        f"Vertical segment ({x1}, {seg_y_min}..{seg_y_max}) "
                        f"passes through obstacle {obstacle}")


class TestChannelGapExpansion(unittest.TestCase):
    """Tests for transit-aware gap expansion in layout."""

    def _make_topology(self):
        """3-layer topology: top(1) → mid(3) → bottom(1), cable skips mid."""
        from wiring_diagram import Topology
        T = Topology()
        T.add_device("top1", label="Top", style=BG_BLUE, layer=0,
                     ports=[("d1", PORT_BLUE)])
        # 3 devices in mid layer to create 2 gaps
        T.add_device("mid1", label="Mid1", style=BG_BLUE, layer=1,
                     ports=[("u1", PORT_BLUE), ("d1", PORT_BLUE)])
        T.add_device("mid2", label="Mid2", style=BG_BLUE, layer=1,
                     ports=[("u1", PORT_BLUE), ("d1", PORT_BLUE)])
        T.add_device("mid3", label="Mid3", style=BG_BLUE, layer=1,
                     ports=[("u1", PORT_BLUE), ("d1", PORT_BLUE)])
        T.add_device("bot1", label="Bot", style=BG_BLUE, layer=2,
                     ports=[("u1", PORT_BLUE)])
        return T

    def test_channel_gap_widens(self):
        """Transit cables should widen the gap between devices."""
        from wiring_diagram.layout import compute_layout
        T = self._make_topology()
        # Cable from top1 to bot1 skipping mid layer → transits a gap
        T.add_cable("top1", "d1", "bot1", "u1", style=EDGE_BLUE)

        layout = compute_layout(T, device_gap=25, cables=T.cables)
        devs = layout['devices']

        # Check that at least one gap in layer 1 is wider than base 25px
        mid_devs = ["mid1", "mid2", "mid3"]
        gaps = []
        for i in range(len(mid_devs) - 1):
            left_end = devs[mid_devs[i]]['x'] + devs[mid_devs[i]]['w']
            right_start = devs[mid_devs[i + 1]]['x']
            gaps.append(right_start - left_end)

        self.assertTrue(any(g > 25 for g in gaps),
                        f"Expected at least one gap > 25px, got {gaps}")

    def test_no_transit_unchanged(self):
        """Without transit cables, gaps remain at base_gap."""
        from wiring_diagram.layout import compute_layout
        T = self._make_topology()
        # Only adjacent-layer cables (no transit)
        T.add_cable("top1", "d1", "mid2", "u1", style=EDGE_BLUE)
        T.add_cable("mid2", "d1", "bot1", "u1", style=EDGE_BLUE)

        layout = compute_layout(T, device_gap=25, cables=T.cables)
        devs = layout['devices']

        # Sort mid-layer devices by X position
        mid_devs = sorted(
            [d for d in ["mid1", "mid2", "mid3"]],
            key=lambda d: devs[d]['x'])
        for i in range(len(mid_devs) - 1):
            left_end = devs[mid_devs[i]]['x'] + devs[mid_devs[i]]['w']
            right_start = devs[mid_devs[i + 1]]['x']
            gap = right_start - left_end
            self.assertEqual(gap, 25,
                             f"Gap {i} should be 25px, got {gap}")

    def test_09_combined_gaps(self):
        """09_combined layer 2 gaps should be wider than 25px base."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gen_combined",
            "/home/user/code/drawio_infra_py/sandbox/09_combined/gen_combined.py")
        # We can't easily import the script (it calls save), so instead
        # replicate the topology and check layout
        from wiring_diagram.layout import compute_layout
        import subprocess
        # Run the script and check it succeeds first
        result = subprocess.run(
            ["python3", "sandbox/09_combined/gen_combined.py"],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

        # Parse the output drawio to verify layer 2 device positions
        import xml.etree.ElementTree as ET2
        tree = ET2.parse(
            "/home/user/code/drawio_infra_py/sandbox/09_combined/combined.drawio")
        root = tree.getroot()

        # Find layer-2 device cells (mgmt1, acc1..acc4, mgmt2) by their id
        layer2_ids = ["mgmt1", "acc1", "acc2", "acc3", "acc4", "mgmt2"]
        positions = {}
        for cell in root.iter("mxCell"):
            cid = cell.get("id")
            if cid in layer2_ids:
                geo = cell.find("mxGeometry")
                if geo is not None:
                    x = float(geo.get("x", 0))
                    w = float(geo.get("width", 0))
                    positions[cid] = (x, w)

        # At least some gaps should be > 25px
        if len(positions) >= 2:
            sorted_devs = sorted(positions.items(), key=lambda kv: kv[1][0])
            gaps = []
            for i in range(len(sorted_devs) - 1):
                _, (x1, w1) = sorted_devs[i]
                _, (x2, _) = sorted_devs[i + 1]
                gaps.append(x2 - (x1 + w1))
            self.assertTrue(any(g > 25 for g in gaps),
                            f"Expected some layer-2 gap > 25px, got {gaps}")


if __name__ == "__main__":
    unittest.main()
