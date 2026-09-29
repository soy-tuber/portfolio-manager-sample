"""ポートフォリオ管理ページ: 保有銘柄・LTV 余力・約定履歴"""

import pandas as pd
import streamlit as st

import portfolio as pf
from ui import load_prices

st.title("📊 ポートフォリオ管理")
st.caption(
    f"担保=配当{len(pf.COLLAT_CODES)}銘柄。日産は担保差入れ済みだがLTV対象外。LTV 55-60%目標。"
)

prices = load_prices()
snap = pf.summarize(prices)
steps = pf.threshold_progress(snap.collateral)
status = pf.ltv_status(snap.ltv)

# =========================
# 保有銘柄
# =========================
st.subheader("現在の保有銘柄")
rows = [{
    '銘柄': f"{code} {info['name']}",
    '株数': f"{info['shares']:,}",
    '株価': f"¥{prices[code]:,.0f}",
    '平均取得 (¥)': f"{info['avg_cost']:,.0f}" if info.get('avg_cost') else '—',
    '時価 (万)': f"{info['shares'] * prices[code] / 10000:,.0f}",
    '配当 (¥)': f"{info['dividend']}" if info['dividend'] else '—',
    '比率': f"{info['shares'] * prices[code] / snap.total_value * 100:.1f}%",
    '性格': info['role'],
} for code, info in pf.STOCKS.items()]
rows.append({
    '銘柄': '**合計**', '株数': '', '株価': '', '平均取得 (¥)': '',
    '時価 (万)': f"**{snap.total_value/10000:,.0f}**",
    '配当 (¥)': f"**{snap.total_dividend:,}**",
    '比率': '100%', '性格': '',
})
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# =========================
# 余力メーター
# =========================
st.subheader("余力メーター")

# 現在地のバンドと、次のしきい値までの距離を最初に出す
if status['next_threshold'] is None:
    st.error(f"{status['icon']} **{status['label']}** — 最上位のしきい値を超えています。")
else:
    nxt = next(s for s in steps if s['threshold'] == status['next_threshold'])
    headline = (
        f"{status['icon']} **LTV {snap.ltv:.1f}%（{status['label']}）** — "
        f"次は {nxt['threshold']*100:.0f}%（{nxt['label']}）。"
        f"担保プールが **{abs(nxt['drop'])*100:.1f}% {'下落' if nxt['drop'] < 0 else '上昇'}** で抵触"
        f"（抵触水準 {nxt['trigger']/10000:,.0f}万 / 枠の残り {nxt['room']/10000:+,.0f}万）。"
    )
    (st.error if nxt['threshold'] >= 0.85 else
     st.warning if status['breached'] else st.info)(headline)

c1, c2, c3, c4 = st.columns(4)
c1.metric("担保プール", f"{snap.collateral/10000:,.0f}万",
          f"現在LTV {snap.ltv:.1f}% / 目標 55-60%", delta_color="off")
c2.metric("借入残高", f"{pf.LOAN_BALANCE/10000:,.0f}万",
          f"下限 {pf.LOAN_FLOOR/10000:,.0f}万", delta_color="off")
step70 = next(s for s in steps if s['threshold'] == 0.70)
c3.metric("70%枠余力", f"{snap.room70/10000:+,.0f}万",
          f"担保 {step70['drop']*100:+.1f}% で70%抵触", delta_color="off")
c4.metric("NAV (純資産)", f"{snap.nav/10000:,.0f}万",
          f"PF {snap.pf_total/10000:,.0f}万 - 借入", delta_color="off")

st.markdown("**しきい値進捗** (借入が枠を何%埋めているか / 抵触までの担保変化率)")
for step in steps:
    if step['room'] >= 0:
        detail = (f"残り {step['room']/10000:+,.0f}万 · "
                  f"担保 {step['drop']*100:+.1f}% で抵触")
    else:
        detail = f"超過 {step['room']/10000:+,.0f}万 · 担保 {step['drop']*100:+.1f}% で解消"
    st.text(f"{step['icon']} {step['threshold']*100:.0f}%枠: "
            f"{step['fill']*100:.1f}%  ({detail})")
    st.progress(min(step['fill'], 1.0))

with st.expander("日産 (LTV対象外) / 現金バッファ", expanded=False):
    d1, d2 = st.columns(2)
    d1.metric("日産", f"{snap.nissan_value/10000:,.0f}万",
              f"{pf.STOCKS[pf.NISSAN_CODE]['shares']:,}株 @¥{prices[pf.NISSAN_CODE]:.0f}",
              delta_color="off")
    d2.metric("現金バッファ", f"{pf.CASH_BUFFER/10000:,.0f}万", "健全運用", delta_color="off")
    st.caption("日産は担保差入れ済みだが LTV 計算には算入しない。")

# =========================
# 約定履歴 / 損益
# =========================
st.subheader("約定履歴")
summary = pf.trade_summary()
cost_rows, cost_totals = pf.position_costs(prices)

t1, t2, t3 = st.columns(3)
t1.metric("確定益 (累計)", f"{summary['realized_gain']/10000:+,.0f}万",
          f"売却 {summary['sell_count']}件 / {summary['sold_shares']:,}株", delta_color="off")
if cost_rows:
    t2.metric("含み損益 (原価判明分)", f"{cost_totals['pl']/10000:+,.0f}万",
              f"{cost_totals['pl_pct']:+.1f}% / 原価 {cost_totals['cost']/10000:,.0f}万",
              delta_color="normal")
else:
    t2.metric("含み損益 (原価判明分)", "—", "平均取得価格が未登録", delta_color="off")
t3.metric("買い増し (累計)", f"{summary['bought_shares']:,}株",
          f"買い {summary['buy_count']}件", delta_color="off")

with st.expander("約定明細 / 取得原価", expanded=False):
    st.dataframe(pd.DataFrame([{
        '約定日': t['date'],
        '銘柄': f"{t['code']} {t['name']}",
        '区分': t['action'],
        '株数': f"{t['shares']:,}",
        '代金 (万)': f"{t['amount']/10000:,.0f}" if t.get('amount') else '—',
        '確定損益 (万)': f"{t['gain']/10000:+,.0f}" if t.get('gain') else '—',
        '資金': t['funding'],
    } for t in pf.TRADES]), use_container_width=True, hide_index=True)
    for t in pf.TRADES:
        if t.get('note'):
            st.caption(f"{t['date']} {t['name']}: {t['note']}")

    if cost_rows:
        st.dataframe(pd.DataFrame([{
            '銘柄': f"{r['code']} {r['name']}",
            '株数': f"{r['shares']:,}",
            '平均取得 (¥)': f"{r['avg_cost']:,.0f}",
            '取得原価 (万)': f"{r['cost']/10000:,.0f}",
            '時価 (万)': f"{r['value']/10000:,.0f}",
            '含み損益 (万)': f"{r['pl']/10000:+,.0f}",
            '騰落率': f"{r['pl_pct']:+.1f}%",
        } for r in cost_rows]), use_container_width=True, hide_index=True)
    st.caption(
        f"含み損益は平均取得価格を登録済みの {cost_totals['covered']}/"
        f"{cost_totals['total_positions']} 銘柄のみ。"
        "他銘柄の平均取得価格を portfolio.py の avg_cost に入れれば集計対象になります。"
    )
