"""Yahoo Finance からの価格取得 (Streamlit キャッシュ付き)

現値と日足を同じ chart API から取る。追加パッケージは不要 (requests のみ)。
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import requests
import streamlit as st

import bottom_analysis as ba
from bottom_analysis import JST
from portfolio import STOCKS

CHART_URL = 'https://query1.finance.yahoo.com/v8/finance/chart/{code}.T'
HEADERS = {'User-Agent': 'Mozilla/5.0'}


@st.cache_data(ttl=900, show_spinner='Yahoo Financeから株価取得中...')
def fetch_prices() -> tuple[dict[str, float | None], str]:
    """保有銘柄の現値を取得。15分キャッシュ。

    みんかぶのスクレイピングは Streamlit Cloud (海外サーバー) から弾かれるため、
    海外からでも日本株 (.T) を返す Yahoo Finance の chart API を使用する。
    """
    results: dict[str, float | None] = {}
    for code in STOCKS:
        try:
            r = requests.get(CHART_URL.format(code=code), headers=HEADERS, timeout=15)
            r.raise_for_status()
            price = r.json()['chart']['result'][0]['meta'].get('regularMarketPrice')
            results[code] = float(price) if price is not None else None
        except Exception:
            results[code] = None
    return results, datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')


@st.cache_data(ttl=3600, show_spinner='日足データ取得中...')
def fetch_daily_bars(codes: tuple[str, ...],
                     period: str) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """同じ chart API に range/interval を付けて日足 OHLC を取得。1時間キャッシュ。"""
    bars: dict[str, pd.DataFrame] = {}
    failed: list[str] = []
    for code in codes:
        try:
            r = requests.get(CHART_URL.format(code=code),
                             params={'range': period, 'interval': '1d'},
                             headers=HEADERS, timeout=20)
            r.raise_for_status()
            bars[code] = ba.parse_chart_bars(r.json())
        except Exception:
            failed.append(code)
    return bars, failed


def clear_caches() -> None:
    fetch_prices.clear()
    fetch_daily_bars.clear()
