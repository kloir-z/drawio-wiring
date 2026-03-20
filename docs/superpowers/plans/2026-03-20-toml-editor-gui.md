# TOML Editor GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Flask-based web GUI for creating and editing TOML wiring diagram definitions, with validation, drawio conversion, and PNG preview.

**Architecture:** Flask server (`tools/web/`) serves a single-page tab-based form editor. Browser sends JSON to stateless API endpoints. Server uses custom TOML serializer and reuses existing `toml2drawio.py` conversion pipeline. No frontend build tools.

**Tech Stack:** Python 3.11, Flask, vanilla JS, Jinja2, existing `lib/wiring_diagram/` + `tools/toml2drawio.py`

**Spec:** `docs/superpowers/specs/2026-03-20-toml-editor-gui-design.md`

---

## File Map

| File | Responsibility | Status |
|------|---------------|--------|
| `tools/web/app.py` | Flask app: routes, API endpoints | Create |
| `tools/web/toml_writer.py` | Dict → TOML string serializer | Create |
| `tools/web/validator.py` | Validation rules (reusable) | Create |
| `tools/web/templates/editor.html` | Main page template (tabs, forms) | Create |
| `tools/web/static/style.css` | All styling | Create |
| `tools/web/static/editor.js` | Tab switching, table CRUD, API calls | Create |
| `tests/test_toml_writer.py` | Tests for TOML serializer | Create |
| `tests/test_validator.py` | Tests for validation rules | Create |
| `tests/test_web_app.py` | Tests for Flask API endpoints | Create |

---

### Task 1: TOML Writer (Custom Serializer)

**Files:**
- Create: `tools/web/toml_writer.py`
- Create: `tests/test_toml_writer.py`

This is the foundation — everything else needs it for TOML output.

- [ ] **Step 1: Write failing test for settings serialization**

```python
# tests/test_toml_writer.py
import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools', 'web'))
from toml_writer import dict_to_toml

class TestTomlWriter(unittest.TestCase):

    def test_settings_section(self):
        data = {
            "settings": {
                "router": "obstacle",
                "layer_gap": 120,
                "device_gap": 25,
                "cable_layers": True,
            }
        }
        result = dict_to_toml(data)
        self.assertIn('[settings]', result)
        self.assertIn('router = "obstacle"', result)
        self.assertIn('layer_gap = 120', result)
        self.assertIn('cable_layers = true', result)

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_toml_writer.py::TestTomlWriter::test_settings_section -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement minimal toml_writer with settings support**

```python
# tools/web/toml_writer.py
"""Custom TOML serializer for wiring diagram schema.

Converts a Python dict (matching the TOML editor's JSON schema)
to a TOML string. Only handles the known schema sections —
not a general-purpose TOML writer.
"""


