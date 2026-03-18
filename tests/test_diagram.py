"""Tests for Diagram XML structure (cell counts, parent-child relationships)."""

import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, '/home/user/code/drawio_infra_py/lib')

from wiring_diagram import Diagram, nid, reset_ids, BG_BLUE, PORT_BLUE, PORT_GREEN, PORT_GRAY, EDGE_BLUE


class TestDiagramBasicStructure(unittest.TestCase):

    def setUp(self):
        reset_ids()

    def test_empty_diagram_has_root_cells(self):
        D = Diagram(800, 600, 100, 300)
        cells = D.R.findall("mxCell")
        self.assertEqual(len(cells), 2)
        self.assertEqual(cells[0].get("id"), "0")
        self.assertEqual(cells[1].get("id"), "1")

    def test_device_creates_container_and_ports(self):
        D = Diagram(800, 600, 100, 300)
        ports = [("p1", "pid1", PORT_BLUE), ("p2", "pid2", PORT_BLUE)]
        result = D.device("sw1", "Switch", 10, 20, BG_BLUE, ports)
        cells = D.R.findall("mxCell")
        # 2 root + 1 container + 2 ports = 5
        self.assertEqual(len(cells), 5)
        # check port parent
        for cell in cells[3:]:
            self.assertEqual(cell.get("parent"), "sw1")
        # check return dict
        self.assertIn("p1", result)
        self.assertIn("p2", result)
        pid, cx, cy = result["p1"]
        self.assertEqual(pid, "pid1")

    def test_device_with_sublabel(self):
        D = Diagram(800, 600, 100, 300)
        ports = [("p1", "pid1", PORT_BLUE)]
        D.device("sw1", "Switch", 10, 20, BG_BLUE, ports,
                 sublabel="1/0/1 - 1/0/24")
        cells = D.R.findall("mxCell")
        # 2 root + 1 container + 1 port + 1 sublabel = 5
        self.assertEqual(len(cells), 5)

    def test_device_carded_structure(self):
        D = Diagram(800, 600, 100, 300)
        cards = [
            ("Card-A", [
                ("NIC#1", "n1", True, PORT_BLUE),
                ("NIC#2", "n2", False, PORT_BLUE),
            ]),
        ]
        result = D.device_carded("srv1", "Server", 10, 400, BG_BLUE, cards)
        # NIC#1 has SFP → conn is sfp id
        self.assertIn("NIC#1", result)
        self.assertIn("NIC#2", result)
        # SFP cell should be created for NIC#1
        sfp_id = result["NIC#1"][0]
        self.assertTrue(sfp_id.startswith("sfp_"))

    def test_simple_edge(self):
        D = Diagram(800, 600, 100, 300)
        D.simple_edge("a", "b", "Link", "strokeColor=#000;")
        cells = D.R.findall("mxCell")
        edge_cells = [c for c in cells if c.get("edge") == "1"]
        self.assertEqual(len(edge_cells), 1)
        self.assertEqual(edge_cells[0].get("source"), "a")
        self.assertEqual(edge_cells[0].get("target"), "b")

    def test_save_produces_valid_xml(self):
        D = Diagram(800, 600, 100, 300)
        D.device("sw1", "SW", 0, 0, BG_BLUE,
                 [("p1", "pid1", PORT_BLUE)])
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".drawio", delete=False) as f:
            path = f.name
        try:
            D.save(path)
            tree = ET.parse(path)
            root = tree.getroot()
            self.assertEqual(root.tag, "mxfile")
        finally:
            os.unlink(path)

    def test_container_returns_cid(self):
        D = Diagram(800, 600, 100, 300)
        cid = D.container("box1", "Box", 0, 0, 100, 50, BG_BLUE)
        self.assertEqual(cid, "box1")

    def test_add_edge_queues_and_flush_emits(self):
        D = Diagram(800, 600, 100, 300)
        D.add_edge(10, 50, 200, 400, "s1", "t1", EDGE_BLUE)
        D.add_edge(50, 50, 250, 400, "s2", "t2", EDGE_BLUE)
        D.flush_edges()
        edge_cells = [c for c in D.R.findall("mxCell") if c.get("edge") == "1"]
        self.assertEqual(len(edge_cells), 2)
        # After flush, edge queue should be empty
        total = sum(len(v) for v in D._edge_zones.values())
        self.assertEqual(total, 0)


