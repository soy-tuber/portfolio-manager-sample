"""ポートフォリオ管理 / 日産PSR分析 — Streamlit Cloud版

担保=配当5銘柄。日産は担保差入れ済みだがLTV計算には算入しない(LTV対象外)。
LTV 55-60%目標。
データソース: Yahoo Finance (15分キャッシュ)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st

# =========================
# 定数
# =========================
STOCKS: dict[str, dict] = {
    '2674': {'name': 'ハードオフ', 'shares': 15000, 'dividend': 92, 'role': '担保', 'fallback_price': 2406},
    '8291': {'name': '日産東京HD', 'shares': 50000, 'dividend': 30, 'role': '担保', 'fallback_price': 553},
    '5869': {'name': '早稲田学習研究会', 'shares': 20000, 'dividend': 62, 'role': '担保', 'fallback_price': 1328},
    '7203': {'name': 'トヨタ自動車', 'shares': 5000, 'dividend': 100, 'role': '担保', 'fallback_price': 2849},
    '7222': {'name': '日産車体', 'shares': 15000, 'dividend': 40, 'role': '担保', 'fallback_price': 1000},
    '7201': {'name': '日産自動車', 'shares': 100000, 'dividend': 0, 'role': 'LTV対象外', 'fallback_price': 381},
}
COLLAT_CODES = ['2674', '8291', '5869', '7203', '7222']
NISSAN_CODE = '7201'

LOAN_BALANCE = 80_000_000     # 8,000万
LOAN_FLOOR = 50_000_000       # 下限 5,000万
CASH_BUFFER = 6_000_000       # 600万


JST = timezone(timedelta(hours=9))


# =========================
# 株価取得 (Yahoo Finance)
# =========================
@st.cache_data(ttl=900, show_spinner='Yahoo Financeから株価取得中...')
def fetch_prices() -> tuple[dict[str, float | None], str]:
    """Yahoo Finance から6銘柄の株価取得。15分キャッシュ。

    みんかぶのスクレイピングは Streamlit Cloud (海外サーバー) から弾かれるため、
    海外からでも日本株 (.T) を返す Yahoo Finance の chart API を使用する。
    """
    headers = {'User-Agent': 'Mozilla/5.0'}
    results: dict[str, float | None] = {}
    for code in STOCKS.keys():
        try:
            r = requests.get(
                f'https://query1.finance.yahoo.com/v8/finance/chart/{code}.T',
                headers=headers, timeout=15,
            )
            r.raise_for_status()
            meta = r.json()['chart']['result'][0]['meta']
            price = meta.get('regularMarketPrice')
            results[code] = float(price) if price is not None else None
        except Exception:
            results[code] = None
    fetched_at = datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')
    return results, fetched_at


# =========================
# ヘッダー & 価格取得
# =========================
# set_page_config / 共通CSS は app.py (エントリ) 側で実行済み。
# 記事は別リポジトリ (soy-tuber/nissan-notes) の GitHub Pages で公開
PAGES_BASE = "https://soy-tuber.github.io/nissan-notes/"

st.title("📊 ポートフォリオ管理")

with st.expander("📚 参考資料 (対話・記事・ロードマップ)", expanded=False):
    st.caption("記事は GitHub Pages に移管しました — https://soy-tuber.github.io/nissan-notes/")
    ref_cols = st.columns(2)
    with ref_cols[0]:
        st.link_button("📖 現場と数字で日産を読む",
                       PAGES_BASE + "nissan_dialogue.html", use_container_width=True)
        st.link_button("🔋 デュアルコア・モビリティ【改訂版】",
                       PAGES_BASE + "dual_core_mobility.html", use_container_width=True)
        st.link_button("🇨🇳 スティーブン・マーと中国日産",
                       PAGES_BASE + "stephen_ma_china.html", use_container_width=True)
    with ref_cols[1]:
        st.link_button("🤖 Wayve × Nissan ロードマップ",
                       PAGES_BASE + "wayve_roadmap.html", use_container_width=True)
        st.link_button("📄 デュアルコア・モビリティ【初版PDF】",
                       PAGES_BASE + "dual_core_shinsho.pdf", use_container_width=True)

prices_raw, fetched_at = fetch_prices()
prices: dict[str, float] = {
    code: (prices_raw.get(code) or STOCKS[code]['fallback_price'])
    for code in STOCKS.keys()
}
failed_codes = [c for c, p in prices_raw.items() if p is None]

col_sub, col_btn = st.columns([4, 1])
with col_sub:
    msg = f"担保=配当5銘柄。日産は担保差入れ済みだがLTV対象外。LTV 55-60%目標。  \n"
    msg += f":gray[更新: {fetched_at} (data: Yahoo Finance)"
    if failed_codes:
        names = ', '.join(STOCKS[c]['name'] for c in failed_codes)
        msg += f" / フォールバック適用: {names}"
    msg += "]"
    st.markdown(msg)
with col_btn:
    if st.button("🔄 再取得", use_container_width=True):
        fetch_prices.clear()
        st.rerun()


# =========================
# Section 1: ポートフォリオ管理
# =========================
st.header("01  ポートフォリオ管理", divider='orange')

# --- 保有銘柄テーブル ---
st.subheader("現在の保有銘柄")
total_value = sum(STOCKS[c]['shares'] * prices[c] for c in STOCKS)
total_dividend = sum(STOCKS[c]['shares'] * STOCKS[c]['dividend'] for c in STOCKS)

rows = []
for code, info in STOCKS.items():
    val = info['shares'] * prices[code]
    rows.append({
        '銘柄': f"{code} {info['name']}",
        '株数': f"{info['shares']:,}",
        '株価': f"¥{prices[code]:,.0f}",
        '時価 (万)': f"{val/10000:,.0f}",
        '配当 (¥)': f"{info['dividend']}" if info['dividend'] else '—',
        '比率': f"{val/total_value*100:.1f}%",
        '性格': info['role'],
    })
rows.append({
    '銘柄': '**合計**', '株数': '', '株価': '',
    '時価 (万)': f"**{total_value/10000:,.0f}**",
    '配当 (¥)': f"**{total_dividend:,}**",
    '比率': '100%', '性格': '',
})
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# --- 余力メーター ---
st.subheader("余力メーター")
st.info(
    "**運用ルール:** 借入5,000万を**下限**として維持。**LTV 55-60%目標**で担保増価に応じて借り増し → 日産買い増し（年1,000万ペース）。  \n"
    "Rakuten Bank: **60% 通常 / 70% 警告 / 85% 強制決済**"
)

collateral = sum(STOCKS[c]['shares'] * prices[c] for c in COLLAT_CODES)
nissan_value = STOCKS[NISSAN_CODE]['shares'] * prices[NISSAN_CODE]
ltv = LOAN_BALANCE / collateral * 100
cap60, cap70, cap85 = collateral * 0.6, collateral * 0.7, collateral * 0.85
room70 = cap70 - LOAN_BALANCE
pf_total = collateral + nissan_value + CASH_BUFFER
nav = pf_total - LOAN_BALANCE

c1, c2, c3, c4 = st.columns(4)
c1.metric("担保プール", f"{collateral/10000:,.0f}万", "配当5銘柄", delta_color="off")
c2.metric("日産 (LTV対象外)", f"{nissan_value/10000:,.0f}万",
          f"100,000株 @¥{prices[NISSAN_CODE]:.0f}", delta_color="off")
c3.metric("現金バッファ", f"{CASH_BUFFER/10000:,.0f}万", "健全運用", delta_color="off")
c4.metric("借入残高", f"{LOAN_BALANCE/10000:,.0f}万",
          f"下限 {LOAN_FLOOR/10000:,.0f}万", delta_color="off")

c5, c6, c7, c8 = st.columns(4)
c5.metric("現在LTV", f"{ltv:.1f}%", "目標 55-60%", delta_color="off")
c6.metric("70%枠余力", f"{room70/10000:+,.0f}万",
          "借り増し可能" if room70 >= 0 else "担保増価待ち",
          delta_color="normal" if room70 >= 0 else "inverse")
c7.metric("PF合計", f"{pf_total/10000:,.0f}万", "担保+日産+現金", delta_color="off")
c8.metric("NAV (純資産)", f"{nav/10000:,.0f}万", "PF - 借入", delta_color="off")

# しきい値バー
st.markdown("**しきい値進捗** (借入が枠を何%埋めているか)")
for label, cap, color in [('60%枠', cap60, '🟢'), ('70%枠', cap70, '🟡'), ('85%枠', cap85, '🔴')]:
    fill = LOAN_BALANCE / cap
    st.text(f"{color} {label}: {fill*100:.1f}%")
    st.progress(min(fill, 1.0))


# =========================
# Section 2: 配当 / 担保推移
# =========================
st.header("02  配当 / 担保推移シミュレーション", divider='orange')

st.info(
    "**モデル:** 配当5銘柄は純資産増加で増配 → 配当還元法で株価も同率上昇 (デフォルト年5%)。"
    "担保増価で LTV が低下し、70%枠余力が拡大する推移を確認できます。借入残高は固定。"
)

sc1, sc2, sc3 = st.columns(3)
with sc1:
    div_g = st.slider("配当成長率 (%/年)", 0.0, 15.0, 5.0, 0.5)
with sc2:
    price_g = st.slider("担保株価成長率 (%/年)", -5.0, 15.0, 5.0, 0.5)
with sc3:
    sim_years = st.slider("シミュレーション年数", 1, 10, 5, 1)

# --- 時系列計算 ---
collateral_y = collateral
dividend_y = total_dividend
total_div_recv = 0.0

timeline_rows = [{
    '年': '現在',
    '担保 (万)': f"{collateral_y/10000:,.0f}",
    '年間配当 (万)': f"{dividend_y/10000:,.0f}",
    'LTV (%)': f"{LOAN_BALANCE/collateral_y*100:.1f}",
    '70%枠余力 (万)': f"{(collateral_y*0.7 - LOAN_BALANCE)/10000:+,.0f}",
}]

for y in range(1, sim_years + 1):
    collateral_y *= 1 + price_g / 100
    dividend_y *= 1 + div_g / 100
    total_div_recv += dividend_y

    timeline_rows.append({
        '年': f"+{y}年",
        '担保 (万)': f"{collateral_y/10000:,.0f}",
        '年間配当 (万)': f"{dividend_y/10000:,.0f}",
        'LTV (%)': f"{LOAN_BALANCE/collateral_y*100:.1f}",
        '70%枠余力 (万)': f"{(collateral_y*0.7 - LOAN_BALANCE)/10000:+,.0f}",
    })

# 結果カード
st.subheader(f"{sim_years}年後の状態")
c1, c2, c3, c4 = st.columns(4)
c1.metric(f"{sim_years}年後 担保", f"{collateral_y/10000:,.0f}万",
          f"{(collateral_y/collateral-1)*100:+.1f}%")
c2.metric(f"{sim_years}年後 年間配当", f"{dividend_y/10000:,.0f}万",
          f"{(dividend_y/total_dividend-1)*100:+.1f}%")
c3.metric(f"{sim_years}年後 LTV", f"{LOAN_BALANCE/collateral_y*100:.1f}%",
          f"現在 {ltv:.1f}%", delta_color="off")
c4.metric(f"{sim_years}年後 70%枠余力",
          f"{(collateral_y*0.7 - LOAN_BALANCE)/10000:+,.0f}万",
          f"現在 {room70/10000:+,.0f}万", delta_color="off")

st.caption(f"累計配当受領 ({sim_years}年計): {total_div_recv/10000:,.0f}万")

st.subheader("年次推移")
st.dataframe(pd.DataFrame(timeline_rows), use_container_width=True, hide_index=True)


# =========================
# 日産分析は GitHub Pages へ移管
# =========================
st.header("03  日産自動車 (7201) 分析", divider='orange')
st.markdown(
    "日産の決算分析・損益分岐点分析・月次データは、ポートフォリオ管理とは独立した内容のため "
    f"[日産分析ノート]({PAGES_BASE}) に移管しました。"
)
n1, n2, n3 = st.columns(3)
with n1:
    st.link_button("📈 日産PSR分析", PAGES_BASE + "psr.html", use_container_width=True)
with n2:
    st.link_button("📐 CVPシナリオ分析", PAGES_BASE + "cvp.html", use_container_width=True)
with n3:
    st.link_button("📅 月次 生産・販売・輸出", PAGES_BASE + "monthly.html", use_container_width=True)

# Footer
st.markdown("---")
st.caption(
    "Data: Yahoo Finance (15分キャッシュ)。"
    "日産の決算・月次データは 日産分析ノート を参照。"
)
st.caption("実際の株価は市場環境・為替・関税政策等により大きく変動します。投資判断はご自身の責任で。")