def _format_value(v):
    """Format a Python value as a TOML value string."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        # Use integer repr if it's a whole number (e.g. 2.0 → 2)
        if v == int(v):
            return str(int(v))
        return str(v)
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, list):
        inner = ", ".join(_format_value(item) for item in v)
        return f"[{inner}]"
    raise TypeError(f"Unsupported TOML value type: {type(v)}")


def _write_settings(settings):
    """Serialize [settings] section."""
    if not settings:
        return ""
    lines = ["[settings]"]
    for key, val in settings.items():
        lines.append(f"{key} = {_format_value(val)}")
    return "\n".join(lines) + "\n"


def dict_to_toml(data):
    """Convert an editor data dict to a TOML string."""
    parts = []
    if "settings" in data:
        parts.append(_write_settings(data["settings"]))
    return "\n".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_toml_writer.py::TestTomlWriter::test_settings_section -v`
Expected: PASS

- [ ] **Step 5: Write failing test for edge_styles and port_styles**

```python
    def test_edge_styles_section(self):
        data = {
            "edge_styles": {
                "core": {"color": "red", "width": 3},
                "mgmt": {"color": "purple", "width": 1.5, "line": "dotted"},
                "stack": {"color": "gray", "width": 4, "line": "solid;double=1"},
            }
        }
        result = dict_to_toml(data)
        self.assertIn('[edge_styles]', result)
        self.assertIn('core', result)
        self.assertIn('color = "red"', result)
        self.assertIn('width = 3', result)
        self.assertIn('line = "dotted"', result)

    def test_port_styles_section(self):
        data = {
            "port_styles": {
                "up": {"color": "red"},
                "down": {"color": "blue", "bold": True},
            }
        }
        result = dict_to_toml(data)
        self.assertIn('[port_styles]', result)
        self.assertIn('up', result)
        self.assertIn('bold = true', result)
```

- [ ] **Step 6: Implement edge_styles and port_styles serialization**

Add to `toml_writer.py`:

```python
def _write_inline_table(d):
    """Format a dict as a TOML inline table: { key = val, ... }."""
    parts = []
    for k, v in d.items():
        parts.append(f"{k} = {_format_value(v)}")
    return "{ " + ", ".join(parts) + " }"


def _write_style_table(section_name, styles):
    """Serialize [edge_styles] or [port_styles]."""
    if not styles:
        return ""
    lines = [f"[{section_name}]"]
    for name, spec in styles.items():
        lines.append(f"{name} = {_write_inline_table(spec)}")
    return "\n".join(lines) + "\n"
```

Update `dict_to_toml` to call `_write_style_table` for `edge_styles` and `port_styles`.

- [ ] **Step 7: Run tests, verify pass**

Run: `python3 -m pytest tests/test_toml_writer.py -v`
Expected: All PASS

- [ ] **Step 8: Write failing test for devices (flat + carded)**

```python
    def test_flat_device(self):
        data = {
            "devices": [{
                "id": "core1", "label": "Core-SW-1", "layer": 0,
                "style": "purple",
                "ports": [
                    {"name": "d1", "style": "down"},
                    {"name": "d2", "style": "down"},
                ]
            }]
        }
        result = dict_to_toml(data)
        self.assertIn('[[devices]]', result)
        self.assertIn('id = "core1"', result)
        self.assertIn('{ name = "d1"', result)

    def test_carded_device(self):
        data = {
            "devices": [{
                "id": "srv1", "label": "Server-1", "layer": 2,
                "style": "blue",
                "cards": [{"name": "NIC1", "ports": [
                    {"name": "eth1", "style": "srv"},
                ]}]
            }]
        }
        result = dict_to_toml(data)
        self.assertIn('[[devices.cards]]', result)
        self.assertIn('name = "NIC1"', result)
```

- [ ] **Step 9: Implement devices serialization**

Add to `toml_writer.py`:

```python
def _write_port_inline(port):
    """Format a port as inline table."""
    parts = [f'name = "{port["name"]}"']
    if port.get("sfp"):
        parts.append("sfp = true")
    if "style" in port:
        parts.append(f'style = "{port["style"]}"')
    return "{ " + ", ".join(parts) + " }"


def _write_devices(devices):
    """Serialize [[devices]] array."""
    if not devices:
        return ""
    chunks = []
    for dev in devices:
        lines = ["[[devices]]"]
        lines.append(f'id = "{dev["id"]}"')
        if dev.get("label"):
            lines.append(f'label = "{dev["label"]}"')
        if dev.get("layer") is not None:
            lines.append(f'layer = {dev["layer"]}')
        if dev.get("style"):
            lines.append(f'style = "{dev["style"]}"')
        if dev.get("cable_side") and dev["cable_side"] != "top":
            lines.append(f'cable_side = "{dev["cable_side"]}"')

        if "controllers" in dev:
            for ctrl in dev["controllers"]:
                lines.append(f'[[devices.controllers]]')
                lines.append(f'name = "{ctrl["name"]}"')
                for card in ctrl["cards"]:
                    lines.append(f'[[devices.controllers.cards]]')
                    lines.append(f'name = "{card["name"]}"')
                    port_strs = [f"    {_write_port_inline(p)}," for p in card["ports"]]
                    lines.append(f'ports = [')
                    lines.extend(port_strs)
                    lines.append(f']')
        elif "cards" in dev:
            for card in dev["cards"]:
                lines.append(f'[[devices.cards]]')
                lines.append(f'name = "{card["name"]}"')
                port_strs = [f"    {_write_port_inline(p)}," for p in card["ports"]]
                lines.append(f'ports = [')
                lines.extend(port_strs)
                lines.append(f']')
        elif "ports" in dev:
            port_strs = [f"    {_write_port_inline(p)}," for p in dev["ports"]]
            lines.append(f'ports = [')
            lines.extend(port_strs)
            lines.append(f']')
        chunks.append("\n".join(lines))
    return "\n\n".join(chunks) + "\n"
```

- [ ] **Step 10: Run tests, verify pass**

Run: `python3 -m pytest tests/test_toml_writer.py -v`
Expected: All PASS

- [ ] **Step 11: Write failing test for cables, simple_links, zone_groups, legend**

```python
    def test_cables(self):
        data = {
            "cables": [{
                "src": ["core1.d1", "core1.d2"],
                "dst": ["acc1.u1", "acc2.u1"],
                "style": "uplink",
            }]
        }
        result = dict_to_toml(data)
        self.assertIn('[[cables]]', result)
        self.assertIn('src = ["core1.d1", "core1.d2"]', result)

    def test_cable_single_string(self):
        data = {
            "cables": [{
                "src": "core1.d1",
                "dst": "acc1.u1",
                "style": "uplink",
            }]
        }
        result = dict_to_toml(data)
        self.assertIn('src = "core1.d1"', result)

    def test_simple_links(self):
        data = {
            "simple_links": [{
                "devices": ["core1", "core2"],
                "label": "",
                "style": "stack",
            }]
        }
        result = dict_to_toml(data)
        self.assertIn('[[simple_links]]', result)
        self.assertIn('devices = ["core1", "core2"]', result)

    def test_zone_groups(self):
        data = {
            "zone_groups": [{
                "layers": [0, 1],
                "groups": [["core"], ["core2"]],
            }]
        }
        result = dict_to_toml(data)
        self.assertIn('[[zone_groups]]', result)
        self.assertIn('layers = [0, 1]', result)

    def test_legend(self):
        data = {
            "legend": [
                {"label": "Core (1系)", "style": "core"},
            ]
        }
        result = dict_to_toml(data)
        self.assertIn('[[legend]]', result)
        self.assertIn('label = "Core (1系)"', result)
```

- [ ] **Step 12: Implement cables, simple_links, zone_groups, legend serialization**

Add the corresponding `_write_*` functions and wire them into `dict_to_toml`.

- [ ] **Step 13: Run all tests, verify pass**

Run: `python3 -m pytest tests/test_toml_writer.py -v`
Expected: All PASS

- [ ] **Step 14: Write failing test for unknown field preservation**

```python
    def test_unknown_fields_preserved(self):
        """Unknown top-level and per-device fields should be passed through."""
        data = {
            "settings": {"router": "obstacle"},
            "custom_section": {"foo": "bar"},  # unknown top-level
            "devices": [{
                "id": "d1", "layer": 0, "ports": [],
                "custom_field": "preserved",  # unknown device field
            }],
        }
        result = dict_to_toml(data)
        # Unknown fields should appear as comments or pass-through
        # At minimum, round-trip should not lose them
        self.assertIn("custom_field", result)
```

- [ ] **Step 15: Implement unknown field preservation in toml_writer**

In `dict_to_toml()`, after writing known sections, iterate remaining keys in the dict and write them as-is. For devices, after writing known fields, write any extra keys as `key = value` lines.

Known top-level keys: `settings`, `edge_styles`, `port_styles`, `devices`, `cables`, `simple_links`, `zone_groups`, `legend`. Anything else is unknown and gets serialized generically.

- [ ] **Step 16: Run tests, verify pass**

Run: `python3 -m pytest tests/test_toml_writer.py -v`
Expected: All PASS

- [ ] **Step 17: Write round-trip test (parse existing TOML → dict → serialize → parse again)**

```python
    def test_round_trip_small_office(self):
        """Parse small_office.toml, serialize back, parse again, compare."""
        import tomllib
        toml_path = os.path.join(os.path.dirname(__file__),
                                 '..', 'examples', 'small_office.toml')
        with open(toml_path, 'rb') as f:
            original = tomllib.load(f)
        toml_str = dict_to_toml(original)
        reparsed = tomllib.loads(toml_str)
        # Compare key structures
        self.assertEqual(set(original.keys()), set(reparsed.keys()))
        self.assertEqual(len(original.get("devices", [])),
                         len(reparsed.get("devices", [])))
        self.assertEqual(len(original.get("cables", [])),
                         len(reparsed.get("cables", [])))
```

- [ ] **Step 18: Fix any round-trip issues, run tests, verify pass**

Run: `python3 -m pytest tests/test_toml_writer.py -v`
Expected: All PASS

- [ ] **Step 19: Commit**

```bash
git add tools/web/toml_writer.py tests/test_toml_writer.py
git commit -m "feat: add custom TOML serializer for editor GUI"
```

---

### Task 2: Validator

**Files:**
- Create: `tools/web/validator.py`
- Create: `tests/test_validator.py`

- [ ] **Step 1: Write failing test for required field validation**

```python
# tests/test_validator.py
import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools', 'web'))
from validator import validate

class TestValidator(unittest.TestCase):

    def test_empty_data_has_no_errors(self):
        """Empty diagram is valid (no devices = nothing to validate)."""
        errors = validate({})
        self.assertEqual(errors, [])

    def test_device_missing_id(self):
        data = {"devices": [{"label": "X", "layer": 0, "ports": []}]}
        errors = validate(data)
        self.assertTrue(any("id" in e["message"] for e in errors))

    def test_device_missing_layer(self):
        data = {"devices": [{"id": "d1", "ports": []}]}
        errors = validate(data)
        self.assertTrue(any("layer" in e["message"] for e in errors))

    def test_duplicate_device_id(self):
        data = {"devices": [
            {"id": "d1", "layer": 0, "ports": []},
            {"id": "d1", "layer": 1, "ports": []},
        ]}
        errors = validate(data)
        self.assertTrue(any("重複" in e["message"] for e in errors))

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_validator.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement validator with device validation**

```python
# tools/web/validator.py
"""Validation rules for TOML wiring diagram editor data.

