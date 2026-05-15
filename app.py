"""ポートフォリオ管理 / 日産PSR分析 — Streamlit Cloud版

担保=配当3銘柄、被担保=日産。LTV 55-60%目標、年1,000万ペースで日産買い増し。
データソース: みんかぶ (15分キャッシュ)
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

# =========================
# 定数
# =========================
STOCKS: dict[str, dict] = {
    '2674': {'name': 'ハードオフ', 'shares': 15000, 'dividend': 92, 'role': '担保', 'fallback_price': 2406},
    '8291': {'name': '日産東京HD', 'shares': 50000, 'dividend': 30, 'role': '担保', 'fallback_price': 553},
    '5869': {'name': '早稲田学習研究会', 'shares': 20000, 'dividend': 62, 'role': '担保', 'fallback_price': 1328},
    '7201': {'name': '日産自動車', 'shares': 100000, 'dividend': 0, 'role': '被担保', 'fallback_price': 381},
}
COLLAT_CODES = ['2674', '8291', '5869']
NISSAN_CODE = '7201'

LOAN_BALANCE = 55_000_000     # 5,500万
LOAN_FLOOR = 50_000_000       # 下限 5,000万
CASH_BUFFER = 10_000_000      # 1,000万

FY24 = {'rev': 12.633, 'op': 698, 'opm': 0.55, 'net': -6709, 'eps': -187.08}
FY25 = {'rev': 12.0079, 'op': 580, 'opm': 0.48, 'net': -5331, 'eps': -152.58}
FY26G = {'rev': 13.0, 'op': 2000, 'opm': 1.54, 'net': 200, 'eps': 5.72}

JST = timezone(timedelta(hours=9))
PRICE_RE = re.compile(r'([\d,]+(?:\.\d+)?)')


# =========================
# スクレイピング
# =========================
@st.cache_data(ttl=900, show_spinner='みんかぶから株価取得中...')
def fetch_prices() -> tuple[dict[str, float | None], str]:
    """みんかぶから4銘柄の株価取得。15分キャッシュ。"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; PortfolioDash/1.0)',
        'Accept-Language': 'ja,en;q=0.9',
    }
    results: dict[str, float | None] = {}
    for code in STOCKS.keys():
        try:
            r = requests.get(f'https://minkabu.jp/stock/{code}', headers=headers, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'lxml')
            price = _extract_price(soup)
            results[code] = price
        except Exception:
            results[code] = None
    fetched_at = datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')
    return results, fetched_at


def _extract_price(soup: BeautifulSoup) -> float | None:
    """複数戦略で株価要素を抽出。HTML構造変化への耐性。"""
    selectors = [
        '.stock_price',
        'div.stock_price',
        '[class*="stock_price"]',
        '.fsxl.fwb',
        'meta[itemprop="price"]',
    ]
    for sel in selectors:
        elem = soup.select_one(sel)
        if not elem:
            continue
        text = elem.get('content') if elem.name == 'meta' else elem.get_text(strip=True)
        if not text:
            continue
        m = PRICE_RE.search(text)
        if m:
            try:
                p = float(m.group(1).replace(',', ''))
                if 10 <= p <= 100000:
                    return p
            except ValueError:
                continue
    # フォールバック: JSON-LD構造化データ
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '{}')
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict):
                    offers = item.get('offers') or item.get('mainEntity', {}).get('offers')
                    if offers and 'price' in offers:
                        return float(offers['price'])
        except Exception:
            continue
    return None


# =========================
# ページ設定
# =========================
st.set_page_config(
    page_title="PF管理 / 日産PSR分析",
    page_icon="📊",
    layout="wide",
)

# =========================
# ヘッダー & 価格取得
# =========================
st.title("📊 ポートフォリオ管理 / 日産PSR分析")

prices_raw, fetched_at = fetch_prices()
prices: dict[str, float] = {
    code: (prices_raw.get(code) or STOCKS[code]['fallback_price'])
    for code in STOCKS.keys()
}
failed_codes = [c for c, p in prices_raw.items() if p is None]

col_sub, col_btn = st.columns([4, 1])
with col_sub:
    msg = f"担保=配当3銘柄、被担保=日産。LTV 55-60%目標、年1,000万ペースで日産買い増し  \n"
    msg += f":gray[更新: {fetched_at} (data: みんかぶ)"
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
room60 = cap60 - LOAN_BALANCE
pf_total = collateral + nissan_value + CASH_BUFFER
nav = pf_total - LOAN_BALANCE

