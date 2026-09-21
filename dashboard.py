"""ポートフォリオ管理 / 底値分析 — Streamlit Cloud版

担保=配当4銘柄。日産は担保差入れ済みだがLTV計算には算入しない(LTV対象外)。
LTV 55-60%目標。
データソース: Yahoo Finance (現値15分 / 日足1時間キャッシュ)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st

import bottom_analysis as ba

# =========================
# 定数
# =========================
STOCKS: dict[str, dict] = {
    '2674': {'name': 'ハードオフ', 'shares': 15000, 'dividend': 92, 'role': '担保', 'fallback_price': 2406},
    '8291': {'name': '日産東京HD', 'shares': 50000, 'dividend': 30, 'role': '担保', 'fallback_price': 553},
    '5869': {'name': '早稲田学習研究会', 'shares': 20000, 'dividend': 62, 'role': '担保', 'fallback_price': 1328},
    '7222': {'name': '日産車体', 'shares': 15000, 'dividend': 40, 'role': '担保', 'fallback_price': 1000},
    '7201': {'name': '日産自動車', 'shares': 100000, 'dividend': 0, 'role': 'LTV対象外', 'fallback_price': 381},
}
COLLAT_CODES = ['2674', '8291', '5869', '7222']
NISSAN_CODE = '7201'

LOAN_BALANCE = 65_000_000     # 6,500万 (トヨタ売却代金1,500万を返済充当後)
LOAN_FLOOR = 50_000_000       # 下限 5,000万
CASH_BUFFER = 6_000_000       # 600万
ANNUAL_ADD_BUDGET = 10_000_000  # 日産買い増し 年1,000万ペース

# 確定済みの売買 (新しい順)。売却代金の使途まで記録する。
REALIZED_TRADES: list[dict] = [
    {
        'date': '2026-09-18',
        'code': '7203',
        'name': 'トヨタ自動車',
        'action': '売却 (成行)',
        'shares': 5000,
        'proceeds': 15_000_000,   # 売却代金 = 借入返済額
        'gain': 700_000,          # 確定益
        'use': '借入返済',
        'note': '担保プールから除外。借入 8,000万 → 6,500万。',
    },
]

# LTV しきい値 (Rakuten Bank) と表示色。
# 色はステータス配色の固定値 (good / warning / critical)。
# Streamlit の Light / Dark どちらでも使える値を採用し、
# 記号+ラベル+y軸上の位置でも区別できるようにしている (色単独に意味を持たせない)。
LTV_THRESHOLDS = [
    (0.60, '🟢', '通常', '#0ca30c'),
    (0.70, '🟡', '警告', '#fab219'),
    (0.85, '🔴', '強制決済', '#d03b3b'),
]
SERIES_COLOR = '#2a78d6'   # カテゴリ配色スロット1 (blue)

PERIOD_OPTIONS = {'1年': '1y', '2年': '2y', '5年': '5y', '10年': '10y'}

JST = timezone(timedelta(hours=9))


# =========================
# 株価取得 (Yahoo Finance)
# =========================
@st.cache_data(ttl=900, show_spinner='Yahoo Financeから株価取得中...')
def fetch_prices() -> tuple[dict[str, float | None], str]:
    """Yahoo Finance から保有銘柄の現値取得。15分キャッシュ。

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


@st.cache_data(ttl=3600, show_spinner='日足データ取得中...')
def fetch_daily_bars(codes: tuple[str, ...],
                     period: str) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """同じ chart API に range/interval を付けて日足 OHLC を取得。1時間キャッシュ。

    現値取得と同じエンドポイントなので追加の依存パッケージは不要。
    """
    headers = {'User-Agent': 'Mozilla/5.0'}
    bars: dict[str, pd.DataFrame] = {}
    failed: list[str] = []
    for code in codes:
        try:
            r = requests.get(
                f'https://query1.finance.yahoo.com/v8/finance/chart/{code}.T',
                params={'range': period, 'interval': '1d'},
                headers=headers, timeout=20,
            )
            r.raise_for_status()
            bars[code] = ba.parse_chart_bars(r.json())
        except Exception:
            failed.append(code)
    return bars, failed


def yen_man(value: float) -> str:
    """円 → 万円表記。"""
    return f"{value/10000:,.0f}万"


def fmt_date(value) -> str:
    return value.strftime('%Y-%m-%d') if value is not None else '—'


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
    msg = f"担保=配当{len(COLLAT_CODES)}銘柄。日産は担保差入れ済みだがLTV対象外。LTV 55-60%目標。  \n"
    msg += f":gray[更新: {fetched_at} (data: Yahoo Finance)"
    if failed_codes:
        names = ', '.join(STOCKS[c]['name'] for c in failed_codes)
        msg += f" / フォールバック適用: {names}"
    msg += "]"
    st.markdown(msg)
