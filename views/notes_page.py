"""資料ページ: 別リポジトリ (soy-tuber/nissan-notes) の GitHub Pages へのリンク集"""

import streamlit as st

PAGES_BASE = "https://soy-tuber.github.io/nissan-notes/"

st.title("📚 資料")
st.caption(f"記事・分析は GitHub Pages に移管しました — {PAGES_BASE}")

st.subheader("日産自動車 (7201) 分析")
st.markdown(
    "決算分析・損益分岐点分析・月次データは、ポートフォリオ管理とは独立した内容のため"
    "別ノートに分けています。"
)
for col, (label, path) in zip(st.columns(3), [
    ("📈 日産PSR分析", "psr.html"),
    ("📐 CVPシナリオ分析", "cvp.html"),
    ("📅 月次 生産・販売・輸出", "monthly.html"),
]):
    col.link_button(label, PAGES_BASE + path, use_container_width=True)

st.subheader("記事・ロードマップ")
left, right = st.columns(2)
for col, items in [
    (left, [
        ("📖 現場と数字で日産を読む", "nissan_dialogue.html"),
        ("🔋 デュアルコア・モビリティ【改訂版】", "dual_core_mobility.html"),
        ("🇨🇳 スティーブン・マーと中国日産", "stephen_ma_china.html"),
    ]),
    (right, [
        ("🤖 Wayve × Nissan ロードマップ", "wayve_roadmap.html"),
        ("📄 デュアルコア・モビリティ【初版PDF】", "dual_core_shinsho.pdf"),
    ]),
]:
    with col:
        for label, path in items:
            st.link_button(label, PAGES_BASE + path, use_container_width=True)
