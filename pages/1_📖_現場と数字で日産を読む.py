"""参考情報: SoyとOpusの対話 (現場と数字で日産を読む)

`docs/nissan_dialogue.md` を読み込んで表示するだけのページ。
内容を更新したいときは markdown を編集して push すれば反映されます。
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="現場と数字で日産を読む",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="collapsed",
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
    /* サイドバーを完全に非表示 */
    [data-testid="stSidebar"] { display: none; }
    [data-testid="stSidebarCollapsedControl"] { display: none; }
    [data-testid="collapsedControl"] { display: none; }
    /* 長文記事用に行間を少し詰める */
    [data-testid="stMarkdownContainer"] p { line-height: 1.7; }
    [data-testid="stMarkdownContainer"] blockquote {
        border-left: 3px solid #d4a853;
        padding-left: 1rem;
        color: #c8c6c0;
    }
</style>
    """,
    unsafe_allow_html=True,
)

st.page_link("app.py", label="← ダッシュボードに戻る")

DOC_PATH = Path(__file__).resolve().parent.parent / "docs" / "nissan_dialogue.md"

try:
    content = DOC_PATH.read_text(encoding="utf-8")
except FileNotFoundError:
    st.error(f"記事ファイルが見つかりません: {DOC_PATH}")
    st.stop()

st.caption(f"Source: `{DOC_PATH.relative_to(DOC_PATH.parent.parent)}` — 更新するには markdown を編集して push。")
st.markdown(content)
