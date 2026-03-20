# TOML 配線図 作成ガイド

このガイドでは、TOML ファイルを書いて物理配線図（.drawio）を自動生成する手順を説明します。

## はじめに

**やること:** TOML ファイルを1つ書く → コマンドで `.drawio` に変換

```bash
python3 tools/toml2drawio.py mydiagram.toml
# → mydiagram.drawio が生成される
```

**サンプルファイル（コピーして使ってください）:**
- `docs/samples/minimal.toml` — 最小構成（スイッチ2台+サーバ1台）
- `docs/samples/small_network.toml` — 冗長構成（スイッチ+サーバ+ストレージ）
- `examples/datacenter.toml` — 大規模構成（23台、105本ケーブル）

---

## TOML の書き方（この順番で書く）

### ステップ 1: 全体設定

```toml
[settings]
router = "obstacle"
cable_layers = true
```

これだけで十分です。他の設定は省略可能。

<details>
<summary>設定の全オプション</summary>

| キー | デフォルト | 説明 |
|------|-----------|------|
| `router` | `"obstacle"` | `"naive"` / `"left-edge"` / `"obstacle"`（obstacle 推奨） |
| `layer_gap` | `200` | レイヤー間の垂直距離（px） |
| `device_gap` | `30` | 同一レイヤー内の機器間隔（px） |
| `cable_layers` | `false` | `true` でケーブルを draw.io レイヤーに分類 |

</details>

### ステップ 2: エッジスタイルとポートスタイルを定義

ケーブルとポートの見た目を名前付きで定義します。

```toml
[edge_styles]
data = { color = "blue", width = 2 }
mgmt = { color = "purple", width = 1.5, line = "dotted" }

[port_styles]
up   = { color = "red" }
down = { color = "blue" }
srv  = { color = "green" }
mgmt = { color = "gray" }
```

**使える色（16色）:**

> `red`, `orange`, `yellow`, `lime`, `green`, `teal`, `cyan`, `blue`, `navy`, `indigo`, `purple`, `magenta`, `pink`, `brown`, `gray`, `dark`

**冗長構成（1系/2系）には `_lt` 版を使う:**

> `red_lt`, `orange_lt`, `blue_lt` ... 各色に薄い版がある

例: 1系 `data = { color = "blue" }` / 2系 `data2 = { color = "blue_lt" }`

**使える線種（`line` に指定）:**

> `"solid"`（省略時のデフォルト）, `"dashed"`, `"dotted"`, `"dash-dot"`, `"long"`, `"short"`

### ステップ 3: デバイスを定義

デバイスは3種類あります。構成に応じて選んでください。

#### 種類 A: Flat（スイッチ等）— ポートが横1列

```toml
[[devices]]
id = "sw1"                  # ← ケーブル定義で使う識別子
label = "Switch-1"          # ← 図に表示される名前
layer = 0                   # ← 0 が最上段、数字が大きいほど下
style = "yellow"            # ← 背景色（yellow/green/purple/red/blue/gray）
ports = [
    { name = "u1", style = "up" },
    { name = "d1", style = "down" },
    { name = "d2", style = "down" },
]
```

#### 種類 B: Carded（サーバ等）— カード → ポートの2段構造

```toml
[[devices]]
id = "srv1"
label = "Server-1"
layer = 1
style = "blue"
[[devices.cards]]
name = "NIC1"
ports = [
    { name = "eth1", style = "srv" },
    { name = "eth2", style = "srv" },
]
[[devices.cards]]
name = "BMC"
ports = [
    { name = "mgmt", style = "mgmt" },
]
```

#### 種類 C: Controllers（ストレージ等）— 筐体 → コントローラ → カード → ポートの3段構造

