"""ページ共通の表示ヘルパー"""

from __future__ import annotations

import streamlit as st

import market
import portfolio as pf


def yen_man(value: float) -> str:
    """円 → 万円表記。"""
    return f"{value/10000:,.0f}万"


def fmt_date(value) -> str:
    return value.strftime('%Y-%m-%d') if value is not None else '—'


def load_prices() -> dict[str, float]:
    """現値を取得し、取得状況と再取得ボタンをサイドバーに出す。"""
    raw, fetched_at = market.fetch_prices()
    prices = pf.resolve_prices(raw)
    failed = [code for code, price in raw.items() if price is None]

    with st.sidebar:
        st.caption(f"更新: {fetched_at}  \ndata: Yahoo Finance")
        if failed:
            names = ', '.join(pf.STOCKS[c]['name'] for c in failed)
            st.caption(f":orange[フォールバック適用: {names}]")
        if st.button("🔄 再取得", use_container_width=True):
            market.clear_caches()
            st.rerun()
    return prices
