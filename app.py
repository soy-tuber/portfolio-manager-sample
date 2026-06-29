"""エントリ: st.navigation で多ページを明示登録するルーター

Streamlit Cloud (Python 3.14) で `pages/` ディレクトリ自動検出が
url_pathname を解決できない不具合を回避するため、st.navigation API
で明示的にページを登録する構成。
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="PF管理 / 日産PSR分析",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
<style>
    html { font-size: 13px; }
    [data-testid="stMetricValue"] { font-size: 1.3rem; }
    [data-testid="stMetricLabel"] { font-size: 0.8rem; }
    [data-testid="stMetricDelta"] { font-size: 0.75rem; }
    .stDataFrame, .stDataFrame td, .stDataFrame th { font-size: 0.82rem; }
    h1 { font-size: 1.6rem; }
    h2 { font-size: 1.25rem; }
    h3 { font-size: 1.05rem; }
</style>
    """,
    unsafe_allow_html=True,
)

pg = st.navigation(
    {
        "メイン": [
            st.Page(
                "dashboard.py",
                title="ポートフォリオ管理 / 日産PSR分析",
                icon="📊",
                default=True,
            ),
        ],
        "参考資料": [
            st.Page(
                "article_nissan_dialogue.py",
                title="現場と数字で日産を読む",
                icon="📖",
            ),
            st.Page(
                "article_dual_core.py",
                title="デュアルコア・モビリティ【改訂版】",
                icon="🔋",
            ),
            st.Page(
                "article_stephen_ma.py",
                title="スティーブン・マーと中国日産",
                icon="🇨🇳",
            ),
            st.Page(
                "article_wayve.py",
                title="Wayve × Nissan ロードマップ",
                icon="🤖",
            ),
            st.Page(
                "article_shinsho.py",
                title="デュアルコア・モビリティ【初版PDF】",
                icon="📄",
            ),
        ],
    }
)
pg.run()