with col_btn:
    if st.button("🔄 再取得", use_container_width=True):
        fetch_prices.clear()
        fetch_daily_bars.clear()
        st.rerun()


# =========================
# 共通の集計値
# =========================
collateral = sum(STOCKS[c]['shares'] * prices[c] for c in COLLAT_CODES)
nissan_value = STOCKS[NISSAN_CODE]['shares'] * prices[NISSAN_CODE]
ltv = LOAN_BALANCE / collateral * 100
cap60, cap70, cap85 = collateral * 0.6, collateral * 0.7, collateral * 0.85
room70 = cap70 - LOAN_BALANCE
pf_total = collateral + nissan_value + CASH_BUFFER
nav = pf_total - LOAN_BALANCE


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

# --- 確定損益 / 借入返済 ---
if REALIZED_TRADES:
    st.subheader("直近の確定売買")

    repaid = sum(t['proceeds'] for t in REALIZED_TRADES if t['use'] == '借入返済')
    realized_gain = sum(t['gain'] for t in REALIZED_TRADES)
    # 売却前の姿を再構成: 売却株は担保プールに入っていたので、
    # 代金ぶんを担保と借入の両方に戻す (残り銘柄は現値のまま = 概算)。
    pre_collateral = collateral + repaid
    pre_loan = LOAN_BALANCE + repaid
    pre_ltv = pre_loan / pre_collateral * 100

    trade_rows = [{
        '約定日': t['date'],
        '銘柄': f"{t['code']} {t['name']}",
        '区分': t['action'],
        '株数': f"{t['shares']:,}",
        '代金 (万)': f"{t['proceeds']/10000:,.0f}",
        '単価 (¥)': f"{t['proceeds']/t['shares']:,.0f}",
        '確定損益 (万)': f"{t['gain']/10000:+,.0f}",
        '代金の使途': t['use'],
    } for t in REALIZED_TRADES]
    st.dataframe(pd.DataFrame(trade_rows), use_container_width=True, hide_index=True)

    t1, t2, t3, t4 = st.columns(4)
    t1.metric("確定益 (累計)", f"{realized_gain/10000:+,.0f}万", "実現ベース", delta_color="off")
    t2.metric("借入返済 (充当)", f"−{repaid/10000:,.0f}万",
              f"{pre_loan/10000:,.0f}万 → {LOAN_BALANCE/10000:,.0f}万", delta_color="off")
    t3.metric("売却後LTV", f"{ltv:.1f}%", f"売却前 {pre_ltv:.1f}% 相当", delta_color="off")
    t4.metric("LTV改善", f"{ltv - pre_ltv:+.1f}pt", "目標 55-60%へ", delta_color="off")

    for t in REALIZED_TRADES:
        if t.get('note'):
            st.caption(f"{t['date']} {t['name']}: {t['note']}")
    st.caption(
        "売却前LTVは「売却銘柄の時価=売却代金」「残り銘柄は現値」とみなした概算です。"
    )