c1, c2, c3, c4 = st.columns(4)
c1.metric("担保プール", f"{collateral/10000:,.0f}万", "配当3銘柄", delta_color="off")
c2.metric("被担保 (日産)", f"{nissan_value/10000:,.0f}万",
          f"100,000株 @¥{prices[NISSAN_CODE]:.0f}", delta_color="off")
c3.metric("現金バッファ", f"{CASH_BUFFER/10000:,.0f}万", "健全運用", delta_color="off")
c4.metric("借入残高", f"{LOAN_BALANCE/10000:,.0f}万",
          f"下限 {LOAN_FLOOR/10000:,.0f}万", delta_color="off")

c5, c6, c7, c8 = st.columns(4)
c5.metric("現在LTV", f"{ltv:.1f}%", "目標 55-60%", delta_color="off")
c6.metric("60%枠余力", f"{room60/10000:+,.0f}万",
          "借り増し可能" if room60 >= 0 else "担保増価待ち",
          delta_color="normal" if room60 >= 0 else "inverse")
c7.metric("PF合計", f"{pf_total/10000:,.0f}万", "担保+日産+現金", delta_color="off")
c8.metric("NAV (純資産)", f"{nav/10000:,.0f}万", "PF - 借入", delta_color="off")

# しきい値バー
st.markdown("**しきい値進捗** (借入が枠を何%埋めているか)")
for label, cap, color in [('60%枠', cap60, '🟢'), ('70%枠', cap70, '🟡'), ('85%枠', cap85, '🔴')]:
    fill = LOAN_BALANCE / cap
    st.text(f"{color} {label}: {fill*100:.1f}%")
    st.progress(min(fill, 1.0))


# =========================
# Section 2: DOE配当シナリオ
# =========================
st.header("02  DOE配当シナリオ (時系列累積)", divider='orange')

st.info(
    "**戦略モデル:** 配当3銘柄は純資産増加で増配 → 配当還元法で株価も同率上昇 (デフォルト年5%)。"
    "**LTV目標**に向けて毎年借り増し可能額を算出 → **配当金+借り増し+収入補填**で年1,000万を日産購入。"
    "日産買い増し単価350-400レンジ (デフォルト¥375)。"
)

sc1, sc2, sc3 = st.columns(3)
with sc1:
    div_g = st.slider("配当成長率 (%/年)", 0.0, 15.0, 5.0, 0.5)
    price_g = st.slider("担保株価成長率 (%/年)", -5.0, 15.0, 5.0, 0.5)
with sc2:
    ltv_target = st.slider("LTV目標 (%)", 40.0, 70.0, 57.5, 0.5)
    annual_budget_man = st.slider("年間日産購入額 (万円)", 0, 3000, 1000, 50)
with sc3:
    nis_buy_price = st.slider("日産買い増し単価 (¥)", 200, 800, 375, 5)
    sim_years = st.slider("シミュレーション年数", 1, 10, 5, 1)

# --- 時系列計算 ---
collateral_y = collateral
dividend_y = total_dividend  # 年間配当合計 (円)
loan_y = LOAN_BALANCE
nis_shares_y = STOCKS[NISSAN_CODE]['shares']
total_supplement = 0.0
total_new_loan = 0.0
total_div_recv = 0.0

timeline_rows = [{
    '年': '現在',
    '担保 (万)': f"{collateral_y/10000:,.0f}",
    '配当 (万)': f"{dividend_y/10000:,.0f}",
    '目標借入 (万)': '—',
    '借り増し (万)': '—',
    '収入補填 (万)': '—',
    '日産購入 (万)': '—',
    '累計日産株数': f"{nis_shares_y:,}",
    '借入残 (万)': f"{loan_y/10000:,.0f}",
    'LTV (%)': f"{loan_y/collateral_y*100:.1f}",
}]

for y in range(1, sim_years + 1):
    collateral_y *= 1 + price_g / 100
    dividend_y *= 1 + div_g / 100
    target_loan = max(LOAN_FLOOR, collateral_y * ltv_target / 100)
    new_loan = max(0, target_loan - loan_y)
    nis_purchase = annual_budget_man * 10000
    supplement = nis_purchase - dividend_y - new_loan
    purchase_shares = int(nis_purchase / nis_buy_price) if nis_buy_price > 0 else 0

    loan_y += new_loan
    nis_shares_y += purchase_shares
    total_supplement += supplement
    total_new_loan += new_loan
    total_div_recv += dividend_y

    timeline_rows.append({
        '年': f"+{y}年",
        '担保 (万)': f"{collateral_y/10000:,.0f}",
        '配当 (万)': f"{dividend_y/10000:,.0f}",
        '目標借入 (万)': f"{target_loan/10000:,.0f}",
        '借り増し (万)': f"{new_loan/10000:,.0f}",
        '収入補填 (万)': f"{supplement/10000:+,.0f}",
        '日産購入 (万)': f"{nis_purchase/10000:,.0f}",
        '累計日産株数': f"{nis_shares_y:,}",
        '借入残 (万)': f"{loan_y/10000:,.0f}",
        'LTV (%)': f"{loan_y/collateral_y*100:.1f}",
    })