```toml
[[devices]]
id = "stor1"
label = "Storage-A"
layer = 1
style = "blue"
[[devices.controllers]]
name = "Ctrl-A"
[[devices.controllers.cards]]
name = "iSCSI"
ports = [
    { name = "e0a", style = "srv" },
    { name = "e0b", style = "srv" },
]
[[devices.controllers]]
name = "Ctrl-B"
[[devices.controllers.cards]]
name = "iSCSI"
ports = [
    { name = "e2a", style = "srv" },
    { name = "e2b", style = "srv" },
]
```

**Controllers の注意点:** ポート名はコントローラ間で重複しないこと。Ctrl-A の `e0a` と Ctrl-B の `e0a` は別名にする（例: `e2a`）。

### ステップ 4: ケーブルを定義

デバイスID とポート名を `.` で繋いで接続先を指定します。

```toml
# 1本ずつ
[[cables]]
src = "sw1.d1"
dst = "srv1.eth1"
style = "data"

# まとめて（src と dst の要素数を揃える）
[[cables]]
src = ["sw1.d1", "sw1.d2"]
dst = ["srv1.eth1", "srv2.eth1"]
style = "data"
```

**★ 最重要ルール: ポート名の一致**

`src = "sw1.d1"` と書いたら、sw1 の ports に `{ name = "d1", ... }` が必ず存在しなければならない。
`dst = "srv1.eth1"` と書いたら、srv1 のカード内に `{ name = "eth1", ... }` が必ず存在しなければならない。

同じポートを2本のケーブルで使ってはいけない（1ポート=1ケーブル）。

### ステップ 5: 直結リンク（任意）

StackWise 等のスイッチ間直結に使います。

```toml
[[simple_links]]
devices = ["sw1", "sw2"]
label = ""
style = "stack"
```

### ステップ 6: 凡例（任意）

図の右上に表示される色の説明。

```toml
[[legend]]
label = "Data"
style = "data"

[[legend]]
label = "Management"
style = "mgmt"
```

### ステップ 7: ゾーングループ（任意・上級）

ケーブルが多い場合、種別ごとにルーティング領域を分けると見やすくなります。

```toml
[[zone_groups]]
layers = [0, 1]          # Layer 0 と Layer 1 の間の領域
groups = [
    ["uplink"],          # uplink スタイルのケーブルだけのゾーン
    ["uplink2"],         # uplink2 スタイルのケーブルだけのゾーン
]
```

---

## チェックリスト（書き終わったら確認）

1. すべてのデバイスに一意の `id` がある
2. すべてのケーブルの `src`/`dst` のデバイスIDとポート名が、デバイス定義と一致している
3. 同じポートが2本以上のケーブルで使われていない
4. 一括記法の `src` と `dst` の要素数が同じ
5. `style` がすべて `[edge_styles]` に定義されている
6. ポートの `style` がすべて `[port_styles]` に定義されている
7. Controllers デバイスのポート名がコントローラ間で重複していない

---

## よくあるエラーと対処

| エラーメッセージ | 原因 | 対処 |
|----------------|------|------|
| `Unknown edge style 'xxx'` | ケーブルの style が未定義 | `[edge_styles]` に追加 |
| `Unknown port style 'xxx'` | ポートの style が未定義 | `[port_styles]` に追加 |
| `src (N) and dst (M) length mismatch` | 一括記法で要素数が不一致 | src と dst の数を揃える |
| `Port 'xxx' not found in device 'yyy'` | ポート名の不一致 | デバイス定義のポート名を確認 |
| `Device 'xxx' has no ports, cards, or controllers` | デバイスに構造が未定義 | ports/cards/controllers のいずれかを追加 |

---

## 生成と確認

```bash
# .drawio ファイルを生成
python3 tools/toml2drawio.py mydiagram.toml

# 出力先を指定する場合
python3 tools/toml2drawio.py mydiagram.toml -o output.drawio

# PNG プレビュー（要: node + puppeteer-core）
node tools/drawio_to_png.mjs mydiagram.drawio
```

生成された `.drawio` は https://app.diagrams.net で開いて確認できます。
