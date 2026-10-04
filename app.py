"""エントリ: st.navigation で多ページを明示登録するルーター

Streamlit Cloud (Python 3.14) で `pages/` ディレクトリ自動検出が
url_pathname を解決できない不具合を回避するため、st.navigation API
で明示的にページを登録する構成 (ページ本体は views/ に置く)。

配色はダーク専用のサイバーパンク。基本色は .streamlit/config.toml、
筐体まわりの装飾は theme.css() が担当する。
"""

from __future__ import annotations

import streamlit as st

import theme

st.set_page_config(
    page_title="ポートフォリオ管理",
    page_icon="📊",
    layout="wide",
)

st.markdown(theme.css(), unsafe_allow_html=True)

pg = st.navigation([
    st.Page("views/portfolio_page.py", title="ポートフォリオ管理",
            icon="📊", url_path="portfolio", default=True),
    st.Page("views/bottom_page.py", title="底値分析",
            icon="📉", url_path="bottom"),
    st.Page("views/notes_page.py", title="資料",
            icon="📚", url_path="notes"),
])
pg.run()

st.sidebar.markdown("---")
st.sidebar.caption(
    "Data: Yahoo Finance (現値15分 / 日足1時間キャッシュ)。  \n"
    "サンプルデータです。投資判断はご自身の責任で。"
)