# 結果カード
final_nis_cost = nis_shares_y * nis_buy_price
final_pf = collateral_y + final_nis_cost + CASH_BUFFER
final_nav = final_pf - loan_y
initial_nav = nav  # Section 1で計算済み

st.subheader(f"{sim_years}年後の状態 (簿価ベース)")
c1, c2, c3, c4 = st.columns(4)
c1.metric(f"{sim_years}年後 担保", f"{collateral_y/10000:,.0f}万",
          f"{(collateral_y/collateral-1)*100:+.1f}%")
c2.metric(f"{sim_years}年後 借入", f"{loan_y/10000:,.0f}万",
          f"累計借り増し {total_new_loan/10000:,.0f}万", delta_color="off")
c3.metric(f"{sim_years}年後 日産株数", f"{nis_shares_y:,}",
          f"+{nis_shares_y - STOCKS[NISSAN_CODE]['shares']:,}株")
c4.metric("日産時価 (簿価)", f"{final_nis_cost/10000:,.0f}万",
          f"@¥{nis_buy_price}基準", delta_color="off")

c5, c6, c7, c8 = st.columns(4)
c5.metric("PF合計 (簿価)", f"{final_pf/10000:,.0f}万")
c6.metric("NAV (簿価)", f"{final_nav/10000:,.0f}万",
          f"{(final_nav/initial_nav-1)*100:+.1f}%")
c7.metric("累計配当受領", f"{total_div_recv/10000:,.0f}万",
          f"{sim_years}年計", delta_color="off")
c8.metric("累計収入補填", f"{total_supplement/10000:,.0f}万",
          f"{sim_years}年計", delta_color="off")

st.subheader("年次推移")
st.dataframe(pd.DataFrame(timeline_rows), use_container_width=True, hide_index=True)
st.caption("収入補填 = 1,000万 - 配当金 - 借り増し額。マイナス = 配当+借り増しが1,000万超過 (余剰)。")

# --- 終了時 日産株価別シナリオ ---
st.subheader("終了時 日産株価別 評価額")
st.info(
    "**FY25-26 (2026/3, 2027/3)** はリストラ+関税継続で**PSR一本評価**。"
    "**FY27 (2028/3) 復配開始**で**PSR+PER併用評価**へ移行。"
)

end_scenarios = [
    ('横ばい', prices[NISSAN_CODE], 'PSR (横ばい)'),
    ('FY26ガイダンス', FY26G['eps'] * 10, 'PER10倍 (FY26EPS)'),
    ('Re:Nissan成功', 1128, 'PSR+PER (復配後)'),
    ('フィッシャー基準', 1672, 'PSR=0.75 (FY25売上)'),
]
end_rows = []
for name, price, axis in end_scenarios:
    nis_val = nis_shares_y * price
    pf_s = collateral_y + nis_val + CASH_BUFFER
    nav_s = pf_s - loan_y
    growth = (nav_s / initial_nav - 1) * 100
    end_rows.append({
        'シナリオ': name,
        '想定株価': f"¥{price:,.0f}",
        '評価軸': axis,
        '日産時価 (万)': f"{nis_val/10000:,.0f}",
        'PF合計 (万)': f"{pf_s/10000:,.0f}",
        'NAV (万)': f"{nav_s/10000:,.0f}",
        'NAV成長率': f"{growth:+.1f}%",
    })
st.dataframe(pd.DataFrame(end_rows), use_container_width=True, hide_index=True)


# =========================
# Section 3: 日産自動車分析
# =========================
st.header("03  日産自動車 (7201) 分析", divider='orange')

st.warning(
    "**評価軸の時間軸:**  \n"
    "• **FY25 (2026/3) 実績**: 売上12.01兆、OP 580億、純損▲5,331億 → **PSR一本評価**  \n"
    "• **FY26 (2027/3) 会社ガイダンス**: 売上13.0兆、OP 2,000億、純利益200億、EPS¥5.72 → "
    "リストラ+米共和党関税継続、**PSR評価継続** (EPS過小でPER 61倍と異常値)  \n"
    "• **FY27 (2028/3) ユーザー想定**: Re:Nissan効果で利益正常化、"
    "**復配開始 → PSR+PER併用評価**へ移行"
)

