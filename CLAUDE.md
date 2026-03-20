# CLAUDE.md

このプロジェクトは draw.io 物理配線図を Python スクリプトで自動生成する。

## 環境

- Raspberry Pi 4, aarch64, Debian 12, Python 3.11（システム標準 `/usr/bin/python3`）
- draw.io デスクトップ不可（ARM64 非対応）。生成した `.drawio` は https://app.diagrams.net で閲覧
- venv なし。外部依存ゼロ（標準ライブラリのみ）

## ディレクトリ構成

```
drawio_infra_py/
├── lib/wiring_diagram/         ← 配線図生成パッケージ
│   ├── __init__.py             ← 再エクスポート（既存 import 互換維持）
│   ├── styles.py               ← PALETTE, LINE_STYLES, edge_style(), port_style(), BG_* 定数
│   ├── ids.py                  ← nid(), reset_ids()
│   ├── diagram.py              ← Diagram クラス本体
│   ├── routing.py              ← Router 基底 + NaiveRouter, LeftEdgeRouter, ObstacleRouter
│   ├── layout.py               ← compute_layout()（Sugiyama法 自動レイアウト）
│   └── graph.py                ← Topology クラス（高レベルグラフ → 自動レイアウト）
├── examples/
│   ├── datacenter.toml         ← 大規模サンプル（24機器, 100本ケーブル）
│   ├── datacenter.drawio       ← 生成済みサンプル出力
│   ├── datacenter.png          ← README 用スクリーンショット
│   ├── small_office.toml       ← 小規模サンプル（4サーバ+ストレージ）
│   ├── small_office.drawio     ← 生成済みサンプル出力
│   └── small_office.png        ← スクリーンショット
├── tests/
│   ├── test_diagram.py         ← XML構造テスト
│   ├── test_routing.py         ← ルーティング特性テスト
│   ├── test_topology.py        ← Topology API テスト
│   └── test_toml2drawio.py     ← TOML→drawio 変換テスト
├── docs/
│   └── prompt_template.md      ← AI向けプロンプトテンプレート
├── sandbox/                    ← 実験用（.gitignore 済み）
└── tools/
    └── toml2drawio.py          ← TOML 定義 → .drawio 変換ツール
```

## コマンド

```bash
# サンプル図を生成する（TOML 定義）
python3 tools/toml2drawio.py examples/datacenter.toml

# テスト実行
python3 -m unittest discover -s tests

# .drawio → PNG プレビュー（要: npm install --prefix tools puppeteer-core）
node tools/drawio_to_png.mjs examples/datacenter.drawio

# 生成 + プレビュー一括実行（Python スクリプト用）
bash tools/preview.sh sandbox/my_script.py

# ライブラリの API ドキュメント
head -30 lib/wiring_diagram/__init__.py
```

## 新しい図を追加する手順

### 方法 A: TOML 定義ファイル（推奨）

1. `.toml` ファイルを作成（`examples/datacenter.toml` を参考）
2. `python3 tools/toml2drawio.py mydiagram.toml` で `.drawio` を生成
3. `-o output.drawio` で出力先を指定可能

### 方法 B: Python スクリプト

1. スクリプトを作成（`sandbox/` 以下は gitignore 済みなので自由に使える）
2. 先頭で `sys.path.insert(0, '/home/user/code/drawio_infra_py/lib')` してから `from wiring_diagram import Topology, ObstacleRouter` 等を import
3. `D.save("output.drawio")` で出力
4. 公開用サンプルにする場合は `examples/` に配置

## ライブラリ API

詳細は `lib/wiring_diagram/__init__.py` 冒頭のdocstringを参照。主要クラス・関数:

| 名前 | 用途 |
|------|------|
| `Diagram(page_w, page_h, route_y_min, route_y_max, router=None)` | 図全体の管理 |
| `D.device(...)` | スイッチ等（ポート横1列） |
| `D.device_carded(..., cards=)` | サーバ（NICカード構造: 2段） |
| `D.device_carded(..., controllers=)` | ストレージ等（筐体→コントローラ→カード: 3段） |
| `D.add_edge(..., zone=None)` | ケーブルをキュー登録（zone で多層対応） |
| `D.simple_edge(...)` | スタックリンク等の直結エッジ |
| `D.legend(entries)` | 凡例ボックス追加（`[(label, style), ...]`） |
| `D.save(path)` | XML書き出し（`flush_edges()` 自動呼び出し） |
| `nid(prefix)` | 一意 ID 生成 |
| `PALETTE` | カラーパレット辞書（16色 + 16色 `_lt` 版: red〜dark, red_lt〜dark_lt） |
| `LINE_STYLES` | 線種辞書（solid/dashed/dotted/dash-dot/long/short） |
| `edge_style(color, width, line)` | エッジスタイル文字列生成 |
| `port_style(color, bold)` | ポートスタイル文字列生成 |
| `NaiveRouter()` | デフォルト: 1エッジ1レーン |
| `LeftEdgeRouter()` | レーン圧縮 + barycenter 交差最小化 |
| `ObstacleRouter()` | LeftEdgeRouter + 垂直セグメントのデバイス迂回 + 垂直重なり回避 |
| `Topology()` | 高レベルグラフモデル（自動レイアウト） |
| `T.add_device(...)` | デバイス追加（flat / carded / 3-level controllers） |
| `ControllerDef` | 3段デバイス用コントローラ定義（graph.py） |
| `T.add_cable(...)` | ケーブル追加 |
| `T.add_simple_link(...)` | 直結リンク追加（StackWise等） |
| `T.to_diagram(...)` | 自動レイアウトして Diagram を返す |

## TOML → drawio 変換ツール

`tools/toml2drawio.py` は TOML 定義ファイルから `.drawio` を生成する。Python 3.11 の `tomllib`（標準ライブラリ）を使用。

### TOML スキーマ概要

| セクション | 用途 |
|-----------|------|
| `[settings]` | `router`, `layer_gap`, `device_gap`, `cable_layers` 等のレイアウト設定 |
| `[edge_styles]` | 名前付きエッジスタイル定義（`color`, `width`, `line`） |
| `[port_styles]` | 名前付きポートスタイル定義（`color`, `bold`） |
| `[[devices]]` | デバイス定義（`ports` / `cards` / `controllers` で構造指定） |
| `[[cables]]` | ケーブル定義（`src`, `dst` はリストで一括指定可） |
| `[[simple_links]]` | StackWise等の直結リンク |
| `[[legend]]` | 凡例エントリ |

色名は PALETTE の16色（`red`, `blue`, `green` 等）＋ 各色の薄い版（`red_lt`, `blue_lt` 等、冗長2系パス向け）。背景は6色（`yellow`, `green`, `purple`, `red`, `blue`, `gray`）。生の draw.io スタイル文字列（`=` 含む）も直接使用可。
