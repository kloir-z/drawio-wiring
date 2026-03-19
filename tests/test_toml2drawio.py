"""Tests for tools/toml2drawio.py TOML → .drawio converter."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

import toml2drawio  # noqa: E402


class TestStyleResolvers(unittest.TestCase):
    """Test style resolution helpers."""

    def test_build_edge_style_solid(self):
        style = toml2drawio._build_edge_style(
            {"color": "red", "width": 3})
        self.assertIn("strokeColor=#E03030", style)
        self.assertIn("strokeWidth=3", style)
        self.assertNotIn("dashed", style)

    def test_build_edge_style_dotted(self):
        style = toml2drawio._build_edge_style(
            {"color": "blue", "width": 1.5, "line": "dotted"})
        self.assertIn("dashed=1", style)

    def test_build_port_style(self):
        style = toml2drawio._build_port_style({"color": "green"})
        self.assertIn("fillColor=#d5e8d4", style)

    def test_build_port_style_bold(self):
        style = toml2drawio._build_port_style(
            {"color": "navy", "bold": True})
        self.assertIn("fontStyle=1", style)

    def test_raw_passthrough_edge(self):
        raw = "strokeColor=#123456;strokeWidth=5;"
        self.assertEqual(toml2drawio._build_edge_style(raw), raw)

    def test_resolve_bg_valid(self):
        self.assertIn("fillColor=", toml2drawio._resolve_bg("yellow"))

    def test_resolve_bg_raw(self):
        raw = "fillColor=#aabbcc;strokeColor=#112233;"
        self.assertEqual(toml2drawio._resolve_bg(raw), raw)

    def test_resolve_bg_invalid(self):
        with self.assertRaises(KeyError):
            toml2drawio._resolve_bg("neon")


class TestBuildTopology(unittest.TestCase):
    """Test build_topology with minimal TOML data."""

    def _minimal_data(self):
        return {
            "settings": {"router": "naive"},
            "edge_styles": {
                "link": {"color": "blue", "width": 2},
            },
            "port_styles": {
                "p": {"color": "blue"},
            },
            "devices": [
                {"id": "sw1", "label": "SW-1", "layer": 0,
                 "style": "yellow",
                 "ports": [{"name": "d1", "style": "p"}]},
                {"id": "srv1", "label": "SRV-1", "layer": 1,
                 "style": "blue",
                 "cards": [
                     {"name": "NIC", "ports": [
                         {"name": "eth0", "style": "p"},
                     ]},
                 ]},
            ],
            "cables": [
                {"src": "sw1.d1", "dst": "srv1.eth0", "style": "link"},
            ],
        }

    def test_topology_devices(self):
        T, settings, _ = toml2drawio.build_topology(self._minimal_data())
        self.assertIn("sw1", T.devices)
        self.assertIn("srv1", T.devices)
        self.assertFalse(T.devices["sw1"].is_carded)
        self.assertTrue(T.devices["srv1"].is_carded)

    def test_topology_cables(self):
        T, _, _ = toml2drawio.build_topology(self._minimal_data())
        self.assertEqual(len(T.cables), 1)
        self.assertEqual(T.cables[0].src_device, "sw1")
        self.assertEqual(T.cables[0].dst_port, "eth0")

    def test_bulk_cables(self):
        data = self._minimal_data()
        # Add extra ports
        data["devices"][0]["ports"] = [
            {"name": "d1", "style": "p"},
            {"name": "d2", "style": "p"},
        ]
        data["devices"][1]["cards"][0]["ports"] = [
            {"name": "eth0", "style": "p"},
            {"name": "eth1", "style": "p"},
        ]
        data["cables"] = [
            {"src": ["sw1.d1", "sw1.d2"],
             "dst": ["srv1.eth0", "srv1.eth1"],
             "style": "link"},
        ]
        T, _, _ = toml2drawio.build_topology(data)
        self.assertEqual(len(T.cables), 2)

    def test_simple_links(self):
        data = self._minimal_data()
        data["devices"].append(
            {"id": "sw2", "label": "SW-2", "layer": 0,
             "style": "yellow",
             "ports": [{"name": "d1", "style": "p"}]})
        data["simple_links"] = [
            {"devices": ["sw1", "sw2"], "label": "Stack",
             "style": "link"},
        ]
        T, _, _ = toml2drawio.build_topology(data)
        self.assertEqual(len(T.simple_links), 1)

    def test_controllers_3level(self):
        data = self._minimal_data()
        data["devices"].append(
            {"id": "stor1", "label": "Storage", "layer": 2,
             "style": "blue",
             "controllers": [
                 {"name": "Ctrl-A", "cards": [
                     {"name": "iSCSI", "ports": [
                         {"name": "e0a", "style": "p"},
                     ]},
                 ]},
             ]})
        T, _, _ = toml2drawio.build_topology(data)
        self.assertTrue(T.devices["stor1"].is_3level)

    def test_mismatched_bulk_length(self):
        data = self._minimal_data()
        data["cables"] = [
            {"src": ["sw1.d1", "sw1.d1"],
             "dst": ["srv1.eth0"],
             "style": "link"},
        ]
        with self.assertRaises(ValueError):
            toml2drawio.build_topology(data)


class TestEndToEnd(unittest.TestCase):
    """Test full conversion pipeline."""

    def test_minimal_convert(self):
        toml_content = b"""\
[settings]
router = "naive"

[edge_styles]
link = { color = "blue", width = 2 }

[port_styles]
p = { color = "blue" }

[[devices]]
id = "sw1"
label = "Switch"
layer = 0
style = "green"
ports = [{ name = "d1", style = "p" }]

[[devices]]
id = "srv1"
label = "Server"
layer = 1
style = "blue"
[[devices.cards]]
name = "NIC"
ports = [{ name = "eth0", style = "p" }]

[[cables]]
src = "sw1.d1"
dst = "srv1.eth0"
style = "link"
"""
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
            f.write(toml_content)
            toml_path = f.name
        try:
            out_path = toml2drawio.convert(toml_path)
            self.assertTrue(os.path.exists(out_path))
            with open(out_path) as fout:
                xml = fout.read()
            self.assertIn("<mxGraphModel", xml)
            self.assertIn("Switch", xml)
            self.assertIn("Server", xml)
        finally:
            os.unlink(toml_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_datacenter_toml(self):
        """Ensure the full datacenter.toml example converts without error."""
        toml_path = os.path.join(os.path.dirname(__file__),
                                 '..', 'examples', 'datacenter.toml')
        if not os.path.exists(toml_path):
            self.skipTest("datacenter.toml not found")
        with tempfile.NamedTemporaryFile(suffix=".drawio", delete=False) as f:
            out_path = f.name
        try:
            toml2drawio.convert(toml_path, out_path)
            with open(out_path) as fout:
                xml = fout.read()
            self.assertIn("<mxGraphModel", xml)
            self.assertIn("Core-SW-1", xml)
            self.assertIn("Storage-A", xml)
            self.assertIn("VM-Host-3", xml)
        finally:
            os.unlink(out_path)


if __name__ == "__main__":
    unittest.main()
