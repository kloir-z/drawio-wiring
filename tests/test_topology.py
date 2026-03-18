"""Tests for Topology graph model and auto-layout."""

import sys
import unittest

sys.path.insert(0, '/home/user/code/drawio_infra_py/lib')

from wiring_diagram import (
    Topology, Diagram, reset_ids,
    BG_YELLOW, BG_GREEN, BG_BLUE, PORT_BLUE, EDGE_BLUE,
)


class TestTopologyBasic(unittest.TestCase):

    def setUp(self):
        reset_ids()

    def test_add_flat_device(self):
        T = Topology()
        T.add_device("sw1", label="Switch", style=BG_YELLOW, layer=0,
                     ports=[("p1", PORT_BLUE), ("p2", PORT_BLUE)])
        self.assertIn("sw1", T.devices)
        self.assertEqual(len(T.devices["sw1"].ports), 2)
        self.assertFalse(T.devices["sw1"].is_carded)

    def test_add_carded_device(self):
        T = Topology()
        T.add_device("srv1", label="Server", style=BG_BLUE, layer=1,
                     cards=[
                         ("NIC", [("eth0", True, PORT_BLUE),
                                  ("eth1", False, PORT_BLUE)]),
                     ])
        self.assertIn("srv1", T.devices)
        self.assertTrue(T.devices["srv1"].is_carded)
        self.assertEqual(T.devices["srv1"].port_labels, ["eth0", "eth1"])

    def test_ports_and_cards_mutual_exclusion(self):
        T = Topology()
        with self.assertRaises(ValueError):
            T.add_device("bad", label="Bad", style=BG_BLUE,
                         ports=[("p1", PORT_BLUE)],
                         cards=[("NIC", [("e0", False, PORT_BLUE)])])

    def test_add_cable(self):
        T = Topology()
        T.add_device("sw1", label="SW", style=BG_YELLOW, layer=0,
                     ports=[("p1", PORT_BLUE)])
        T.add_device("srv1", label="SRV", style=BG_BLUE, layer=1,
                     ports=[("p1", PORT_BLUE)])
        T.add_cable("sw1", "p1", "srv1", "p1", style=EDGE_BLUE)
        self.assertEqual(len(T.cables), 1)


class TestTopologyToDiagram(unittest.TestCase):

    def setUp(self):
        reset_ids()

    def _make_simple_topology(self):
        T = Topology()
        T.add_device("sw1", label="Switch-1", style=BG_YELLOW, layer=0,
                     ports=[("1/0/1", PORT_BLUE), ("1/0/2", PORT_BLUE)])
        T.add_device("sw2", label="Switch-2", style=BG_YELLOW, layer=0,
                     ports=[("1/0/1", PORT_BLUE)])
        T.add_device("srv1", label="Server-1", style=BG_BLUE, layer=1,
                     cards=[
                         ("NIC", [("eth0", True, PORT_BLUE),
                                  ("eth1", False, PORT_BLUE)]),
                     ])
        T.add_cable("sw1", "1/0/1", "srv1", "eth0", style=EDGE_BLUE)
        T.add_cable("sw2", "1/0/1", "srv1", "eth1", style=EDGE_BLUE)
        return T

    def test_to_diagram_returns_diagram(self):
        T = self._make_simple_topology()
        D = T.to_diagram()
        self.assertIsInstance(D, Diagram)

    def test_to_diagram_has_edges(self):
        T = self._make_simple_topology()
        D = T.to_diagram()
        D.flush_edges()
        edge_cells = [c for c in D.R.findall("mxCell") if c.get("edge") == "1"]
        self.assertEqual(len(edge_cells), 2)

    def test_to_diagram_saves_valid_xml(self):
        T = self._make_simple_topology()
        D = T.to_diagram()
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".drawio", delete=False) as f:
            path = f.name
        try:
            D.save(path)
            import xml.etree.ElementTree as ET
            tree = ET.parse(path)
            self.assertEqual(tree.getroot().tag, "mxfile")
        finally:
            os.unlink(path)


class TestThreeTierTopology(unittest.TestCase):

    def setUp(self):
        reset_ids()

    def test_three_layer_layout(self):
        T = Topology()
        T.add_device("core", label="Core", style=BG_YELLOW, layer=0,
                     ports=[("p1", PORT_BLUE), ("p2", PORT_BLUE)])
        T.add_device("dist1", label="Dist-1", style=BG_GREEN, layer=1,
                     ports=[("p1", PORT_BLUE), ("p2", PORT_BLUE)])
        T.add_device("dist2", label="Dist-2", style=BG_GREEN, layer=1,
                     ports=[("p1", PORT_BLUE)])
        T.add_device("acc1", label="Access-1", style=BG_BLUE, layer=2,
                     ports=[("p1", PORT_BLUE)])
        T.add_device("acc2", label="Access-2", style=BG_BLUE, layer=2,
                     ports=[("p1", PORT_BLUE)])

        T.add_cable("core", "p1", "dist1", "p1", style=EDGE_BLUE)
        T.add_cable("core", "p2", "dist2", "p1", style=EDGE_BLUE)
        T.add_cable("dist1", "p2", "acc1", "p1", style=EDGE_BLUE)
        T.add_cable("dist2", "p1", "acc2", "p1", style=EDGE_BLUE)  # reuse port — fixed below

        D = T.to_diagram()
        D.flush_edges()
        edge_cells = [c for c in D.R.findall("mxCell") if c.get("edge") == "1"]
        # Should have 4 routed edges
        self.assertEqual(len(edge_cells), 4)

    def test_auto_layer_assignment(self):
        """Devices without explicit layer should be auto-assigned."""
        T = Topology()
        T.add_device("core", label="Core", style=BG_YELLOW, layer=0,
                     ports=[("p1", PORT_BLUE)])
        T.add_device("sw", label="Switch", style=BG_GREEN,
                     ports=[("p1", PORT_BLUE), ("p2", PORT_BLUE)])
        T.add_device("srv", label="Server", style=BG_BLUE,
                     ports=[("p1", PORT_BLUE)])

        T.add_cable("core", "p1", "sw", "p1", style=EDGE_BLUE)
        T.add_cable("sw", "p2", "srv", "p1", style=EDGE_BLUE)

        D = T.to_diagram()
        # sw should be layer 1, srv should be layer 2
        self.assertEqual(T.devices["sw"].layer, 1)
        self.assertEqual(T.devices["srv"].layer, 2)

    def test_simple_link(self):
        T = Topology()
        T.add_device("sw1", label="SW-1", style=BG_YELLOW, layer=0,
                     ports=[("p1", PORT_BLUE)])
        T.add_device("sw2", label="SW-2", style=BG_YELLOW, layer=0,
                     ports=[("p1", PORT_BLUE)])
        T.add_simple_link("sw1", "sw2", "StackWise", "strokeColor=#888;")

        D = T.to_diagram()
        edge_cells = [c for c in D.R.findall("mxCell") if c.get("edge") == "1"]
        self.assertEqual(len(edge_cells), 1)


if __name__ == "__main__":
    unittest.main()
