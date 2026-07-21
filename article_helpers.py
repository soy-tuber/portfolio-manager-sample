"""記事ページ共通のヘルパー (CSS注入・戻るボタン・各形式のレンダラ)"""

from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

DOCS_DIR = Path(__file__).resolve().parent / "docs"
_IMG_MD_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def _embed_images(content: str, base_dir: Path) -> str:
    """markdown 内の相対パス画像を base64 data URI に置換。

    Streamlit Cloud では docs/ 配下の画像を直接配信できないため、
    ![alt](images/foo.webp) のような相対参照を、その場で読み込んで
    data URI に埋め込む。存在しないファイルはそのまま残す。
    """

    def replace(match: re.Match[str]) -> str:
        alt = match.group(1)
        ref = match.group(2).strip()
        if ref.startswith(("http://", "https://", "data:")):
            return match.group(0)
        img_path = (base_dir / ref).resolve()
        try:
            data = img_path.read_bytes()
        except (FileNotFoundError, IsADirectoryError, OSError):
            return match.group(0)
        mime, _ = mimetypes.guess_type(img_path.name)
        if mime is None:
            if img_path.suffix.lower() == ".webp":
                mime = "image/webp"
            else:
                mime = "application/octet-stream"
        b64 = base64.b64encode(data).decode("ascii")
        return f"![{alt}](data:{mime};base64,{b64})"

    return _IMG_MD_RE.sub(replace, content)


def setup_article_page() -> None:
    """全記事ページ共通の追加CSSと「戻る」ボタンを描画。"""
    st.markdown(
        """
<style>
    /* 長文記事用に行間を詰める + 引用ブロックをテーマカラーで強調 */
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


def render_markdown(filename: str) -> None:
    """docs/<filename> の markdown を読み込んで描画。

    markdown 内の相対パス画像参照 (docs/ からの相対) は base64 data URI に
    展開して埋め込む。docs/images/foo.webp を ![alt](images/foo.webp) の
    形で参照できる。
    """
    path = DOCS_DIR / filename
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        st.error(f"記事ファイルが見つかりません: {path}")
        st.stop()
    content = _embed_images(content, DOCS_DIR)
    st.caption(f"Source: `docs/{filename}` — 更新するには markdown を編集して push。")
    st.markdown(content)


def render_html(filename: str, height: int = 4000) -> None:
    """docs/<filename> の HTML を iframe で埋め込み描画。"""
    path = DOCS_DIR / filename
    try:
        html = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        st.error(f"記事ファイルが見つかりません: {path}")
        st.stop()
    st.caption(f"Source: `docs/{filename}` — 更新するには HTML を編集して push。")
    components.html(html, height=height, scrolling=True)


def render_pdf(filename: str, height: int = 900) -> None:
    """docs/<filename> の PDF を iframe (base64) で埋め込み描画。"""
    path = DOCS_DIR / filename
    try:
        pdf_bytes = path.read_bytes()
    except FileNotFoundError:
        st.error(f"PDFファイルが見つかりません: {path}")
        st.stop()
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    st.caption(f"Source: `docs/{filename}` — ブラウザのPDFビューアで表示。")
    st.download_button(
        "📥 PDFをダウンロード",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
    )
    iframe = (
        f'<iframe src="data:application/pdf;base64,{b64}" '
        f'width="100%" height="{height}px" '
        'style="border:1px solid #28384A;border-radius:6px;"></iframe>'
    )
    st.markdown(iframe, unsafe_allow_html=True)