class TestNid(unittest.TestCase):

    def test_nid_increments(self):
        reset_ids()
        a = nid("x")
        b = nid("x")
        self.assertEqual(a, "x_1")
        self.assertEqual(b, "x_2")

    def test_nid_default_prefix(self):
        reset_ids()
        self.assertEqual(nid(), "c_1")


class TestLayers(unittest.TestCase):

    def setUp(self):
        reset_ids()

    def test_add_layer_creates_cell(self):
        D = Diagram(800, 600, 100, 300)
        layer_id = D.add_layer("iSCSI")
        cells = D.R.findall("mxCell")
        layer_cell = [c for c in cells if c.get("id") == layer_id]
        self.assertEqual(len(layer_cell), 1)
        self.assertEqual(layer_cell[0].get("value"), "iSCSI")
        self.assertEqual(layer_cell[0].get("parent"), "0")

    def test_add_layer_idempotent(self):
        D = Diagram(800, 600, 100, 300)
        id1 = D.add_layer("iSCSI")
        id2 = D.add_layer("iSCSI")
        self.assertEqual(id1, id2)

    def test_edge_with_layer_has_correct_parent(self):
        D = Diagram(800, 600, 100, 300)
        D.add_edge(10, 50, 200, 400, "s1", "t1", EDGE_BLUE, layer="iSCSI")
        D.flush_edges()
        edge_cells = [c for c in D.R.findall("mxCell") if c.get("edge") == "1"]
        self.assertEqual(len(edge_cells), 1)
        parent = edge_cells[0].get("parent")
        self.assertNotEqual(parent, "1")
        # Verify the parent cell exists and has correct value
        layer_cell = [c for c in D.R.findall("mxCell") if c.get("id") == parent]
        self.assertEqual(len(layer_cell), 1)
        self.assertEqual(layer_cell[0].get("value"), "iSCSI")

    def test_edge_without_layer_has_default_parent(self):
        D = Diagram(800, 600, 100, 300)
        D.add_edge(10, 50, 200, 400, "s1", "t1", EDGE_BLUE)
        D.flush_edges()
        edge_cells = [c for c in D.R.findall("mxCell") if c.get("edge") == "1"]
        self.assertEqual(edge_cells[0].get("parent"), "1")

    def test_simple_edge_with_layer(self):
        D = Diagram(800, 600, 100, 300)
        D.simple_edge("a", "b", "Link", "strokeColor=#000;", layer="Mgmt")
        edge_cells = [c for c in D.R.findall("mxCell") if c.get("edge") == "1"]
        parent = edge_cells[0].get("parent")
        self.assertNotEqual(parent, "1")
        layer_cell = [c for c in D.R.findall("mxCell") if c.get("id") == parent]
        self.assertEqual(layer_cell[0].get("value"), "Mgmt")

    def test_simple_edge_without_layer(self):
        D = Diagram(800, 600, 100, 300)
        D.simple_edge("a", "b", "Link", "strokeColor=#000;")
        edge_cells = [c for c in D.R.findall("mxCell") if c.get("edge") == "1"]
        self.assertEqual(edge_cells[0].get("parent"), "1")

    def test_mixed_layers_and_default(self):
        D = Diagram(800, 600, 100, 300)
        D.add_edge(10, 50, 200, 400, "s1", "t1", EDGE_BLUE, layer="iSCSI")
        D.add_edge(50, 50, 250, 400, "s2", "t2", EDGE_BLUE)
        D.add_edge(90, 50, 300, 400, "s3", "t3", EDGE_BLUE, layer="NFS")
        D.flush_edges()
        edge_cells = [c for c in D.R.findall("mxCell") if c.get("edge") == "1"]
        self.assertEqual(len(edge_cells), 3)
        parents = {c.get("parent") for c in edge_cells}
        # Should have 3 distinct parents: "1", layer_iSCSI, layer_NFS
        self.assertEqual(len(parents), 3)
        self.assertIn("1", parents)