st.subheader("2025年度 決算ハイライト (2026/5/13)")
c1, c2, c3 = st.columns(3)
c1.metric("売上高", "12.01兆", "-4.9%")
c2.metric("営業利益", "580億", "OPM 0.5%", delta_color="off")
c3.metric("当期純損失", "▲5,331億", "前期▲6,709億 (損失縮小)", delta_color="off")
c4, c5, c6 = st.columns(3)
c4.metric("Q4単四半期OPM", "2.0%", "OP 681億 (勢い)")
c5.metric("ネットキャッシュ", "1.17兆", "自動車事業", delta_color="off")
c6.metric("手元資金", "2.17兆", "+コミット2.31兆", delta_color="off")

st.info(
    "**Re:Nissan進捗:** 10ヶ月で生産7拠点統廃合発表 (17→10)、エンジニアリングコスト18%削減、"
    "20,000人体制適正化。固定費削減**2,000億超**前倒し、変動費**550億**。下期FCF黒字転換。"
)

st.subheader("2026年度 会社ガイダンス")
c1, c2, c3 = st.columns(3)
c1.metric("売上高見通し", "13.00兆", "+8.3%")
c2.metric("営業利益", "2,000億", "OPM 1.5% (+1.0pp)")
c3.metric("当期純利益", "+200億", "黒字転換 (+5,531億)")
c4, c5, c6 = st.columns(3)
c4.metric("EPS", "¥5.72", "前期▲152.58円")
c5.metric("販売台数", "3,300千台", "+4.7%")
c6.metric("配当", "0円", "無配継続 (復配はFY27〜)", delta_color="off")

st.info(
    "**OPブリッジ (580→2,000億):** 為替 -200 / 原材料 -850 / 関税 +300 / 販売 +1,550 / "
    "モノづくり +3,400 / インフレ -600 / 一過性 -1,480 (米環境規制 -1,030、英 -160) / その他 -700。"
    "為替前提: 150円/USD、175円/EUR。"
)

st.subheader("Re:Nissan成功シナリオ (FY27〜ユーザー想定)")
nc1, nc2, nc3 = st.columns(3)
with nc1:
    n_rev = st.slider("FY27〜 売上高 (兆円)", 10.0, 14.0, 13.5, 0.1)
    n_opm = st.slider("FY27〜 営業利益率 (%)", 0.0, 8.0, 5.0, 0.1)
with nc2:
    n_per = st.slider("正常化PER (倍)", 5.0, 20.0, 10.0, 0.5)
    n_net_ratio = st.slider("純利益率/営業利益率 (%)", 30, 80, 60, 5)
with nc3:
    n_shares_oku = st.slider("発行済株式数 (億株)", 30.0, 40.0, 35.9, 0.5)

shares = n_shares_oku * 100_000_000
revenue_yen = n_rev * 1_000_000_000_000
op_profit = revenue_yen * n_opm / 100
net_profit = op_profit * n_net_ratio / 100
eps = net_profit / shares
target_price = eps * n_per
target_mc = target_price * shares
target_psr = target_mc / revenue_yen

cur_price = prices[NISSAN_CODE]
current_mc = cur_price * shares
current_psr = current_mc / (FY25['rev'] * 1_000_000_000_000)
upside = (target_price / cur_price - 1) * 100
# FY26ガイダンスはEPS過小でPERが異常値 → PSR評価。現在PSRを横ばい適用しFY26売上に対応する株価。
guidance_price = current_psr * FY26G['rev'] * 1_000_000_000_000 / shares
guidance_upside = (guidance_price / cur_price - 1) * 100
fisher_theory = revenue_yen * 0.05 * 15
fisher_price = fisher_theory / shares
nissan_new_value = STOCKS[NISSAN_CODE]['shares'] * target_price

c1, c2, c3 = st.columns(3)
c1.metric("想定株価 (FY27〜)", f"¥{target_price:,.0f}", f"{upside:+.1f}%")
c2.metric("ガイダンス株価 (FY26 / PSR)", f"¥{guidance_price:,.0f}", f"{guidance_upside:+.1f}%")
c3.metric("想定営業利益", f"{op_profit/100_000_000:,.0f}億",
          "FY26G 2,000億", delta_color="off")
c4, c5, c6 = st.columns(3)
c4.metric("想定EPS", f"¥{eps:,.1f}", "FY26G ¥5.72", delta_color="off")
c5.metric("日産時価 (現株数100K)", f"{nissan_new_value/10000:,.0f}万",
          "買増前ベース", delta_color="off")
c6.metric("想定時価総額", f"{target_mc/1_000_000_000_000:.2f}兆",
          f"現在 {current_mc/1_000_000_000_000:.2f}兆")

