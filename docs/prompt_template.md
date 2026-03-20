# 配線図生成プロンプト テンプレート

新しい配線図を作る際、以下のテンプレートで AI に指示すると 1-2 回のやり取りで完成します。

2つのアプローチがあります:
- **Topology API（推奨）** — 機器とケーブルを宣言するだけで自動レイアウト
- **Direct Diagram API** — 座標を手動指定して細かく制御

どちらも以下の import で始めます:

```python
import sys
sys.path.insert(0, '/home/user/code/drawio_infra_py/lib')

from wiring_diagram import Topology, ObstacleRouter       # Topology API
from wiring_diagram import Diagram, nid                    # Direct Diagram API
from wiring_diagram import edge_style, port_style          # 共通
from wiring_diagram import (
    PALETTE, LINE_STYLES,
    BG_YELLOW, BG_GREEN, BG_PURPLE, BG_RED, BG_BLUE, BG_GRAY,
    PORT_BLUE, PORT_NAVY, PORT_GREEN, PORT_RED, PORT_GRAY,
)
```

---

## テンプレート A: Topology API（推奨）

コピペして空欄を埋めるだけで配線図を指示できます。

> `sandbox/NN_name/gen_name.py` を作成し、**Topology API** で
> _____ の物理配線図を生成するスクリプトを書いてほしい。

### 1. 機器一覧

```markdown
| ID | ラベル | レイヤー | BG色 | 種別 | 構造 |
|----|--------|---------|------|------|------|
| sw1 | Core-SW (Nexus 9500) | 0 | BG_PURPLE | flat | ports=[(port_label, PORT_style), ...] |
| srv1 | Dell R660-1 | 1 | BG_BLUE | carded | cards=[...] |
| nas1 | NetApp AFF A400 | 1 | BG_BLUE | 3-level | controllers=[...] |
```

**種別ごとの構造定義:**

**Flat（スイッチ等）** — ポート横1列:
```python
T.add_device("sw1", label="Core-SW\n(Nexus 9500)", style=BG_PURPLE, layer=0,
             ports=[("p1", PORT_RED), ("p2", PORT_RED), ("p3", PORT_BLUE)])
```

**2段 Carded（サーバ等）** — NICカード → ポート:
```python
T.add_device("srv1", label="Dell R660-1", style=BG_BLUE, layer=1,
             cards=[
                 ("OCP",   [("ocp1", False, PORT_GREEN), ("ocp2", False, PORT_GREEN)]),
                 ("PCIe1", [("pci1", True,  PORT_GREEN), ("pci2", True,  PORT_GREEN)]),
                 # (port_label, has_sfp, PORT_style)
                 ("BMC", [("mgmt", False, PORT_GRAY)]),
             ])
```

**3段 Controllers（ストレージ等）** — 筐体 → コントローラ → カード → ポート:
```python
T.add_device("nas1", label="NetApp AFF A400", style=BG_BLUE, layer=1,
             controllers=[
                 ("Controller A", [
                     ("iSCSI", [("e0a", False, PORT_GREEN), ("e0b", False, PORT_GREEN)]),
                     ("NFS",   [("e1a", False, PORT_GREEN), ("e1b", False, PORT_GREEN)]),
                     ("Mgmt",  [("e0M", False, PORT_GRAY)]),
                 ]),
                 ("Controller B", [
                     ("iSCSI", [("e0a", False, PORT_GREEN), ("e0b", False, PORT_GREEN)]),
                     ("NFS",   [("e1a", False, PORT_GREEN), ("e1b", False, PORT_GREEN)]),
                     ("Mgmt",  [("e0M", False, PORT_GRAY)]),
                 ]),
             ])
```

### 2. 配線仕様

```markdown
| Source (device, port) | Dest (device, port) | Style | Label (任意) |
|-----------------------|---------------------|-------|-------------|
| sw1, p1 | srv1, ocp1 | edge_style("orange", width=2) | |
| sw1, p2 | nas1, e0a | edge_style("red", width=2) | |
```

### 3. 直結リンク（StackWise等、任意）

```python
T.add_simple_link("sw1", "sw2", "StackWise",
                  edge_style("gray", width=1.5, line="dotted"))
```

