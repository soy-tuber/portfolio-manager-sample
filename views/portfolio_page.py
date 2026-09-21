"""ポートフォリオ管理ページ: 保有銘柄・確定売買・LTV 余力"""

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

# =========================
# 保有銘柄
# =========================
st.subheader("現在の保有銘柄")
rows = [{
    '銘柄': f"{code} {info['name']}",
    '株数': f"{info['shares']:,}",
    '株価': f"¥{prices[code]:,.0f}",
    '時価 (万)': f"{info['shares'] * prices[code] / 10000:,.0f}",
    '配当 (¥)': f"{info['dividend']}" if info['dividend'] else '—',
    '比率': f"{info['shares'] * prices[code] / snap.total_value * 100:.1f}%",
    '性格': info['role'],
} for code, info in pf.STOCKS.items()]
rows.append({
    '銘柄': '**合計**', '株数': '', '株価': '',
    '時価 (万)': f"**{snap.total_value/10000:,.0f}**",
    '配当 (¥)': f"**{snap.total_dividend:,}**",
    '比率': '100%', '性格': '',
})
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# =========================
# 余力メーター
# =========================
st.subheader("余力メーター")
st.info(
    f"**運用ルール:** 借入{pf.LOAN_FLOOR/10000:,.0f}万を**下限**として維持。"
    "**LTV 55-60%目標**で担保増価に応じて借り増し → 日産買い増し"
    f"（年{pf.ANNUAL_ADD_BUDGET/10000:,.0f}万ペース）。  \n"
    "Rakuten Bank: **60% 通常 / 70% 警告 / 85% 強制決済**"
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("担保プール", f"{snap.collateral/10000:,.0f}万",
          f"現在LTV {snap.ltv:.1f}% / 目標 55-60%", delta_color="off")
c2.metric("借入残高", f"{pf.LOAN_BALANCE/10000:,.0f}万",
          f"下限 {pf.LOAN_FLOOR/10000:,.0f}万", delta_color="off")
c3.metric("70%枠余力", f"{snap.room70/10000:+,.0f}万",
          "借り増し可能" if snap.room70 >= 0 else "担保増価待ち",
          delta_color="normal" if snap.room70 >= 0 else "inverse")
c4.metric("NAV (純資産)", f"{snap.nav/10000:,.0f}万",
          f"PF {snap.pf_total/10000:,.0f}万 - 借入", delta_color="off")

st.markdown("**しきい値進捗** (借入が枠を何%埋めているか)")
for step in pf.threshold_progress(snap.collateral):
    st.text(f"{step['icon']} {step['threshold']*100:.0f}%枠: {step['fill']*100:.1f}%")
    st.progress(min(step['fill'], 1.0))

with st.expander("日産 (LTV対象外) / 現金バッファ", expanded=False):
    d1, d2 = st.columns(2)
    d1.metric("日産", f"{snap.nissan_value/10000:,.0f}万",
              f"{pf.STOCKS[pf.NISSAN_CODE]['shares']:,}株 @¥{prices[pf.NISSAN_CODE]:.0f}",
              delta_color="off")
    d2.metric("現金バッファ", f"{pf.CASH_BUFFER/10000:,.0f}万", "健全運用", delta_color="off")
    st.caption("日産は担保差入れ済みだが LTV 計算には算入しない。")

# =========================
# 確定売買
# =========================
if pf.REALIZED_TRADES:
    st.subheader("確定売買")
    realized = pf.realized_summary(snap.collateral)

    t1, t2, t3 = st.columns(3)
    t1.metric("確定益 (累計)", f"{realized['gain']/10000:+,.0f}万", "実現ベース", delta_color="off")
    t2.metric("借入返済 (充当)", f"−{realized['repaid']/10000:,.0f}万",
              f"{realized['pre_loan']/10000:,.0f}万 → {pf.LOAN_BALANCE/10000:,.0f}万",
              delta_color="off")
    t3.metric("LTV改善", f"{realized['ltv_delta']:+.1f}pt",
              f"{realized['pre_ltv']:.1f}% 相当 → {realized['ltv']:.1f}%", delta_color="off")

    with st.expander("約定明細", expanded=False):
        st.dataframe(pd.DataFrame([{
            '約定日': t['date'],
            '銘柄': f"{t['code']} {t['name']}",
            '区分': t['action'],
            '株数': f"{t['shares']:,}",
            '代金 (万)': f"{t['proceeds']/10000:,.0f}",
            '単価 (¥)': f"{t['proceeds']/t['shares']:,.0f}",
            '確定損益 (万)': f"{t['gain']/10000:+,.0f}",
            '代金の使途': t['use'],
        } for t in pf.REALIZED_TRADES]), use_container_width=True, hide_index=True)
        for t in pf.REALIZED_TRADES:
            if t.get('note'):
                st.caption(f"{t['date']} {t['name']}: {t['note']}")
        st.caption(
            "売却前LTVは「売却銘柄の時価=売却代金」「残り銘柄は現値」とみなした概算です。"
        )