# --- 余力メーター ---
st.subheader("余力メーター")
st.info(
    "**運用ルール:** 借入5,000万を**下限**として維持。**LTV 55-60%目標**で担保増価に応じて借り増し → 日産買い増し（年1,000万ペース）。  \n"
    "Rakuten Bank: **60% 通常 / 70% 警告 / 85% 強制決済**"
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("担保プール", f"{collateral/10000:,.0f}万", f"配当{len(COLLAT_CODES)}銘柄", delta_color="off")
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
for threshold, icon, _label, _color in LTV_THRESHOLDS:
    cap = collateral * threshold
    fill = LOAN_BALANCE / cap
    st.text(f"{icon} {threshold*100:.0f}%枠: {fill*100:.1f}%")
    st.progress(min(fill, 1.0))


# =========================
# Section 2: 配当 / 担保推移
# =========================
st.header("02  配当 / 担保推移シミュレーション", divider='orange')

st.info(
    f"**モデル:** 配当{len(COLLAT_CODES)}銘柄は純資産増加で増配 → 配当還元法で株価も同率上昇 (デフォルト年5%)。"
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
# Section 3: 底値分析
# =========================
st.header("03  底値分析", divider='orange')

st.info(
    "**考え方:** 単一銘柄の「◯円以下だった日数」ではなく、保有株数で重み付けした "
    "**担保プールの合成日次系列**を作り、現在の借入 "
    f"{LOAN_BALANCE/10000:,.0f}万 に対して LTV しきい値 (60/70/85%) が過去どれだけ"
    "踏まれていたかを数えます。日数はすべて**取引日**ベース (暦日ではない)。  \n"
    "判定にはその日の**安値**を使います（ザラ場で触った水準まで拾う）。"
)

bp1, bp2 = st.columns([1, 3])
with bp1:
    period_label = st.selectbox("対象期間", list(PERIOD_OPTIONS.keys()), index=1)
with bp2:
    run_bottom = st.toggle(
        "日足を取得して集計する", value=False,
        help=f"Yahoo Finance の chart API に{len(STOCKS)}銘柄ぶんリクエストします (1時間キャッシュ)",
    )

if not run_bottom:
    st.caption("トグルを ON にすると日足を取得して集計します（現値表示より重いため既定は OFF）。")
else:
    bars, bar_failed = fetch_daily_bars(tuple(STOCKS.keys()), PERIOD_OPTIONS[period_label])
    if bar_failed:
        st.warning(
            "日足を取得できませんでした: "
            + ', '.join(f"{c} {STOCKS[c]['name']}" for c in bar_failed)
        )

    # --- (a) 担保プール 底値ストレステスト ---
    st.subheader("担保プール 底値ストレステスト")
    pool = None
    try:
        pool = ba.build_pool_series(bars, {c: STOCKS[c]['shares'] for c in COLLAT_CODES})
    except ValueError as error:
        st.error(f"担保プールを合成できませんでした: {error}")

    if pool is not None:
        pool_low = pool['pool_low']
        pool_min = float(pool_low.min())
        pool_min_date = pool_low.idxmin()
        ltv_at_min = LOAN_BALANCE / pool_min * 100
        drawdown = ba.worst_drawdown(pool['pool_close'])

        holdings_note = ', '.join(
            f"{STOCKS[c]['name']} {STOCKS[c]['shares']:,}株" for c in COLLAT_CODES
        )
        st.caption(
            f"共通営業日 {len(pool):,} 取引日 "
            f"({fmt_date(pool.index[0])} 〜 {fmt_date(pool.index[-1])})。"
            f"現在の株数 ({holdings_note}) を過去の株価に当てはめた仮想プールです。"
        )

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("現在の担保プール", yen_man(collateral), f"現在LTV {ltv:.1f}%", delta_color="off")
        p2.metric("期間最安プール", yen_man(pool_min), fmt_date(pool_min_date), delta_color="off")
        p3.metric("最安時の想定LTV", f"{ltv_at_min:.1f}%",
                  f"現在比 {ltv_at_min - ltv:+.1f}pt", delta_color="inverse")
        p4.metric("最大DD (終値)", f"{drawdown['depth']*100:.1f}%",
                  f"{fmt_date(drawdown['peak_date'])} → {fmt_date(drawdown['trough_date'])}",
                  delta_color="off")

        scan = ba.ltv_threshold_scan(
            pool_low, current_pool=collateral, loan=LOAN_BALANCE,
            thresholds=tuple(t for t, _i, _l, _c in LTV_THRESHOLDS),
        )
        meta = {t: (icon, label, color) for t, icon, label, color in LTV_THRESHOLDS}

        scan_rows = []
        for row in scan:
            icon, label, _color = meta[row['threshold']]
            scan_rows.append({
                'しきい値': f"{icon} {row['threshold']*100:.0f}% ({label})",
                '抵触プール水準 (万)': f"{row['trigger_pool']/10000:,.0f}",
                '現在プールからの距離': f"{row['gap']*100:+.1f}%",
                '期間中の抵触日数': f"{row['days']:,}",
                '抵触率': f"{row['ratio']*100:.1f}%",
                '最長連続 (取引日)': f"{row['longest_run']:,}",
                '直近の抵触日': fmt_date(row['last_date']),
            })
        st.dataframe(pd.DataFrame(scan_rows), use_container_width=True, hide_index=True)
        st.caption(
            "「現在プールからの距離」がマイナスなら、そこまで下げないと抵触しない余裕。"
            "プラスならすでに超過している水準です。"
        )

        # 推移チャート (単位は万円のみ = 1軸。しきい値線は記号+ラベル+高さでも区別可能)
        chart = pd.DataFrame({'担保プール 終値 (万)': pool['pool_close'] / 10000})
        colors = [SERIES_COLOR]
        for row in scan:
            icon, label, color = meta[row['threshold']]
            name = (f"{icon} {row['threshold']*100:.0f}%抵触水準 "
                    f"{row['trigger_pool']/10000:,.0f}万")
            chart[name] = row['trigger_pool'] / 10000
            colors.append(color)
        st.line_chart(chart, color=colors, use_container_width=True)

        csv = pool.assign(
            pool_low_man=pool['pool_low'] / 10000,
            pool_close_man=pool['pool_close'] / 10000,
            ltv_on_low=LOAN_BALANCE / pool['pool_low'] * 100,
        ).to_csv().encode('utf-8-sig')
        st.download_button(
            "⬇️ 担保プール日次系列 (CSV)", csv,
            file_name=f"collateral_pool_{PERIOD_OPTIONS[period_label]}.csv",
            mime='text/csv',
        )

    # --- (b) 銘柄別 底値マップ ---
    st.subheader("銘柄別 底値マップ")
    near_pct = st.slider("「安値圏」の幅 (期間安値から+X%以内)", 1.0, 30.0, 10.0, 1.0)

    profile_rows = []
    for code, info in STOCKS.items():
        if code not in bars:
            continue
        profile = ba.bottom_profile(bars[code], prices[code], near_pct=near_pct)
        profile_rows.append({
            '銘柄': f"{code} {info['name']}",
            '性格': info['role'],
            '現値 (¥)': f"{prices[code]:,.0f}",
            '期間安値 (¥)': f"{profile['low']:,.0f}",
            '安値日': fmt_date(profile['low_date']),
            '安値からの上昇': f"{profile['above_low']*100:+.1f}%",
            '期間高値 (¥)': f"{profile['high']:,.0f}",
            '高値からの下落': f"{profile['below_high']*100:+.1f}%",
            '安値圏の上限 (¥)': f"{profile['near_level']:,.0f}",
            '安値圏日数': f"{profile['near_days']:,}",
            '取引日数': f"{profile['trading_days']:,}",
        })
    if profile_rows:
        st.dataframe(pd.DataFrame(profile_rows), use_container_width=True, hide_index=True)
        st.caption(
            "「安値圏日数」= 期間安値から指定幅以内の安値を付けた取引日数。"
            "その水準を拾う機会が実際に何日あったかの目安。"
        )

    # --- (c) 日産 買い増しラダー ---
    st.subheader(f"日産 買い増しラダー (年{ANNUAL_ADD_BUDGET/10000:,.0f}万ペース)")
    if NISSAN_CODE not in bars:
        st.warning("日産の日足が取得できていないためラダーを計算できません。")
    else:
        nissan_bars = bars[NISSAN_CODE]
        nissan_price = prices[NISSAN_CODE]

        def nice_step(price: float) -> int:
            for candidate in (1, 2, 5, 10, 25, 50, 100, 250, 500):
                if price * 0.05 <= candidate:
                    return candidate
            return 1000

        step_default = nice_step(nissan_price)
        top_default = int(nissan_price // step_default * step_default) or step_default

        l1, l2, l3 = st.columns(3)
        with l1:
            ladder_top = st.number_input("ラダー上限 (円)", min_value=1,
                                         value=int(top_default), step=step_default)
        with l2:
            ladder_step = st.number_input("刻み (円)", min_value=1,
                                          value=int(step_default), step=1)
        with l3:
            ladder_count = st.number_input("本数", min_value=2, max_value=12, value=6, step=1)

        ladder_rows = []
        for level in ba.price_ladder(float(ladder_top), float(ladder_step), int(ladder_count)):
            hit = ba.days_at_or_below(nissan_bars['low'], level)
            shares = ba.lot_size_for_budget(level, ANNUAL_ADD_BUDGET)
            ladder_rows.append({
                '指値 (¥)': f"{level:,.0f}",
                '現値比': f"{(level/nissan_price - 1)*100:+.1f}%" if nissan_price else '—',
                '到達日数': f"{hit['days']:,}",
                '到達率': f"{hit['ratio']*100:.1f}%",
                '最長連続 (取引日)': f"{hit['longest_run']:,}",
                '直近の到達日': fmt_date(hit['last_date']),
                f'{ANNUAL_ADD_BUDGET/10000:,.0f}万で買える株数': f"{shares:,}",
            })
        st.dataframe(pd.DataFrame(ladder_rows), use_container_width=True, hide_index=True)
        st.caption(
            f"到達日数 = その日の安値が指値以下だった取引日数 (期間: {period_label})。"
            "最長連続が長い水準は「待てば必ず来る」のではなく"
            "「来たときに長く居座った」水準であることに注意。"
        )


# =========================
# 日産分析は GitHub Pages へ移管
# =========================
st.header("04  日産自動車 (7201) 分析", divider='orange')
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
    "Data: Yahoo Finance (現値15分 / 日足1時間キャッシュ)。"
    "日産の決算・月次データは 日産分析ノート を参照。"
)
st.caption("実際の株価は市場環境・為替・関税政策等により大きく変動します。投資判断はご自身の責任で。")