### 4. レイアウトオプション

```python
D = T.to_diagram(
    router=ObstacleRouter(),  # or LeftEdgeRouter() or NaiveRouter()
    layer_gap=200,            # レイヤー間の垂直距離 (default 200)
    device_gap=30,            # 同一レイヤー内の機器間隔 (default 30)
    cable_layers=True,        # draw.io レイヤーで配線をグループ化
    port_w=14, port_h=12,     # ポートサイズ
)
```

### 5. 凡例（任意）

```python
D.legend([
    ("10G Data",   edge_style("orange", width=2)),
    ("25G iSCSI",  edge_style("red", width=2)),
    ("1G Mgmt",    edge_style("cyan", width=1.5)),
    ("StackWise",  edge_style("gray", width=1.5, line="dotted")),
])
```

---

## テンプレート B: Direct Diagram API

座標やサイズを細かく指定したい場合に使います。

> `sandbox/NN_name/gen_name.py` を作成し、`Diagram` クラスを使って
> _____ の物理配線図を生成するスクリプトを書いてほしい。

### 1. 機器のビジュアル構造（ASCII で十分）

```
【スイッチ（device()）】
┌───────────────────────────────┐
│ Svc-SW-1 (Cisco C9300X-24HX) │  ← ラベル
│ [1][2][3]...[24]              │  ← ポート横一列、小正方形
│ sublabel: "1/0/1 ─ 1/0/24"   │  ← ポート内番号なし、範囲をまとめて表記
└───────────────────────────────┘
  ・全ポート表示（未使用はグレー）
  ・使用中は色で種別を区別

【サーバ（device_carded()）】
┌────────────────────────────────────┐
│ ┌──OCP──┐ ┌─PCIe1─┐ ┌─PCIe2─┐   │  ← NICカード = ボックス
│ │[s][s] │ │[s][s] │ │       │   │  ← [s] = SFPモジュール（ケーブル側）
│ │[■][■] │ │[■][■] │ │[□][□] │   │  ← [■/□] = ポート
│ └───────┘ └───────┘ └───────┘   │
│                        Dell-1     │  ← ラベルはケーブルの逆側
└────────────────────────────────────┘
```

### 2. レイアウト指定

上下の配置と数値を指定します。

```
Y=20   [Core-SW]
Y=110  [Svc-SW-1] [Svc-SW-2] ... [Mgmt-SW-1] [Mgmt-SW-2]
Y=210〜410  ← ケーブルルーティングゾーン（200px確保）
Y=430  [NetApp-A] [NetApp-B] [Dell-1] [Dell-2] ... [AD-1] [AD-2]
```

ポイント:
- ルーティングゾーンの高さ = ケーブル本数に応じて確保
- 機器間の横ギャップ: 同種 20px、異種 30-60px

### 3. サイズ基準

| 要素 | 幅 | 高さ | 備考 |
|------|-----|------|------|
| スイッチポート | 14-16px | 12-14px | 実機のポート感覚で小さめ |
| SFPモジュール | 8px | 6px | ポートに貼り付け |
| ケーブルゾーン | - | 200px以上 | ケーブル本数に比例 |

### 4. 配線仕様

```python
E_10G = edge_style("orange", width=2)
E_MGT = edge_style("cyan", width=1.5, line="dotted")

D.add_edge(src_cx, src_cy, tgt_cx, tgt_cy, src_id, tgt_id, E_10G, label="")
D.simple_edge("sw1", "sw2", "StackWise",
              edge_style("gray", width=1.5, line="dotted"))
```

### 5. 凡例

```python
D.legend([
    ("10G Data", E_10G),
    ("Mgmt",     E_MGT),
])
```

---

## 実践例

### 例1: Topology API 最小プロンプト

