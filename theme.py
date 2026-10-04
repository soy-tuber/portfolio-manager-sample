"""サイバーパンク配色とスタイル (表示専用 / ロジック非依存)

色の方針:
  - **UIクローム** (枠・グロー・見出し・リンク) はフルネオン。これはチャートの
    マークではないので、WCAG コントラストだけを満たせばよい。
  - **チャートのマーク** (折れ線・スカイラインのビル・しきい値線) は
    ダークモードの明度バンド (OKLCH L 0.48-0.67) 内に収め、
    CVD 分離・彩度下限・対地コントラストの検証を通した値だけを使う。
    発光感は色そのものではなく CSS のグロー (drop-shadow) で出す。

検証: 背景 #070b14 に対して全セット PASS。
  チャート4色 隣接 CVD ΔE 9.4 / 通常視 ΔE 21.7
  ステータス3色 全ペア CVD ΔE 9.4
  スカイライン2色 全ペア CVD ΔE 7.8 (6-8のフロア帯 → 直接ラベル併記が必須)
"""

from __future__ import annotations

# --- サーフェス / クローム (チャートマークではない) ---
BG = '#070b14'            # 地
PANEL = '#0d1424'         # パネル・サイドバー
BORDER = '#1b2b45'        # レール・罫線
TEXT = '#d8e6f2'          # 本文        15.5:1
TEXT_MUTED = '#7b93ad'    # 補足         6.2:1
NEON_CYAN = '#00d9ff'     # 主アクセント 11.6:1
NEON_MAGENTA = '#ff2e97'  # 副アクセント  5.7:1

# --- チャートのマーク (検証済み / 明度バンド内) ---
SERIES = '#0da4cf'          # 担保プール 折れ線
SKYLINE_COLLAT = '#0da4cf'  # 担保銘柄のビル
SKYLINE_OTHER = '#fe29ab'   # LTV対象外のビル

# しきい値ごとのステータス色 (good / warning / critical)。
# 明度を散らすことで2型色覚でも分離する (同一明度だと緑と赤が潰れる)。
STATUS = {
    0.60: '#087736',   # L 0.50
    0.70: '#b88a01',   # L 0.66
    0.85: '#d90625',   # L 0.56
}

FONT_STACK = ("'JetBrains Mono', 'Share Tech Mono', ui-monospace, "
              "SFMono-Regular, Menlo, Consolas, monospace")


def css() -> str:
    """コンソール筐体・走査線・グリッド・ネオングローの CSS。"""
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');

:root {{
  --cy-bg: {BG};
  --cy-panel: {PANEL};
  --cy-border: {BORDER};
  --cy-text: {TEXT};
  --cy-muted: {TEXT_MUTED};
  --cy-cyan: {NEON_CYAN};
  --cy-magenta: {NEON_MAGENTA};
}}

html, body, [data-testid="stAppViewContainer"] {{
  background-color: var(--cy-bg);
  font-family: {FONT_STACK};
  font-size: 13px;
}}

/* 40px グリッド + 走査線。下地なのでポインタは通す */
[data-testid="stAppViewContainer"]::before {{
  content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background-image:
    linear-gradient(rgba(0, 217, 255, .045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 217, 255, .045) 1px, transparent 1px);
  background-size: 40px 40px;
}}
[data-testid="stAppViewContainer"]::after {{
  content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 1;
  background: repeating-linear-gradient(
    180deg, rgba(0, 0, 0, .22) 0 1px, transparent 1px 3px);
  mix-blend-mode: multiply;
}}
[data-testid="stMain"], [data-testid="stSidebar"] {{ position: relative; z-index: 2; }}

/* コンソール筐体: 本文の左右にネオンのレールを立てる */
[data-testid="stMainBlockContainer"] {{
  border-left: 1px solid var(--cy-border);
  border-right: 1px solid var(--cy-border);
  box-shadow: inset 1px 0 12px -6px var(--cy-cyan), inset -1px 0 12px -6px var(--cy-cyan);
  padding-left: 2.2rem; padding-right: 2.2rem;
}}

[data-testid="stSidebar"] {{
  background-color: var(--cy-panel);
  border-right: 1px solid var(--cy-border);
}}

/* 見出しはターミナルのプロンプト行に見せる */
h1, h2, h3 {{ font-family: {FONT_STACK}; letter-spacing: .02em; }}
h1 {{
  font-size: 1.5rem; color: var(--cy-cyan);
  text-shadow: 0 0 12px rgba(0, 217, 255, .55);
}}
h1::before {{ content: "> "; color: var(--cy-magenta); }}
/* 点滅カーソル */
h1::after {{
  content: "_"; color: var(--cy-cyan); margin-left: .15em;
  animation: cy-blink 1.1s step-end infinite;
}}
@keyframes cy-blink {{ 50% {{ opacity: 0; }} }}
h2 {{ font-size: 1.2rem; color: var(--cy-text); }}
h2::before {{ content: "// "; color: var(--cy-muted); }}
h3 {{ font-size: 1.02rem; color: var(--cy-text); }}

/* 指標カード: 枠 + 内側グロー */
[data-testid="stMetric"] {{
  background: linear-gradient(180deg, rgba(0,217,255,.045), transparent 70%);
  border: 1px solid var(--cy-border);
  border-left: 2px solid var(--cy-cyan);
  border-radius: 2px; padding: .55rem .7rem;
}}
[data-testid="stMetricValue"] {{
  font-size: 1.3rem; color: var(--cy-cyan);
  text-shadow: 0 0 10px rgba(0, 217, 255, .4);
}}
[data-testid="stMetricLabel"] {{ font-size: .78rem; color: var(--cy-muted); }}
[data-testid="stMetricDelta"] {{ font-size: .72rem; }}

/* 表 */
.stDataFrame, .stDataFrame td, .stDataFrame th {{ font-size: .82rem; }}

/* 進捗バーをネオンに */
[data-testid="stProgress"] div[role="progressbar"] > div {{
  background-image: linear-gradient(90deg, var(--cy-cyan), var(--cy-magenta));
  box-shadow: 0 0 10px rgba(0, 217, 255, .45);
}}

/* 注意喚起ブロックは角を落として枠線だけ光らせる */
[data-testid="stAlertContainer"] {{
  border-radius: 2px; border-left-width: 3px;
}}

/* ボタン / リンクボタン */
.stButton button, .stLinkButton a, [data-testid="stDownloadButton"] button {{
  font-family: {FONT_STACK};
  border: 1px solid var(--cy-border);
  border-radius: 2px;
  background: var(--cy-panel);
  color: var(--cy-text);
}}
.stButton button:hover, .stLinkButton a:hover,
[data-testid="stDownloadButton"] button:hover {{
  border-color: var(--cy-cyan); color: var(--cy-cyan);
  box-shadow: 0 0 12px -2px var(--cy-cyan);
}}

/* 動きを減らす設定の人には点滅と走査線を出さない */
@media (prefers-reduced-motion: reduce) {{
  h1::after {{ animation: none; }}
  [data-testid="stAppViewContainer"]::after {{ display: none; }}
}}
</style>
"""
