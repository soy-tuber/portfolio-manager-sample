"""底値分析ページ: 担保プールのストレステスト / 銘柄別底値 / 買い増しラダー"""

import pandas as pd
import streamlit as st

import bottom_analysis as ba
import market
import portfolio as pf
from ui import fmt_date, load_prices, yen_man

st.title("📉 底値分析")
st.info(
    "**考え方:** 単一銘柄の「◯円以下だった日数」ではなく、保有株数で重み付けした "
    "**担保プールの合成日次系列**を作り、現在の借入 "
    f"{pf.LOAN_BALANCE/10000:,.0f}万 に対して LTV しきい値 (60/70/85%) が過去どれだけ"
    "踏まれていたかを数えます。日数はすべて**取引日**ベース (暦日ではない)。  \n"
    "判定にはその日の**安値**を使います（ザラ場で触った水準まで拾う）。"
)

prices = load_prices()
snap = pf.summarize(prices)

bp1, bp2 = st.columns([1, 3])
with bp1:
    period_label = st.selectbox("対象期間", list(pf.PERIOD_OPTIONS.keys()), index=1)
with bp2:
    run = st.toggle(
        "日足を取得して集計する", value=False,
        help=f"chart API に{len(pf.STOCKS)}銘柄ぶんリクエストします (1時間キャッシュ)",
    )

if not run:
    st.caption("トグルを ON にすると日足を取得して集計します（現値表示より重いため既定は OFF）。")
    st.stop()

bars, bar_failed = market.fetch_daily_bars(tuple(pf.STOCKS), pf.PERIOD_OPTIONS[period_label])
if bar_failed:
    st.warning("日足を取得できませんでした: "
               + ', '.join(f"{c} {pf.STOCKS[c]['name']}" for c in bar_failed))

# =========================
# 担保プール 底値ストレステスト
# =========================
st.subheader("担保プール 底値ストレステスト")
pool = None
try:
    pool = ba.build_pool_series(bars, {c: pf.STOCKS[c]['shares'] for c in pf.COLLAT_CODES})
except ValueError as error:
    st.error(f"担保プールを合成できませんでした: {error}")