st.subheader("フィッシャーPSR逆算 (FY25売上ベース)")
psr_judge = '買い圏内' if target_psr <= 0.75 else '適正圏' if target_psr <= 1.5 else '割高'
f1, f2, f3, f4 = st.columns(4)
f1.metric("現在PSR", f"{current_psr:.3f}", "基準: 0.75以下で買い", delta_color="off")
f2.metric("成功時PSR", f"{target_psr:.3f}", psr_judge, delta_color="off")
f3.metric("フィッシャー理論時価", f"{fisher_theory/1_000_000_000_000:.1f}兆",
          "売上×5%×PER15", delta_color="off")
f4.metric("フィッシャー理論株価", f"¥{fisher_price:,.0f}",
          "純利益率5%基準", delta_color="off")

# Timeline
st.subheader("業績推移タイムライン")

def _scenario_price(rev_t, opm_pct, shares_n, per, net_ratio_pct):
    op = rev_t * 1e12 * opm_pct / 100
    net_yen = op * net_ratio_pct / 100
    eps_s = net_yen / shares_n
    return eps_s * per, net_yen / 1e8

def _actual_price(net_oku, shares_n, per):
    return (net_oku * 1e8 / shares_n) * per if net_oku > 0 else None

stages_def = [
    ('FY24 実績', FY24['rev'], FY24['opm'], FY24['net'], 'actual', 'PSR'),
    ('FY25 実績', FY25['rev'], FY25['opm'], FY25['net'], 'actual', 'PSR'),
    ('FY26 ガイダンス', FY26G['rev'], FY26G['opm'], FY26G['net'], 'guidance', 'PSR (現在PSR横ばい)'),
    ('FY27 ユーザー想定', n_rev, n_opm, None, 'scenario', 'PSR+PER 復配'),
    ('FY28 正常化', n_rev * 1.03, min(n_opm + 0.5, 8), None, 'scenario', 'PER中心'),
]

tl_rows = []
for label, rev, opm, net, typ, axis in stages_def:
    op = rev * 1e12 * opm / 100
    if typ == 'guidance':
        price = guidance_price  # FY26はPSR評価 (現在PSR横ばい)
        net_oku = net
    elif typ == 'actual':
        price = _actual_price(net, shares, n_per)
        net_oku = net
    else:
        price, net_oku = _scenario_price(rev, opm, shares, n_per, n_net_ratio)

    price_str = f"¥{price:,.0f}" if price else ('赤字' if net_oku and net_oku < 0 else '—')
    net_str = (f"{'+' if net_oku >= 0 else '▲'}{abs(net_oku):,.0f}億"
               if net_oku is not None else '—')
    tl_rows.append({
        '時期': label,
        '売上 (兆)': f"{rev:.2f}",
        '営業利益 (億)': f"{op/1e8:+,.0f}",
        'OPM (%)': f"{opm:.2f}",
        '純損益 (億)': net_str,
        '想定株価': price_str,
        '評価軸': axis,
    })
st.dataframe(pd.DataFrame(tl_rows), use_container_width=True, hide_index=True)

# Summary
st.subheader("サマリー")
opm_diff = n_opm - FY26G['opm']
st.markdown(f"""
会社ガイダンス FY26 OPM {FY26G['opm']:.2f}% / 売上{FY26G['rev']:.2f}兆 → PSR{current_psr:.3f}横ばいで**¥{guidance_price:,.0f}** ({guidance_upside:+.1f}%)。
ユーザー想定 FY27〜 OPM {n_opm:.1f}% → **¥{target_price:.0f}** ({upside:+.1f}%)。
OPM差 **{opm_diff:.1f}pt** がRe:Nissan後の上振れ期待値。

**評価軸の遷移:** FY25-26は赤字/超低EPSのためPSRが第一指標 (現在PSR {current_psr:.3f}、フィッシャー基準0.75以下)。
FY27復配開始でPSR+PER併用評価へ。Section 2の終了時シナリオで日産株価別のNAV感応度確認可能。

**Section 2 連携:** 想定株価¥{target_price:.0f}でRe:Nissan成功シナリオが動作。フィッシャー基準¥{fisher_price:.0f}は超強気ケース。
""")

# Footer
st.markdown("---")
st.caption(
    "Data: みんかぶ (https://minkabu.jp, 15分キャッシュ) / "
    "日産自動車 2025年度決算短信・プレゼン資料 (2026/5/13) / IRBank / 有報第126期"
)
st.caption("実際の株価は市場環境・為替・関税政策等により大きく変動します。投資判断はご自身の責任で。")