Each rule function takes the full data dict and returns a list
of error dicts: {"tab": str, "field": str, "index": int|None, "message": str}
"""

_VALID_BG = {"yellow", "green", "purple", "red", "blue", "gray"}
_VALID_CABLE_SIDE = {"top", "bottom"}
_VALID_ROUTERS = {"naive", "left-edge", "obstacle"}


def _validate_devices(data):
    errors = []
    devices = data.get("devices", [])
    seen_ids = set()
    for i, dev in enumerate(devices):
        if not dev.get("id"):
            errors.append({"tab": "devices", "field": "id",
                           "index": i, "message": f"デバイス {i+1}: id は必須です"})
        else:
            if dev["id"] in seen_ids:
                errors.append({"tab": "devices", "field": "id",
                               "index": i,
                               "message": f"デバイス {i+1}: id '{dev['id']}' が重複しています"})
            seen_ids.add(dev["id"])

        if dev.get("layer") is None:
            errors.append({"tab": "devices", "field": "layer",
                           "index": i, "message": f"デバイス {i+1}: layer は必須です"})
        elif not isinstance(dev.get("layer"), int):
            errors.append({"tab": "devices", "field": "layer",
                           "index": i, "message": f"デバイス {i+1}: layer は整数にしてください"})

        cs = dev.get("cable_side", "top")
        if cs not in _VALID_CABLE_SIDE:
            errors.append({"tab": "devices", "field": "cable_side",
                           "index": i,
                           "message": f"デバイス {i+1}: cable_side は top/bottom のいずれかです"})

        # Must have one of ports/cards/controllers
        has_structure = any(k in dev for k in ("ports", "cards", "controllers"))
        if not has_structure:
            errors.append({"tab": "devices", "field": "ports",
                           "index": i,
                           "message": f"デバイス {i+1}: ports, cards, controllers のいずれかが必要です"})
    return errors


def validate(data):
    """Validate editor data dict. Returns list of error dicts."""
    errors = []
    errors.extend(_validate_devices(data))
    return errors
```

- [ ] **Step 4: Run tests, verify pass**

Run: `python3 -m pytest tests/test_validator.py -v`
Expected: All PASS

- [ ] **Step 5: Write failing tests for cable validation**

```python
    def test_cable_missing_style(self):
        data = {
            "devices": [{"id": "d1", "layer": 0, "ports": [{"name": "p1"}]}],
            "cables": [{"src": "d1.p1", "dst": "d1.p1"}],
        }
        errors = validate(data)
        self.assertTrue(any("style" in e["message"] for e in errors))

    def test_cable_invalid_device_ref(self):
        data = {
            "devices": [{"id": "d1", "layer": 0, "ports": [{"name": "p1"}]}],
            "edge_styles": {"s1": {"color": "red", "width": 2}},
            "cables": [{"src": "nonexist.p1", "dst": "d1.p1", "style": "s1"}],
        }
        errors = validate(data)
        self.assertTrue(any("nonexist" in e["message"] for e in errors))

    def test_cable_invalid_port_ref(self):
        data = {
            "devices": [{"id": "d1", "layer": 0, "ports": [{"name": "p1"}]}],
            "edge_styles": {"s1": {"color": "red", "width": 2}},
            "cables": [{"src": "d1.bad", "dst": "d1.p1", "style": "s1"}],
        }
        errors = validate(data)
        self.assertTrue(any("bad" in e["message"] for e in errors))

    def test_cable_undefined_style(self):
        data = {
            "devices": [{"id": "d1", "layer": 0, "ports": [{"name": "p1"}]}],
            "cables": [{"src": "d1.p1", "dst": "d1.p1", "style": "nope"}],
        }
        errors = validate(data)
        self.assertTrue(any("nope" in e["message"] for e in errors))
```

- [ ] **Step 6: Implement cable validation**

Add `_validate_cables(data)` function that:
- Builds a device→port lookup from devices (handle flat ports, cards, controllers)
- Checks src/dst format (`device.port`), device existence, port existence
- Checks style is defined in `edge_styles` or is a raw style (contains `=`)
- Handles both string and list src/dst

- [ ] **Step 7: Run tests, verify pass**

Run: `python3 -m pytest tests/test_validator.py -v`
Expected: All PASS

- [ ] **Step 8: Write failing tests for style and settings validation**

```python
    def test_edge_style_invalid_line(self):
        data = {
            "edge_styles": {"s1": {"color": "red", "width": 2, "line": "invalid"}},
        }
        errors = validate(data)
        self.assertTrue(any("line" in e["message"] for e in errors))

    def test_edge_style_line_with_extra_markers(self):
        """'solid;double=1' should pass — extra markers after ';' are free-form."""
        data = {
            "edge_styles": {"stack": {"color": "gray", "width": 4, "line": "solid;double=1"}},
        }
        errors = validate(data)
        line_errors = [e for e in errors if "line" in e.get("field", "")]
        self.assertEqual(line_errors, [])

    def test_settings_invalid_router(self):
        data = {"settings": {"router": "unknown"}}
        errors = validate(data)
        self.assertTrue(any("router" in e["message"] for e in errors))

    def test_settings_cable_layers_valid_values(self):
        for val in [True, "device", "style", False]:
            data = {"settings": {"cable_layers": val}}
            errors = validate(data)
            cl_errors = [e for e in errors if "cable_layers" in e.get("field", "")]
            self.assertEqual(cl_errors, [], f"cable_layers={val!r} should be valid")

    def test_settings_cable_layers_invalid(self):
        data = {"settings": {"cable_layers": "invalid"}}
        errors = validate(data)
        self.assertTrue(any("cable_layers" in e.get("field", "") for e in errors))

    def test_raw_edge_style_passthrough(self):
        """Raw style strings (containing '=') should pass validation."""
        data = {
            "edge_styles": {"custom": "strokeColor=#FF0000;strokeWidth=2;"},
        }
        errors = validate(data)
        style_errors = [e for e in errors if e.get("tab") == "edge_styles"]
        self.assertEqual(style_errors, [])

    def test_simple_link_needs_two_devices(self):
        data = {
            "devices": [{"id": "d1", "layer": 0, "ports": []}],
            "simple_links": [{"devices": ["d1"], "style": "s1"}],
        }
        errors = validate(data)
        self.assertTrue(any("2" in e["message"] for e in errors))
```

- [ ] **Step 9: Implement style, settings, simple_links, zone_groups validation**

Add `_validate_edge_styles`, `_validate_settings`, `_validate_simple_links`, `_validate_zone_groups` and wire into `validate()`.

Key implementation details:
- `_validate_edge_styles`: If a style value is a string containing `=`, it's a raw passthrough — skip field validation. Otherwise validate `color` in PALETTE, `line` base part (before `;`) in LINE_STYLES, `width` is numeric.
- `_validate_settings`: Validate `router` in `_VALID_ROUTERS`, `cable_layers` in `{True, False, "device", "style"}`, numeric fields are numbers.
- `_validate_simple_links`: `devices` has exactly 2 items, both exist in device IDs.
- `_validate_zone_groups`: `layers` has exactly 2 integers.

- [ ] **Step 10: Run all tests, verify pass**

Run: `python3 -m pytest tests/test_validator.py -v`
Expected: All PASS

- [ ] **Step 11: Commit**

```bash
git add tools/web/validator.py tests/test_validator.py
git commit -m "feat: add validation rules for TOML editor"
```

---

### Task 3: Flask App — Schema API + Basic Structure

**Files:**
- Create: `tools/web/app.py`
- Create: `tests/test_web_app.py`

- [ ] **Step 1: Write failing test for schema endpoint**

```python
# tests/test_web_app.py
import unittest
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools', 'web'))
from app import create_app

class TestWebApp(unittest.TestCase):

    def setUp(self):
        app = create_app()
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_schema_endpoint(self):
        resp = self.client.get('/api/schema')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('colors', data['data'])
        self.assertIn('line_styles', data['data'])
        self.assertIn('bg_styles', data['data'])
        self.assertIn('routers', data['data'])
        # Verify palette has 32 entries
        self.assertEqual(len(data['data']['colors']), 32)

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_web_app.py::TestWebApp::test_schema_endpoint -v`
Expected: FAIL

- [ ] **Step 3: Implement Flask app skeleton with schema endpoint**

```python
# tools/web/app.py
"""Flask web application for the TOML wiring diagram editor."""

import os
import sys

from flask import Flask, jsonify, request, render_template

# Resolve library paths
_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_TOOLS)
sys.path.insert(0, os.path.join(_ROOT, 'lib'))
sys.path.insert(0, _TOOLS)

from wiring_diagram.styles import PALETTE, LINE_STYLES


_BG_STYLES = ["yellow", "green", "purple", "red", "blue", "gray"]
_ROUTERS = ["naive", "left-edge", "obstacle"]


def create_app():
    app = Flask(__name__,
                template_folder=os.path.join(_HERE, 'templates'),
                static_folder=os.path.join(_HERE, 'static'))

    @app.route('/')
    def index():
        return render_template('editor.html')

    @app.route('/api/schema')
    def schema():
        colors = []
        for name, (stroke, fill, _) in PALETTE.items():
            colors.append({"name": name, "stroke": stroke, "fill": fill})
        return jsonify({
            "ok": True, "errors": [],
            "data": {
                "colors": colors,
                "line_styles": list(LINE_STYLES.keys()),
                "bg_styles": _BG_STYLES,
                "routers": _ROUTERS,
            }
        })

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
```

**Note on imports:** `app.py` adds both `lib/` and `tools/` to `sys.path`. This ensures:
- `from wiring_diagram.styles import PALETTE` works (via `lib/`)
- `from toml2drawio import build_topology` works (via `tools/`)
- `from validator import validate` works (via `tools/web/` — `app.py` runs from this dir)
- `toml2drawio.py` has its own `sys.path` manipulation that adds `lib/`, so the import chain resolves.

- [ ] **Step 4: Create minimal template so app doesn't crash**

Create `tools/web/templates/editor.html` with minimal HTML:
```html
<!DOCTYPE html>
<html><head><title>TOML Editor</title></head>
<body><h1>TOML Editor</h1></body></html>
```

- [ ] **Step 5: Run test, verify pass**

Run: `python3 -m pytest tests/test_web_app.py::TestWebApp::test_schema_endpoint -v`
Expected: PASS

- [ ] **Step 6: Write failing test for validate endpoint**

```python
    def test_validate_endpoint(self):
        resp = self.client.post('/api/validate',
            data=json.dumps({"devices": [{"label": "X"}]}),
            content_type='application/json')
        data = resp.get_json()
        self.assertFalse(data['ok'])
        self.assertTrue(len(data['errors']) > 0)

    def test_validate_valid_data(self):
        resp = self.client.post('/api/validate',
            data=json.dumps({"devices": [
                {"id": "d1", "layer": 0, "ports": [{"name": "p1"}]}
            ]}),
            content_type='application/json')
        data = resp.get_json()
        self.assertTrue(data['ok'])
```

- [ ] **Step 7: Implement validate endpoint**

Add to `app.py`:
```python
from validator import validate

@app.route('/api/validate', methods=['POST'])
def api_validate():
    data = request.get_json()
    errors = validate(data)
    return jsonify({"ok": len(errors) == 0, "errors": errors, "data": {}})
```

- [ ] **Step 8: Run tests, verify pass**

Run: `python3 -m pytest tests/test_web_app.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add tools/web/app.py tools/web/templates/editor.html tests/test_web_app.py
git commit -m "feat: add Flask app with schema and validate endpoints"
```

---

### Task 4: Generate + Upload + Preview Endpoints

**Files:**
- Modify: `tools/web/app.py`
- Modify: `tests/test_web_app.py`

- [ ] **Step 1: Write failing test for generate endpoint (TOML output)**

```python
    def test_generate_toml(self):
        data = {
            "settings": {"router": "obstacle"},
            "edge_styles": {"s1": {"color": "red", "width": 2}},
            "port_styles": {"up": {"color": "red"}},
            "devices": [
                {"id": "d1", "layer": 0, "style": "purple",
                 "ports": [{"name": "p1", "style": "up"}]},
            ],
            "cables": [],
        }
        resp = self.client.post('/api/generate',
            data=json.dumps({"data": data, "format": "toml"}),
            content_type='application/json')
        result = resp.get_json()
        self.assertTrue(result['ok'])
        self.assertIn('toml', result['data'])
        self.assertIn('[settings]', result['data']['toml'])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_web_app.py::TestWebApp::test_generate_toml -v`
Expected: FAIL

- [ ] **Step 3: Implement generate endpoint**

Add to `app.py`:
```python
import tempfile
from toml_writer import dict_to_toml
from toml2drawio import build_topology, topology_to_diagram

@app.route('/api/generate', methods=['POST'])
def api_generate():
    body = request.get_json()
    data = body.get('data', {})
    fmt = body.get('format', 'toml')

    # Validate first
    errors = validate(data)
    if errors:
        return jsonify({"ok": False, "errors": errors, "data": {}})

    toml_str = dict_to_toml(data)
    result = {"toml": toml_str}

    if fmt in ("drawio", "both"):
        try:
            T, settings, edge_styles, zg_config = build_topology(data)
            D = topology_to_diagram(T, settings, zone_groups=zg_config)
            if "legend" in data:
                from toml2drawio import _resolve_edge_style
                entries = []
                for entry in data["legend"]:
                    style = _resolve_edge_style(entry["style"], edge_styles)
                    entries.append((entry["label"], style))
                D.legend(entries)
            with tempfile.NamedTemporaryFile(suffix='.drawio', delete=False) as f:
                D.save(f.name)
                with open(f.name, 'r') as rf:
                    result["drawio"] = rf.read()
                os.unlink(f.name)
        except Exception as e:
            return jsonify({"ok": False,
                           "errors": [{"tab": "general", "field": "",
                                       "index": None, "message": str(e)}],
                           "data": {}})

    return jsonify({"ok": True, "errors": [], "data": result})
```

- [ ] **Step 4: Run test, verify pass**

Run: `python3 -m pytest tests/test_web_app.py::TestWebApp::test_generate_toml -v`
Expected: PASS

- [ ] **Step 5: Write failing test for upload endpoint**

```python
    def test_upload_toml(self):
        toml_content = b'[settings]\nrouter = "obstacle"\n\n[[devices]]\nid = "d1"\nlayer = 0\nports = []\n'
        from io import BytesIO
        resp = self.client.post('/upload',
            data={'file': (BytesIO(toml_content), 'test.toml')},
            content_type='multipart/form-data')
        result = resp.get_json()
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['settings']['router'], 'obstacle')
```

- [ ] **Step 6: Implement upload endpoint**

```python
import tomllib

@app.route('/upload', methods=['POST'])
def upload():
    f = request.files.get('file')
    if not f:
        return jsonify({"ok": False,
                       "errors": [{"tab": "general", "field": "",
                                   "index": None, "message": "ファイルが選択されていません"}],
                       "data": {}})
    try:
        data = tomllib.load(f)
    except Exception as e:
        return jsonify({"ok": False,
                       "errors": [{"tab": "general", "field": "",
                                   "index": None,
                                   "message": f"TOML パースエラー: {e}"}],
                       "data": {}})
    return jsonify({"ok": True, "errors": [], "data": data})
```

- [ ] **Step 7: Run tests, verify pass**

Run: `python3 -m pytest tests/test_web_app.py -v`
Expected: All PASS

- [ ] **Step 8: Write failing test for preview endpoint (error path)**

```python
    def test_preview_no_node(self):
        """Preview returns error when drawio_to_png.mjs subprocess fails."""
        data = {
            "settings": {"router": "obstacle"},
            "devices": [
                {"id": "d1", "layer": 0, "style": "purple",
                 "ports": [{"name": "p1"}]},
            ],
            "cables": [],
        }
        resp = self.client.post('/api/preview',
            data=json.dumps({"data": data}),
            content_type='application/json')
        result = resp.get_json()
        # Either succeeds with base64 PNG or fails gracefully with error message
        if not result['ok']:
            self.assertTrue(any(e["message"] for e in result['errors']))
        else:
            self.assertIn('png_base64', result['data'])
```

- [ ] **Step 9: Implement preview endpoint**

```python
import subprocess
import base64

@app.route('/api/preview', methods=['POST'])
def api_preview():
    body = request.get_json()
    data = body.get('data', {})

    # Validate first
    errors = validate(data)
    if errors:
        return jsonify({"ok": False, "errors": errors, "data": {}})

    # Generate drawio
    try:
        T, settings, edge_styles, zg_config = build_topology(data)
        D = topology_to_diagram(T, settings, zone_groups=zg_config)
        if "legend" in data:
            from toml2drawio import _resolve_edge_style
            entries = []
            for entry in data["legend"]:
                style = _resolve_edge_style(entry["style"], edge_styles)
                entries.append((entry["label"], style))
            D.legend(entries)
    except Exception as e:
        return jsonify({"ok": False,
                       "errors": [{"tab": "general", "field": "",
                                   "index": None, "message": str(e)}],
                       "data": {}})

    # Save drawio to temp file
    drawio_tmp = tempfile.NamedTemporaryFile(suffix='.drawio', delete=False)
    try:
        D.save(drawio_tmp.name)
        drawio_tmp.close()

        # Convert to PNG
        drawio_to_png = os.path.join(_TOOLS, 'drawio_to_png.mjs')
        png_path = drawio_tmp.name.replace('.drawio', '.png')

        result = subprocess.run(
            ['node', drawio_to_png, drawio_tmp.name],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return jsonify({"ok": False,
                           "errors": [{"tab": "general", "field": "",
                                       "index": None,
                                       "message": f"PNG変換エラー: {result.stderr}"}],
                           "data": {}})

        if not os.path.exists(png_path):
            return jsonify({"ok": False,
                           "errors": [{"tab": "general", "field": "",
                                       "index": None,
                                       "message": "PNGファイルが生成されませんでした"}],
                           "data": {}})

        with open(png_path, 'rb') as pf:
            png_b64 = base64.b64encode(pf.read()).decode('ascii')
        os.unlink(png_path)

        return jsonify({"ok": True, "errors": [],
                       "data": {"png_base64": png_b64}})
    finally:
        if os.path.exists(drawio_tmp.name):
            os.unlink(drawio_tmp.name)
```

- [ ] **Step 10: Run all tests, verify pass**

Run: `python3 -m pytest tests/test_web_app.py -v`
Expected: All PASS

- [ ] **Step 11: Commit**

```bash
git add tools/web/app.py tests/test_web_app.py
git commit -m "feat: add generate, upload, and preview endpoints"
```

---

### Task 5: Frontend — HTML Template + CSS + Tab Switching

**Files:**
- Create: `tools/web/templates/editor.html` (replace minimal placeholder)
- Create: `tools/web/static/style.css`
- Create: `tools/web/static/editor.js`

This task creates the full HTML structure and basic tab switching. No data manipulation yet.

**Frontend testing strategy:** Tasks 5-9 are manually tested (verify in browser). Automated frontend testing would require Selenium/Playwright which adds significant setup overhead to the RPi environment. The server-side API is fully tested via Flask test client, and the integration tests (Task 10) verify the full round-trip. Frontend logic bugs will be caught during manual smoke testing (Task 11).

- [ ] **Step 1: Create the full HTML template**

`tools/web/templates/editor.html` — structure:
- Top toolbar: New / Open / Save / Convert / Preview buttons
- Tab bar: Settings / Edge Styles / Port Styles / Devices / Cables / Legend
- Tab panels (one per tab, only active one visible)
- Bottom: TOML preview panel (toggleable)
- Bottom: PNG preview area

Each tab panel contains the appropriate form structure (tables, inputs) as described in the spec. Use `data-tab` attributes for JS tab switching.

- [ ] **Step 2: Create CSS**

`tools/web/static/style.css` — key rules:
- Tab bar styling (active tab highlighted)
- Table styling (striped rows, hover)
- Color chip display (small square next to dropdown)
- Error state (red border on `.field-error`)
- Badge on tab buttons (`.tab-badge`)
- TOML preview panel (collapsible, monospace)
- Responsive layout basics

- [ ] **Step 3: Create initial editor.js with tab switching and schema loading**

```javascript
// tools/web/static/editor.js
"use strict";

// -- State --
let schema = null;  // Loaded from /api/schema
let formData = {};  // Current form state

// -- Tab switching --
function switchTab(tabName) {
    document.querySelectorAll('.tab-panel').forEach(p => p.hidden = true);
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('panel-' + tabName).hidden = false;
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
}

// -- Schema loading --
async function loadSchema() {
    const resp = await fetch('/api/schema');
    const result = await resp.json();
    if (result.ok) {
        schema = result.data;
        populateDropdowns();
    }
}

function populateDropdowns() {
    // Populate all color/style/router dropdowns from schema
    // ...
}

// -- Init --
document.addEventListener('DOMContentLoaded', () => {
    loadSchema();
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });
    switchTab('settings');
});
```

- [ ] **Step 4: Verify manually — start Flask and open in browser**

Run: `python3 tools/web/app.py`
Open: `http://localhost:5000`
Verify: Tabs switch, basic layout renders, schema dropdown data loads.

- [ ] **Step 5: Commit**

```bash
git add tools/web/templates/editor.html tools/web/static/style.css tools/web/static/editor.js
git commit -m "feat: add editor HTML template, CSS, and tab switching JS"
```

---

### Task 6: Frontend — Settings + Edge Styles + Port Styles Tabs

**Files:**
- Modify: `tools/web/static/editor.js`
- Modify: `tools/web/templates/editor.html` (if needed)

- [ ] **Step 1: Implement Settings tab form binding**

JS functions to:
- Read/write Settings form fields (router dropdown, number inputs for layer_gap etc.)
- `getSettingsData()` → returns settings dict
- `setSettingsData(settings)` → populates form from dict

- [ ] **Step 2: Implement Edge Styles table CRUD**

JS functions to:
- Add row (name, color dropdown, width input, line dropdown, extra markers text)
- Delete selected rows
- `getEdgeStylesData()` / `setEdgeStylesData(styles)`
- Color dropdown shows color chip preview

- [ ] **Step 3: Implement Port Styles table CRUD**

JS functions to:
- Add row (name, color dropdown, bold checkbox)
- Delete selected rows
- `getPortStylesData()` / `setPortStylesData(styles)`

- [ ] **Step 4: Implement raw style passthrough UI**

For both Edge Styles and Port Styles:
- Add a "カスタム (raw)" option at the end of the color dropdown
- When selected, hide color/width/line fields and show a raw text input
- `getEdgeStylesData()` returns the raw string value instead of an object when raw mode is active
- `setEdgeStylesData()` detects raw styles (string containing `=`) and auto-enables raw mode
- Same pattern for Port Styles

- [ ] **Step 5: Verify manually**

Start Flask, test adding/deleting rows, verify dropdowns populate from schema. Test raw style input mode.

- [ ] **Step 6: Commit**

```bash
git add tools/web/static/editor.js tools/web/templates/editor.html
git commit -m "feat: implement Settings, Edge Styles, Port Styles tab logic"
```

---

### Task 7: Frontend — Devices Tab

**Files:**
- Modify: `tools/web/static/editor.js`

This is the most complex tab due to nested structures (flat/carded/3-level).

- [ ] **Step 1: Implement device list table**

JS functions to:
- Add device row (id, label, layer, BG style dropdown, type dropdown, cable_side dropdown)
- Delete device
- `getDevicesData()` / `setDevicesData(devices)`

- [ ] **Step 2: Implement expandable detail panel**

- Click device row → toggle detail panel below
- Type dropdown changes panel content

- [ ] **Step 3: Implement flat device port editor**

- Port table within detail panel (name input, style dropdown)
- Add/delete port rows

- [ ] **Step 4: Implement carded device editor**

- Card table (name input) + nested port table per card
- Add/delete cards, add/delete ports within cards
- Port rows include: name, sfp checkbox, style dropdown

- [ ] **Step 5: Implement 3-level (controllers) device editor**

- Controller table → Card table → Port table
- Same nesting pattern as carded but one level deeper

- [ ] **Step 6: Verify manually**

Test all three device types, add/delete at each nesting level.

- [ ] **Step 7: Commit**

```bash
git add tools/web/static/editor.js
git commit -m "feat: implement Devices tab with flat/carded/3-level support"
```

---

### Task 8: Frontend — Cables + Legend Tabs

**Files:**
- Modify: `tools/web/static/editor.js`

- [ ] **Step 1: Implement Cables table**

- Add cable row with 2-stage dropdown (device → port) for src/dst
- Style dropdown populated from defined edge_styles
- Bulk mode: multiple src/dst pairs per cable
- Optional: label, zone text fields

- [ ] **Step 2: Implement Simple Links sub-section**

- Toggle to show/hide
- Two device ID dropdowns + label + style + zone

- [ ] **Step 3: Implement Zone Groups sub-section**

- Layer pair inputs + group array editor
- Groups selectable from defined edge_style names

- [ ] **Step 4: Implement Legend table**

- Add row: label text + style dropdown (from edge_styles)
- Delete selected rows

- [ ] **Step 5: Implement `getFormData()` — collect all tabs into one dict**

```javascript
function getFormData() {
    return {
        settings: getSettingsData(),
        edge_styles: getEdgeStylesData(),
        port_styles: getPortStylesData(),
        devices: getDevicesData(),
        cables: getCablesData(),
        simple_links: getSimpleLinksData(),
        zone_groups: getZoneGroupsData(),
        legend: getLegendData(),
    };
}
```

- [ ] **Step 6: Verify manually — all tabs work, getFormData produces correct structure**

- [ ] **Step 7: Commit**

```bash
git add tools/web/static/editor.js
git commit -m "feat: implement Cables, Legend tabs and getFormData"
```

---

### Task 9: Frontend — File Operations + Validation Display + TOML Preview

**Files:**
- Modify: `tools/web/static/editor.js`

- [ ] **Step 1: Implement toolbar buttons**

- **New**: Reset form (with unsaved-changes confirmation via `confirm()`)
- **Open**: File input → POST to `/upload` → `setFormData(response.data)`
- **Save**: POST form data to `/api/generate` (format=toml) → trigger download
- **Convert**: POST form data to `/api/generate` (format=drawio) → trigger download
- **Preview**: POST form data to `/api/preview` → show base64 PNG inline

- [ ] **Step 2: Implement validation display**

- Call `/api/validate` on form change (debounced, e.g. 500ms after last change)
- Show error badge on tab buttons
- Highlight invalid fields with `.field-error` class
- Show error messages near invalid fields

- [ ] **Step 3: Implement TOML preview panel**

- Toggle button to show/hide bottom panel
- On toggle open (or on form change): POST to `/api/generate` (format=toml) and display TOML text
- Monospace `<pre>` element

- [ ] **Step 4: Implement `setFormData(data)` — populate all tabs from dict**

Used by Open (upload) and also useful for testing.

```javascript
function setFormData(data) {
    setSettingsData(data.settings || {});
    setEdgeStylesData(data.edge_styles || {});
    setPortStylesData(data.port_styles || {});
    setDevicesData(data.devices || []);
    setCablesData(data.cables || []);
    setSimpleLinksData(data.simple_links || []);
    setZoneGroupsData(data.zone_groups || []);
    setLegendData(data.legend || []);
}
```

- [ ] **Step 5: Verify manually — full workflow**

1. Open browser, create a simple diagram (2 devices, 1 cable)
2. Click Save → verify TOML downloads correctly
3. Click New → form resets
4. Click Open → upload `examples/small_office.toml` → verify form populates
5. Click Convert → verify .drawio downloads
6. Click Preview → verify PNG appears (if Node.js available)
7. Introduce an error (remove device ID) → verify validation badges appear

- [ ] **Step 6: Commit**

```bash
git add tools/web/static/editor.js
git commit -m "feat: implement file ops, validation display, TOML preview"
```

---

### Task 10: Integration Testing + Polish

**Files:**
- Modify: `tests/test_web_app.py`
- Possibly: minor fixes to any file

- [ ] **Step 1: Write integration test — round-trip small_office.toml**

```python
    def test_round_trip_via_api(self):
        """Upload small_office.toml, generate TOML back, parse both, compare."""
        toml_path = os.path.join(os.path.dirname(__file__),
                                 '..', 'examples', 'small_office.toml')
        with open(toml_path, 'rb') as f:
            content = f.read()
        from io import BytesIO
        # Upload
        resp = self.client.post('/upload',
            data={'file': (BytesIO(content), 'small_office.toml')},
            content_type='multipart/form-data')
        uploaded = resp.get_json()
        self.assertTrue(uploaded['ok'])
        # Generate TOML back
        resp2 = self.client.post('/api/generate',
            data=json.dumps({"data": uploaded['data'], "format": "toml"}),
            content_type='application/json')
        generated = resp2.get_json()
        self.assertTrue(generated['ok'])
        self.assertIn('[settings]', generated['data']['toml'])
```

- [ ] **Step 2: Write integration test — generate drawio from datacenter.toml**

```python
    def test_generate_drawio_datacenter(self):
        toml_path = os.path.join(os.path.dirname(__file__),
                                 '..', 'examples', 'datacenter.toml')
        with open(toml_path, 'rb') as f:
            content = f.read()
        from io import BytesIO
        resp = self.client.post('/upload',
            data={'file': (BytesIO(content), 'datacenter.toml')},
            content_type='multipart/form-data')
        uploaded = resp.get_json()
        resp2 = self.client.post('/api/generate',
            data=json.dumps({"data": uploaded['data'], "format": "both"}),
            content_type='application/json')
        generated = resp2.get_json()
        self.assertTrue(generated['ok'])
        self.assertIn('drawio', generated['data'])
        self.assertIn('mxGraphModel', generated['data']['drawio'])
```

- [ ] **Step 3: Run all tests**

Run: `python3 -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Fix any remaining issues**

- [ ] **Step 5: Run existing project tests to ensure no regressions**

Run: `python3 -m unittest discover -s tests`
Expected: All PASS (including pre-existing tests)

- [ ] **Step 6: Commit**

```bash
git add tests/test_web_app.py
git commit -m "test: add integration tests for full round-trip workflow"
```

---

### Task 11: Documentation + Final Commit

**Files:**
- Modify: `CLAUDE.md` (add web editor section)

- [ ] **Step 1: Add web editor section to CLAUDE.md**

Add under `## コマンド`:
```markdown
# Web エディタ起動（要: pip install flask）
python3 tools/web/app.py
# ブラウザで http://localhost:5000 を開く
```

- [ ] **Step 2: Verify Flask is installable**

Run: `pip install flask` (or `pip3 install flask`)
Verify: No errors on RPi

- [ ] **Step 3: Full manual smoke test**

1. `python3 tools/web/app.py`
2. Open browser → http://localhost:5000
3. Load `examples/small_office.toml` via Open button
4. Verify all tabs populated correctly
5. Modify a device, add a cable
6. Save as TOML → verify output
7. Convert to drawio → verify output
8. Preview PNG (if available)

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add web editor launch instructions to CLAUDE.md"
```
