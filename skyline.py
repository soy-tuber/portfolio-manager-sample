"""保有銘柄を「ネオンの街」として描く SVG ジェネレータ

棒グラフ (量の比較) をビル群に見立てたもの。見た目は都市だが、
エンコードは素直な棒グラフのままにしてある:

  - 高さは時価に**線形**比例し、必ず 0 を基準にする。
    平方根などで圧縮すると見栄えは整うが量の比較が嘘になるため使わない。
  - 色は銘柄の性格 (担保 / LTV対象外) を表すカテゴリ2色。検証済みの
    明度バンド内の値で、2色の CVD 分離は 6-8 のフロア帯にあるため
    各ビットに**直接ラベル**を併記することを必須とする。
  - 窓の点灯は銘柄コードから決定的に導く。乱数を使うと再実行のたびに
    街並みが変わり、データが変わっていないのに画面が動いてしまう。

Streamlit にもネットワークにも依存しないため単体テスト可能。
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from xml.sax.saxutils import escape

# レイアウト (viewBox 座標)
VIEW_W = 960
VIEW_H = 340
SKY_TOP = 24
GROUND_Y = 272           # 地面 (ビルの底辺)
MAX_BUILDING_H = GROUND_Y - SKY_TOP - 26   # 値ラベル用に上を空ける
GAP = 14                 # ビル間の余白
ROOF_R = 4               # 屋上の丸み
WINDOW_W, WINDOW_H = 6, 7
WINDOW_GAP_X, WINDOW_GAP_Y = 11, 13


@dataclass(frozen=True)
class Building:
    key: str          # 決定的な窓配置のための種 (銘柄コード)
    label: str        # 直接ラベル (必須)
    sublabel: str     # 補足 (株数など)
    value: float      # 高さを決める量 (時価)
    value_text: str   # 値ラベル
    color: str        # カテゴリ色
    category: str     # 凡例の見出し


def fnv1a(text: str) -> int:
    """決定的な32bitハッシュ。

    Python の組込み hash() はプロセスごとに種が変わるため使わない
    (同じデータでも再起動のたびに窓並びが変わってしまう)。
    """
    h = 0x811c9dc5
    for byte in text.encode('utf-8'):
        h = ((h ^ byte) * 0x01000193) & 0xFFFFFFFF
    return h


def window_is_lit(key: str, row: int, col: int, lit_ratio: int = 62) -> bool:
    """そのビルの (row, col) の窓が点いているか。常に同じ答えを返す。"""
    return fnv1a(f'{key}:{row}:{col}') % 100 < lit_ratio


def building_height(value: float, max_value: float) -> float:
    """0 基準の線形スケール。"""
    if max_value <= 0:
        return 0.0
    return MAX_BUILDING_H * max(0.0, value) / max_value


def _windows(x: float, y: float, w: float, h: float, key: str) -> list[str]:
    """ビルの壁に窓を敷き詰める。"""
    out = []
    inset_x, inset_top = 7.0, 12.0
    cols = int((w - inset_x * 2 + WINDOW_GAP_X) // (WINDOW_W + WINDOW_GAP_X))
    rows = int((h - inset_top - 6 + WINDOW_GAP_Y) // (WINDOW_H + WINDOW_GAP_Y))
    if cols < 1 or rows < 1:
        return out
    used_w = cols * WINDOW_W + (cols - 1) * WINDOW_GAP_X
    start_x = x + (w - used_w) / 2
    for row in range(rows):
        wy = y + inset_top + row * (WINDOW_H + WINDOW_GAP_Y)
        for col in range(cols):
            wx = start_x + col * (WINDOW_W + WINDOW_GAP_X)
            # 消えている窓は描かない。壁の塗り (opacity .30) がそのまま
            # 暗い窓に見えるので、ノード数を半分近くまで減らせる。
            if not window_is_lit(key, row, col):
                continue
            out.append(
                f'<rect x="{wx:.0f}" y="{wy:.0f}" width="{WINDOW_W}" height="{WINDOW_H}" '
                f'fill="#ffffff" opacity="0.8"/>'
            )
    return out


def _stars(seed: str, count: int = 46) -> list[str]:
    """空の星。これも決定的に置く。"""
    out = []
    for i in range(count):
        h = fnv1a(f'{seed}:star:{i}')
        x = h % VIEW_W
        y = SKY_TOP + (h >> 8) % max(1, GROUND_Y - SKY_TOP - 150)
        r = 0.6 + ((h >> 16) % 3) * 0.35
        opacity = 0.18 + ((h >> 20) % 5) * 0.10
        out.append(f'<circle cx="{x}" cy="{y}" r="{r:.2f}" fill="#d8e6f2" opacity="{opacity:.2f}"/>')
    return out


def render(buildings: list[Building], *, text: str, muted: str,
           ground: str, title: str = '') -> str:
    """スカイラインの SVG を文字列で返す。"""
    if not buildings:
        return ''

    max_value = max(b.value for b in buildings)
    n = len(buildings)
    total_gap = GAP * (n - 1)
    bw = (VIEW_W - 48 - total_gap) / n
    parts: list[str] = []

    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VIEW_W} {VIEW_H}" '
        f'width="{VIEW_W}" height="{VIEW_H}" role="img" '
        f'aria-label="{escape(title or "保有銘柄の時価")}">'
    )
    parts.append(
        '<defs>'
        '<filter id="cy-glow" x="-60%" y="-60%" width="220%" height="220%">'
        '<feGaussianBlur stdDeviation="5" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
        '</defs>'
    )
    parts.extend(_stars(''.join(b.key for b in buildings)))

    for i, b in enumerate(buildings):
        x = 24 + i * (bw + GAP)
        h = building_height(b.value, max_value)
        y = GROUND_Y - h
        cx = x + bw / 2

        # 値ラベル (ビルの上)
        parts.append(
            f'<text x="{cx:.1f}" y="{y - 9:.1f}" fill="{b.color}" font-size="13" '
            f'font-weight="700" text-anchor="middle" '
            f'font-family="monospace">{escape(b.value_text)}</text>'
        )
        # 本体 (屋上だけ角丸 / 底辺は地面に接地)
        parts.append(
            f'<path d="M{x:.1f} {GROUND_Y} V{y + ROOF_R:.1f} '
            f'q0 -{ROOF_R} {ROOF_R} -{ROOF_R} H{x + bw - ROOF_R:.1f} '
            f'q{ROOF_R} 0 {ROOF_R} {ROOF_R} V{GROUND_Y} Z" '
            f'fill="{b.color}" opacity="0.30"/>'
        )
        parts.append(
            f'<path d="M{x:.1f} {GROUND_Y} V{y + ROOF_R:.1f} '
            f'q0 -{ROOF_R} {ROOF_R} -{ROOF_R} H{x + bw - ROOF_R:.1f} '
            f'q{ROOF_R} 0 {ROOF_R} {ROOF_R} V{GROUND_Y}" '
            f'fill="none" stroke="{b.color}" stroke-width="2" filter="url(#cy-glow)"/>'
        )
        parts.extend(_windows(x, y, bw, h, b.key))
        # 直接ラベル (CVD フロア帯のため必須)
        parts.append(
            f'<text x="{cx:.1f}" y="{GROUND_Y + 20:.1f}" fill="{text}" font-size="12" '
            f'text-anchor="middle" font-family="monospace">{escape(b.label)}</text>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{GROUND_Y + 36:.1f}" fill="{muted}" font-size="10.5" '
            f'text-anchor="middle" font-family="monospace">{escape(b.sublabel)}</text>'
        )

    # 地面
    parts.append(
        f'<line x1="12" y1="{GROUND_Y}" x2="{VIEW_W - 12}" y2="{GROUND_Y}" '
        f'stroke="{ground}" stroke-width="1"/>'
    )

    # 凡例 (2カテゴリ以上は常に出す)
    seen: dict[str, str] = {}
    for b in buildings:
        seen.setdefault(b.category, b.color)
    lx = 24
    for category, color in seen.items():
        parts.append(f'<rect x="{lx}" y="{VIEW_H - 16}" width="9" height="9" rx="2" fill="{color}"/>')
        parts.append(
            f'<text x="{lx + 14}" y="{VIEW_H - 8}" fill="{muted}" font-size="11" '
            f'font-family="monospace">{escape(category)}</text>'
        )
        lx += 22 + len(category) * 11

    parts.append('</svg>')
    return ''.join(parts)


def to_img_tag(svg: str, alt: str) -> str:
    """SVG を data URI の <img> に包む。

    Streamlit は生HTMLをサニタイズするため、インラインSVGは描画系の要素
    (filter など) が落ちることがある。画像として渡せば中身は一切触られない。
    """
    if not svg:
        return ''
    b64 = base64.b64encode(svg.encode('utf-8')).decode('ascii')
    return (f'<img src="data:image/svg+xml;base64,{b64}" alt="{escape(alt)}" '
            f'style="width:100%;height:auto;display:block">')