> `sandbox/99_demo/gen_demo.py` を作成してほしい。
> Topology API + ObstacleRouter で以下を生成:
>
> **機器:**
> | ID | ラベル | Layer | BG | 種別 |
> |----|--------|-------|----|------|
> | core | Core-SW (Nexus 9300) | 0 | BG_PURPLE | flat: 4ポート |
> | dist1 | Dist-SW-1 (C9300) | 1 | BG_YELLOW | flat: 5ポート |
> | dist2 | Dist-SW-2 (C9300) | 1 | BG_YELLOW | flat: 5ポート |
> | srv1 | Server-1 | 2 | BG_BLUE | carded: NIC(eth0, eth1) |
> | srv2 | Server-2 | 2 | BG_BLUE | carded: NIC(eth0, eth1) |
>
> **配線:**
> | Source | Dest | Style |
> |--------|------|-------|
> | core:p1 → dist1:u1 | edge_style("red", width=3) |
> | core:p2 → dist2:u1 | edge_style("red", width=3) |
> | dist1:d1 → srv1:eth0 | edge_style("blue", width=1.5) |
> | dist2:d1 → srv2:eth0 | edge_style("blue", width=1.5) |
>
> **直結:** dist1 ↔ dist2 StackWise (gray, dotted)
>
> **凡例:** 10G Uplink (red), 1G Data (blue), StackWise (gray dotted)

### 例2: Direct Diagram API 最小プロンプト

> `sandbox/07_onprem/gen_wiring.py` を作成してほしい。
> `Diagram` クラスを使うこと。
>
> 【構成】
> - 上段: スイッチ4台（Svc-SW x2 + Mgmt-SW x2）、Core-SW 1台
> - 下段: サーバ7台（NetApp x2, Dell x3, AD x2）
> - スイッチポート: 16x14px、全24ポート表示、未使用グレー
> - サーバ: NICカード構造、SFP付きポートあり
> - ルーティングゾーン: Y=210〜410
>
> 【配線】
> (テーブルを貼る)
>
> 【凡例】
> (色と意味の対応を貼る)

---

## やり取りを減らすコツ

1. **サイズは px で指定する** — 「小さめ」は曖昧、「16x14px」は一意
2. **未使用ポートの扱いを明記する** — 全表示 or 使用中のみ
3. **参考画像があれば添付する** — 手書きスケッチでも効果大
4. **ライブラリの既存スクリプトを読ませる** — `examples/datacenter.py` を先に読ませると出力の形式が合う
5. **Topology API ならレイアウト指定不要** — layer= だけで上下配置が決まる
6. **ObstacleRouter でケーブル迂回は自動** — デバイスボックスを避けてルーティングされる

---

## クイックリファレンス（AI向け）

### カラーパレット（16色 + 16色 `_lt` 版）

各色に薄い `_lt`（light）版があり、冗長構成の2系パスに使える。

| 名前 | strokeColor | fillColor | portStroke |
|------|-------------|-----------|------------|
| red | #E03030 | #f8cecc | #b85450 |
| orange | #FF8000 | #ffe6cc | #d79b00 |
| yellow | #D6B656 | #fff2cc | #d6b656 |
| lime | #7AB648 | #e6f5d0 | #7AB648 |
| green | #52A352 | #d5e8d4 | #82b366 |
| teal | #00A89D | #ccf2f0 | #00897B |
| cyan | #00B0F0 | #ddf4ff | #0097CC |
| blue | #0070C0 | #dae8fc | #6c8ebf |
| navy | #3A5FA0 | #b3cde3 | #3a5fa0 |
| indigo | #5C4DB1 | #d9d2f0 | #5C4DB1 |
| purple | #9673A6 | #e1d5e7 | #9673a6 |
| magenta | #CC3399 | #f5d0e6 | #a8286b |
| pink | #F06090 | #fce4ec | #d84a6e |
| brown | #8B5E3C | #efdbcb | #795548 |
| gray | #888888 | #f5f5f5 | #999999 |
| dark | #444444 | #e0e0e0 | #555555 |
| red_lt | #F08080 | #fde8e8 | #d4807a |
| orange_lt | #FFB366 | #fff2e0 | #e0a840 |
| yellow_lt | #E8D48A | #fffbeb | #d6c47a |
| lime_lt | #A8D480 | #f0fadf | #9ac47a |
| green_lt | #82C882 | #e4f4e4 | #6aaa6a |
| teal_lt | #66CBC4 | #e0f8f6 | #4aada6 |
| cyan_lt | #66D0F8 | #e8f8ff | #4ab0d8 |
| blue_lt | #60A0D8 | #e4f0ff | #7aaccc |
| navy_lt | #7A8FC0 | #d6e0f0 | #6a80b0 |
| indigo_lt | #9080D0 | #e8e0f8 | #8070c0 |
| purple_lt | #B8A0C8 | #f0e8f4 | #a890b8 |
| magenta_lt | #E080C0 | #fce8f4 | #c860a0 |
| pink_lt | #F8A0B8 | #fef0f4 | #e08898 |
| brown_lt | #B89878 | #f6ede4 | #a08870 |
| gray_lt | #B0B0B0 | #fafafa | #bbbbbb |
| dark_lt | #808080 | #eeeeee | #909090 |