class TestDevice3Level(unittest.TestCase):

    def setUp(self):
        reset_ids()

    def test_3level_returns_all_ports(self):
        D = Diagram(800, 600, 100, 300)
        controllers = [
            ("Controller A", [
                ("iSCSI", [("e0a", "p1", False, PORT_GREEN),
                           ("e0b", "p2", False, PORT_GREEN)]),
                ("Mgmt",  [("e0M", "p3", False, PORT_GRAY)]),
            ]),
            ("Controller B", [
                ("iSCSI", [("e0a", "p4", False, PORT_GREEN)]),
            ]),
        ]
        result = D.device_carded("stor1", "NetApp", 10, 20, BG_BLUE,
                                 controllers=controllers)
        # Controller B's e0a overwrites Controller A's e0a (last wins, same key)
        self.assertIn("e0a", result)
        self.assertIn("e0b", result)
        self.assertIn("e0M", result)
        self.assertEqual(len(result), 3)

    def test_3level_xml_structure(self):
        """3-level device: chassis → ctrl → card → port hierarchy."""
        D = Diagram(800, 600, 100, 300)
        controllers = [
            ("Ctrl-A", [
                ("NIC", [("eth0", "pa1", False, PORT_GREEN)]),
            ]),
        ]
        D.device_carded("dev1", "Device", 0, 0, BG_BLUE,
                         controllers=controllers)
        cells = D.R.findall("mxCell")
        # 2 root + 1 device + 1 ctrl + 1 card + 1 port = 6
        self.assertEqual(len(cells), 6)
        # device parent = "1"
        dev_cell = [c for c in cells if c.get("id") == "dev1"][0]
        self.assertEqual(dev_cell.get("parent"), "1")
        # ctrl parent = device
        ctrl_cell = [c for c in cells if "ctrl" in (c.get("id") or "")][0]
        self.assertEqual(ctrl_cell.get("parent"), "dev1")
        # card parent = ctrl
        card_cell = [c for c in cells if "card" in (c.get("id") or "")][0]
        self.assertEqual(card_cell.get("parent"), ctrl_cell.get("id"))
        # port parent = card
        port_cell = [c for c in cells if c.get("id") == "pa1"][0]
        self.assertEqual(port_cell.get("parent"), card_cell.get("id"))

    def test_3level_device_box_registered(self):
        D = Diagram(800, 600, 100, 300)
        controllers = [
            ("Ctrl-A", [("NIC", [("eth0", "pa1", False, PORT_GREEN)])]),
        ]
        D.device_carded("dev1", "Device", 50, 100, BG_BLUE,
                         controllers=controllers)
        self.assertEqual(len(D._device_boxes), 1)
        bx, by, bw, bh = D._device_boxes[0]
        self.assertEqual(bx, 50)
        self.assertEqual(by, 100)
        self.assertGreater(bw, 0)
        self.assertGreater(bh, 0)

    def test_3level_abs_coordinates(self):
        """Port absolute coordinates should be within device bounds."""
        D = Diagram(800, 600, 100, 300)
        controllers = [
            ("Ctrl-A", [("NIC", [("eth0", "pa1", False, PORT_GREEN)])]),
        ]
        result = D.device_carded("dev1", "Device", 50, 100, BG_BLUE,
                                  controllers=controllers)
        _, cx, cy = result["eth0"]
        bx, by, bw, bh = D._device_boxes[0]
        self.assertGreaterEqual(cx, bx)
        self.assertLessEqual(cx, bx + bw)
        self.assertGreaterEqual(cy, by)
        self.assertLessEqual(cy, by + bh)