if pool is not None:
    pool_low = pool['pool_low']
    pool_min = float(pool_low.min())
    ltv_at_min = pf.LOAN_BALANCE / pool_min * 100
    drawdown = ba.worst_drawdown(pool['pool_close'])

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("現在の担保プール", yen_man(snap.collateral),
              f"現在LTV {snap.ltv:.1f}%", delta_color="off")
    p2.metric("期間最安プール", yen_man(pool_min),
              fmt_date(pool_low.idxmin()), delta_color="off")
    p3.metric("最安時の想定LTV", f"{ltv_at_min:.1f}%",
              f"現在比 {ltv_at_min - snap.ltv:+.1f}pt", delta_color="inverse")
    p4.metric("最大DD (終値)", f"{drawdown['depth']*100:.1f}%",
              f"{fmt_date(drawdown['peak_date'])} → {fmt_date(drawdown['trough_date'])}",
              delta_color="off")

    scan = ba.ltv_threshold_scan(
        pool_low, current_pool=snap.collateral, loan=pf.LOAN_BALANCE,
        thresholds=tuple(t for t, _i, _l, _c in pf.LTV_THRESHOLDS),
    )
    meta = {t: (icon, label, color) for t, icon, label, color in pf.LTV_THRESHOLDS}

    st.dataframe(pd.DataFrame([{
        'しきい値': f"{meta[row['threshold']][0]} {row['threshold']*100:.0f}%"
                    f" ({meta[row['threshold']][1]})",
        '抵触プール水準 (万)': f"{row['trigger_pool']/10000:,.0f}",
        '現在プールからの距離': f"{row['gap']*100:+.1f}%",
        '期間中の抵触日数': f"{row['days']:,}",
        '抵触率': f"{row['ratio']*100:.1f}%",
        '最長連続 (取引日)': f"{row['longest_run']:,}",
        '直近の抵触日': fmt_date(row['last_date']),
    } for row in scan]), use_container_width=True, hide_index=True)
    st.caption(
        "「現在プールからの距離」がマイナスなら、そこまで下げないと抵触しない余裕。"
        "プラスならすでに超過している水準です。"
    )

    # 推移チャート (単位は万円のみ = 1軸。しきい値線は記号+ラベル+高さでも区別できる)
    chart = pd.DataFrame({'担保プール 終値 (万)': pool['pool_close'] / 10000})
    colors = [pf.SERIES_COLOR]
    for row in scan:
        icon, _label, color = meta[row['threshold']]
        chart[f"{icon} {row['threshold']*100:.0f}%抵触水準 "
              f"{row['trigger_pool']/10000:,.0f}万"] = row['trigger_pool'] / 10000
        colors.append(color)
    st.line_chart(chart, color=colors, use_container_width=True)

    with st.expander("計算の前提 / データ書き出し", expanded=False):
        holdings_note = ', '.join(
            f"{pf.STOCKS[c]['name']} {pf.STOCKS[c]['shares']:,}株" for c in pf.COLLAT_CODES
        )
        st.caption(
            f"共通営業日 {len(pool):,} 取引日 "
            f"({fmt_date(pool.index[0])} 〜 {fmt_date(pool.index[-1])})。"
            f"現在の株数 ({holdings_note}) を過去の株価に当てはめた仮想プールです。"
            "1銘柄でも日足が欠けた日は評価額が過小になるため除外しています。"
        )
        st.download_button(
            "⬇️ 担保プール日次系列 (CSV)",
            pool.assign(
                pool_low_man=pool['pool_low'] / 10000,
                pool_close_man=pool['pool_close'] / 10000,
                ltv_on_low=pf.LOAN_BALANCE / pool['pool_low'] * 100,
            ).to_csv().encode('utf-8-sig'),
            file_name=f"collateral_pool_{pf.PERIOD_OPTIONS[period_label]}.csv",
            mime='text/csv',
        )

# =========================
# 銘柄別 底値マップ
# =========================
st.subheader("銘柄別 底値マップ")
near_pct = st.slider("「安値圏」の幅 (期間安値から+X%以内)", 1.0, 30.0, 10.0, 1.0)

profile_rows = []
for code, info in pf.STOCKS.items():
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

# =========================
# 日産 買い増しラダー
# =========================
st.subheader(f"日産 買い増しラダー (年{pf.ANNUAL_ADD_BUDGET/10000:,.0f}万ペース)")
if pf.NISSAN_CODE not in bars:
    st.warning("日産の日足が取得できていないためラダーを計算できません。")
else:
    nissan_bars = bars[pf.NISSAN_CODE]
    nissan_price = prices[pf.NISSAN_CODE]

    def nice_step(price: float) -> int:
        """現値の約5%に当たるキリのいい刻み。"""
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
        ladder_rows.append({
            '指値 (¥)': f"{level:,.0f}",
            '現値比': f"{(level/nissan_price - 1)*100:+.1f}%" if nissan_price else '—',
            '到達日数': f"{hit['days']:,}",
            '到達率': f"{hit['ratio']*100:.1f}%",
            '最長連続 (取引日)': f"{hit['longest_run']:,}",
            '直近の到達日': fmt_date(hit['last_date']),
            f'{pf.ANNUAL_ADD_BUDGET/10000:,.0f}万で買える株数':
                f"{ba.lot_size_for_budget(level, pf.ANNUAL_ADD_BUDGET):,}",
        })
    st.dataframe(pd.DataFrame(ladder_rows), use_container_width=True, hide_index=True)
    st.caption(
        f"到達日数 = その日の安値が指値以下だった取引日数 (期間: {period_label})。"
        "最長連続が長い水準は「待てば必ず来る」のではなく"
        "「来たときに長く居座った」水準であることに注意。"
    )
