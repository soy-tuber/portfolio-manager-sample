"""skyline.py の単体テスト (SVG 文字列の検査のみ / 描画不要)"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import skyline as sk  # noqa: E402

CYAN, MAGENTA = '#0da4cf', '#fe29ab'


def sample(values=(100.0, 50.0)) -> list[sk.Building]:
    return [
        sk.Building(key=f'C{i}', label=f'銘柄{i}', sublabel=f'{i*1000:,}株',
                    value=v, value_text=f'{v:,.0f}万',
                    color=CYAN if i else MAGENTA,
                    category='担保' if i else 'LTV対象外')
        for i, v in enumerate(values)
    ]


def render(buildings):
    return sk.render(buildings, text='#d8e6f2', muted='#7b93ad', ground='#1b2b45')


def test_fnv1a_is_stable_across_runs():
    """組込み hash() はプロセスごとに種が変わるため使っていないこと。"""
    assert sk.fnv1a('7222:3:4') == sk.fnv1a('7222:3:4')
    assert sk.fnv1a('') == 0x811c9dc5
    assert sk.fnv1a('a') != sk.fnv1a('b')
    # 既知値を固定し、実装が変わったら気づけるようにする
    assert sk.fnv1a('7222') == 0x94ca04f8


def test_windows_are_deterministic():
    first = [sk.window_is_lit('7222', r, c) for r in range(6) for c in range(6)]
    second = [sk.window_is_lit('7222', r, c) for r in range(6) for c in range(6)]
    assert first == second
    # 銘柄が違えば並びも違う (全部同じ街並みにはならない)
    other = [sk.window_is_lit('2674', r, c) for r in range(6) for c in range(6)]
    assert other != first
    # 全消灯・全点灯になっていない
    assert 0 < sum(first) < len(first)


def test_height_is_linear_and_zero_based():
    """見栄えのための圧縮 (sqrt など) をしていないこと。"""
    assert sk.building_height(0, 100) == 0.0
    assert sk.building_height(100, 100) == sk.MAX_BUILDING_H
    # 半分の値はちょうど半分の高さ
    assert sk.building_height(50, 100) == sk.MAX_BUILDING_H / 2
    # 1/4 も厳密に 1/4 (sqrt なら 1/2 になってしまう)
    assert sk.building_height(25, 100) == sk.MAX_BUILDING_H / 4


def test_height_handles_degenerate_input():
    assert sk.building_height(10, 0) == 0.0
    assert sk.building_height(-5, 100) == 0.0


def test_render_includes_direct_labels_and_legend():
    """CVD フロア帯の2色なので、直接ラベルと凡例は必須。"""
    svg = render(sample())
    for text in ('銘柄0', '銘柄1', '100万', '50万', '担保', 'LTV対象外'):
        assert text in svg, text
    assert svg.startswith('<svg') and svg.endswith('</svg>')
    assert CYAN in svg and MAGENTA in svg


def test_render_escapes_markup_in_labels():
    bad = [sk.Building(key='X', label='<script>&', sublabel='"q"', value=1,
                       value_text='1', color=CYAN, category='担保')]
    svg = render(bad)
    assert '<script>' not in svg
    assert '&lt;script&gt;&amp;' in svg


def test_render_is_reproducible():
    assert render(sample()) == render(sample())


def test_render_empty_is_empty():
    assert render([]) == ''
    assert sk.to_img_tag('', 'alt') == ''


def test_to_img_tag_round_trips_the_svg():
    svg = render(sample())
    tag = sk.to_img_tag(svg, '保有銘柄の時価')
    assert tag.startswith('<img src="data:image/svg+xml;base64,')
    b64 = tag.split('base64,')[1].split('"')[0]
    assert base64.b64decode(b64).decode('utf-8') == svg
    assert 'alt="保有銘柄の時価"' in tag


def test_svg_has_intrinsic_size_for_img_embedding():
    """<img> で使うため width/height 属性が要る (viewBox だけだと潰れる)。"""
    svg = render(sample())
    assert f'width="{sk.VIEW_W}"' in svg and f'height="{sk.VIEW_H}"' in svg
    assert f'viewBox="0 0 {sk.VIEW_W} {sk.VIEW_H}"' in svg