class TestTopologyCableLayers(unittest.TestCase):

    def setUp(self):
        reset_ids()

    def _make_topology(self):
        from wiring_diagram import Topology
        T = Topology()
        T.add_device("sw1", label="Switch-1", style=BG_BLUE, layer=0,
                     ports=[("d1", PORT_BLUE), ("d2", PORT_BLUE)])
        T.add_device("srv1", label="Server-1", style=BG_BLUE, layer=1,
                     ports=[("u1", PORT_BLUE), ("u2", PORT_BLUE)])
        T.add_device("srv2", label="Server-2", style=BG_BLUE, layer=1,
                     ports=[("u1", PORT_BLUE)])
        return T

    def test_cable_layers_false_default_parent(self):
        T = self._make_topology()
        T.add_cable("sw1", "d1", "srv1", "u1", style=EDGE_BLUE)
        D = T.to_diagram(cable_layers=False)
        D.flush_edges()
        edge_cells = [c for c in D.R.findall("mxCell") if c.get("edge") == "1"]
        for c in edge_cells:
            self.assertEqual(c.get("parent"), "1")

    def test_cable_layers_true_auto_assigns(self):
        T = self._make_topology()
        T.add_cable("sw1", "d1", "srv1", "u1", style=EDGE_BLUE)
        T.add_cable("sw1", "d2", "srv2", "u1", style=EDGE_BLUE)
        D = T.to_diagram(cable_layers=True)
        D.flush_edges()
        edge_cells = [c for c in D.R.findall("mxCell") if c.get("edge") == "1"]
        parents = {c.get("parent") for c in edge_cells}
        # No edge should use default layer "1"
        self.assertNotIn("1", parents)
        # Two different layer parents (Server-1, Server-2)
        self.assertEqual(len(parents), 2)

    def test_manual_layer_overrides_auto(self):
        T = self._make_topology()
        T.add_cable("sw1", "d1", "srv1", "u1", style=EDGE_BLUE,
                    layer="Custom")
        D = T.to_diagram(cable_layers=True)
        D.flush_edges()
        edge_cells = [c for c in D.R.findall("mxCell") if c.get("edge") == "1"]
        parent = edge_cells[0].get("parent")
        layer_cell = [c for c in D.R.findall("mxCell") if c.get("id") == parent]
        self.assertEqual(layer_cell[0].get("value"), "Custom")

    def test_auto_layer_picks_lower_device(self):
        """Auto layer should use the device with higher layer index."""
        T = self._make_topology()
        T.add_cable("sw1", "d1", "srv1", "u1", style=EDGE_BLUE)
        D = T.to_diagram(cable_layers=True)
        D.flush_edges()
        edge_cells = [c for c in D.R.findall("mxCell") if c.get("edge") == "1"]
        parent = edge_cells[0].get("parent")
        layer_cell = [c for c in D.R.findall("mxCell") if c.get("id") == parent]
        self.assertEqual(layer_cell[0].get("value"), "Server-1")

    def test_same_layer_picks_alpha_later(self):
        """Same layer index: pick alphabetically later label."""
        from wiring_diagram import Topology
        T = Topology()
        T.add_device("a", label="Alpha", style=BG_BLUE, layer=0,
                     ports=[("p1", PORT_BLUE)])
        T.add_device("b", label="Beta", style=BG_BLUE, layer=0,
                     ports=[("p1", PORT_BLUE)])
        T.add_cable("a", "p1", "b", "p1", style=EDGE_BLUE)
        D = T.to_diagram(cable_layers=True)
        D.flush_edges()
        edge_cells = [c for c in D.R.findall("mxCell") if c.get("edge") == "1"]
        parent = edge_cells[0].get("parent")
        layer_cell = [c for c in D.R.findall("mxCell") if c.get("id") == parent]
        self.assertEqual(layer_cell[0].get("value"), "Beta")


if __name__ == "__main__":
    unittest.main()
