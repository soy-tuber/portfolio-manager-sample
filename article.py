"""参考情報: SoyとOpusの対話 (現場と数字で日産を読む)

`docs/nissan_dialogue.md` を読み込んで表示するだけのページ。
内容を更新したいときは markdown を編集して push すれば反映されます。
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

# set_page_config / 共通CSS は app.py (エントリ) 側で実行済み。
# ここでは記事ページ固有の追加スタイルだけ注入。
st.markdown(
    """
<style>
    /* 長文記事用に行間を少し詰める + 引用ブロックをテーマカラーで強調 */
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

if st.button("← ダッシュボードに戻る"):
    st.switch_page("dashboard.py")

DOC_PATH = Path(__file__).resolve().parent / "docs" / "nissan_dialogue.md"

try:
    content = DOC_PATH.read_text(encoding="utf-8")
except FileNotFoundError:
    st.error(f"記事ファイルが見つかりません: {DOC_PATH}")
    st.stop()

st.caption(f"Source: `{DOC_PATH.relative_to(DOC_PATH.parent.parent)}` — 更新するには markdown を編集して push。")
st.markdown(content)
