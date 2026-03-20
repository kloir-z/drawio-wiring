# TOML Editor GUI - Design Spec

## Overview

drawio_infra_py の TOML 配線図定義ファイルを、GUI で作成・編集できる Web ベースのエディタ。TOML スキーマを知らないチームメンバーでも、表形式の UI で配線図定義を完成させられることを目的とする。

## Requirements

- **Users**: TOML スキーマに不慣れなチームメンバー
- **Workflow**: 新規作成 / 既存 TOML 読み込み・編集 / バリデーション / drawio 変換 / PNG プレビュー
- **Environment**: Raspberry Pi 4 (aarch64, Debian 12, Python 3.11)
- **Constraints**: 後からの UI 調整を容易にする構造。外部依存は Flask のみ追加（`pip install flask`）
- **PNG preview dependency**: Node.js + puppeteer-core が既にインストール済みであることを前提とする。未インストール時は Preview ボタンをグレーアウトし「要 Node.js + puppeteer-core」と表示

## Architecture

```
Browser (HTML/JS)              Flask Server (tools/web/)
┌─────────────────┐           ┌──────────────────────┐
│ Tab-based Form  │◄──JSON──►│ /api/validate        │
│                 │           │ /api/generate         │
│ TOML Preview    │           │ /api/preview          │
│ PNG Preview     │           │ /upload (TOML import) │
│ Download        │           │ /download (TOML/drawio│
└─────────────────┘           └──────┬───────────────┘
                                     │ import
                              ┌──────▼───────────────┐
                              │ tools/toml2drawio.py  │
                              │ lib/wiring_diagram/   │
                              │ tools/drawio_to_png.mjs│
                              └──────────────────────┘
```

## File Structure

```
tools/web/
├── app.py              ← Flask app (API + page serving)
├── toml_writer.py      ← Custom TOML serializer (dict → TOML string)
├── validator.py        ← Validation rules (reusable outside Flask)
├── static/
│   ├── style.css       ← Styling
│   └── editor.js       ← Tab switching, table CRUD, validation, API calls
└── templates/
    └── editor.html     ← Jinja2 template (main editor page)
```

Launch: `python3 tools/web/app.py` → `http://localhost:5000`

## Tab Structure

6 tabs, each with a table-based editor:

| Tab | Content | UI |
|-----|---------|-----|
| Settings | router, layer_gap, device_gap, cable_layers, first_layer_y, port_w, port_h, page_w, page_h | Form (dropdowns + number inputs) |
| Edge Styles | Named edge style definitions | Table (name, color dropdown, width, line style dropdown, extra markers text field) |
| Port Styles | Named port style definitions | Table (name, color dropdown, bold checkbox) |
| Devices | Device definitions | Table + expandable nested panel |
| Cables | Cable definitions + zone_groups + simple_links | Table with 2-stage dropdown (device→port) |
| Legend | Legend entries | Table (label, style dropdown) |

### Devices Tab Detail

Devices have three structural types, requiring a nested UI:

- **Device list**: Table showing id, label, layer, style (BG color), type (flat/carded/3-level), cable_side (top/bottom, default: top)
- **Expand on click**: Opens a detail panel below the row
- **Type dropdown** switches the detail panel:
  - **flat**: Simple port table (name, style)
  - **carded**: Card table, each card expandable to port table (name, sfp checkbox, style)
  - **3-level (controllers)**: Controller table → Card table → Port table (name, sfp checkbox, style)

### Cables Tab Detail

- **Cables section**: src/dst use 2-stage dropdowns (device → port). A "bulk" mode allows adding multiple src/dst pairs per cable entry. Optional fields: label (text), zone (text).
- **Simple Links section**: Toggle-switchable sub-section. Two device ID dropdowns + label + style + optional zone.
- **Zone Groups section**: Layer pair (two numbers) + group name array (selected from defined edge_style names).

## API Design

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Serve editor page |
| POST | `/api/validate` | Validate JSON form data, return errors |
| POST | `/api/generate` | JSON → TOML + drawio conversion, return TOML/drawio as file download |
| POST | `/api/preview` | generate + PNG generation, return base64 image |
| POST | `/upload` | Parse uploaded TOML file, return JSON for form |
| GET | `/api/schema` | Return PALETTE colors, LINE_STYLES, BG colors, router types |

### Response Format (unified)

```json
{
  "ok": true,
  "errors": [],
  "data": {}
}
```

## Data Flow

```
Browser form state (JS object)
    ↓ JSON POST
Flask: JSON → Python dict → TOML string (custom serializer, no tomli_w dependency)
    ↓ build_topology() + topology_to_diagram()
    ↓ D.save() → .drawio file
    ↓ drawio_to_png.mjs → .png file
    ↓ PNG as base64 in response
Browser: display preview
```

### TOML Serialization

Python 3.11 の `tomllib` は読み取り専用のため、TOML 出力はカスタムシリアライザで行う。スキーマが固定的なので、セクションごとにテンプレート的に文字列を組み立てる方式（`toml_writer.py`）。外部依存の追加は不要。

## Validation Rules

Validation runs server-side (reusable by CLI) and results displayed in the UI:

- Required fields: device.id, device.layer, port.name, cable.src, cable.dst, cable.style
- Device ID uniqueness
- Cable src/dst reference existing device.port
- Edge/port style references are defined
- Layer values are integers
- zone_groups.layers has exactly 2 items
- simple_links.devices has exactly 2 items
- cable_layers accepts boolean true or string "device" / "style"
- device.cable_side is "top" or "bottom"
- edge_style line values match LINE_STYLES keys (extra markers after `;` are free-form)

### Error Display

- Tab name shows badge count (e.g., `Devices ⚠2`)
- Invalid fields highlighted with red border
- Error messages in Japanese

## TOML Preview Panel

- Toggleable panel (画面下部に配置)
- Shows current form state as live TOML text
- Allows advanced users to verify output format

## File Operations

| Button | Action |
|--------|--------|
| New | Reset all form fields (未保存の変更がある場合は確認ダイアログ表示) |
| Open | Upload TOML file → parse → populate form |
| Save | Generate TOML string → download as .toml |
| Convert | TOML → drawio conversion → download .drawio |
| Preview | Convert + PNG generation → display inline |

## Dropdown Options (from library)

- **Colors**: PALETTE 32 colors (16 primary + 16 `_lt`), displayed with color chip
- **Line styles**: LINE_STYLES (solid, dashed, dotted, dash-dot, long, short)
- **BG styles**: yellow, green, purple, red, blue, gray
- **Routers**: naive, left-edge, obstacle

## Design for Change

The user expects iterative UI adjustments. Key structural decisions to support this:

- **Validation rules** in isolated functions — easy to add/modify/remove
- **Tab structure** in template partials — tabs can be reordered/added without touching JS logic
- **API response format** unified — frontend error handling stays consistent
- **CSS** separated — visual tweaks without touching logic
- **editor.js** organized by tab — each tab's logic in its own section/module

## Raw Style Passthrough

Edge style / port style のドロップダウンに加え、各スタイルフィールドに「カスタム (raw)」オプションを用意。選択するとテキスト入力欄が表示され、draw.io の生スタイル文字列を直接入力可能。TOML インポート時に raw スタイル（`=` を含む文字列）を検出した場合は自動的にこのモードで表示。

## TOML Import Edge Cases

- GUI が対応していないフィールドが TOML に含まれる場合: 警告を表示しつつ、未知のフィールドはそのまま保持して再出力時に含める
- Raw スタイル文字列: ドロップダウンではなく raw テキスト入力モードで表示