### 線種（6種）

| 名前 | パターン | ビジュアル |
|------|---------|-----------|
| solid | (なし) | ──────── |
| dashed | 8 4 | ── ── ── |
| dotted | 3 1 | ·· ·· ·· |
| dash-dot | 8 3 2 3 | ──·──·── |
| long | 12 6 | ———  ——— |
| short | 4 3 | ─ ─ ─ ─ |

### スタイル関数

```python
# エッジ（ケーブル）
edge_style(color_name, width=2, line="solid")
# → "strokeColor=#FF8000;strokeWidth=2;"

# ポート
port_style(color_name, bold=False)
# → "fillColor=#dae8fc;strokeColor=#6c8ebf;"
```

### プリセット定数

| 定数 | 用途 |
|------|------|
| `PORT_BLUE`, `PORT_NAVY`, `PORT_GREEN`, `PORT_RED`, `PORT_GRAY` | ポート色 |
| `EDGE_BLUE`, `EDGE_NAVY`, `EDGE_GREEN`, `EDGE_RED`, `EDGE_ACCENT` | エッジ色 |
| `BG_YELLOW`, `BG_GREEN`, `BG_PURPLE`, `BG_RED`, `BG_BLUE`, `BG_GRAY` | デバイス背景色 |
| `CARD_STYLE`, `CTRL_STYLE`, `SFP_STYLE` | NICカード/コントローラ/SFP 内部スタイル |

### デバイス種別と引数形式

| 種別 | Topology API | Diagram API |
|------|-------------|-------------|
| Flat (スイッチ) | `ports=[(label, style), ...]` | `D.device(cid, label, x, y, style, [(label, pid, style), ...])` |
| 2段 Carded (サーバ) | `cards=[(card_label, [(label, has_sfp, style), ...]), ...]` | `D.device_carded(cid, label, x, y, style, cards=[(card_label, [(label, pid, has_sfp, style), ...]), ...])` |
| 3段 Controllers (ストレージ) | `controllers=[(ctrl_label, [(card_label, [...]), ...]), ...]` | `D.device_carded(cid, label, x, y, style, controllers=[(ctrl_label, [(card_label, [...]), ...]), ...])` |

### ルーター比較表

| ルーター | 特徴 | 用途 |
|---------|------|------|
| `NaiveRouter()` | 1エッジ=1レーン、midpoint X でソート | シンプルな図（~10本） |
| `LeftEdgeRouter()` | レーン圧縮 + barycenter 交差最小化 | 中規模（~30本） |
| `ObstacleRouter()` | LeftEdgeRouter + デバイスボックス迂回 + 垂直重なり回避 | 大規模・密集配線（推奨） |

### `to_diagram()` パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `router` | `LeftEdgeRouter()` | ルーティング戦略 |
| `layer_gap` | `200` | レイヤー間の垂直距離 (px) |
| `device_gap` | `30` | 同一レイヤー内の機器間隔 (px) |
| `route_zone_height` | `layer_gap * 0.6` | ルーティングゾーンの高さ (px) |
| `first_layer_y` | `30` | 最上位レイヤーの Y オフセット |
| `port_w` | `14` | ポート幅 (px) |
| `port_h` | `12` | ポート高さ (px) |
| `cable_layers` | `False` | True で draw.io レイヤー自動割り当て |
| `page_w` | auto | ページ幅（None で自動計算） |
| `page_h` | auto | ページ高さ（None で自動計算） |

### サンプル参考

| パス | 内容 | API |
|------|------|-----|
| `examples/datacenter.py` | 大規模DC（24機器、100本ケーブル） | Topology + ObstacleRouter |
