"""bottom_analysis の単体テスト (合成データのみ / ネットワーク不要)

実行: python tests/test_bottom_analysis.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bottom_analysis as ba  # noqa: E402


def epoch(year: int, month: int, day: int) -> int:
    """JP 日足のタイムスタンプ (00:00 UTC = その日の 09:00 JST) を作る。"""
    return int(datetime(year, month, day, 0, 0, tzinfo=timezone.utc).timestamp())


def chart_payload(stamps, opens, highs, lows, closes) -> dict:
    return {'chart': {'result': [{
        'meta': {'symbol': 'TEST.T'},
        'timestamp': stamps,
        'indicators': {'quote': [{
            'open': opens, 'high': highs, 'low': lows, 'close': closes,
        }]},
    }]}}


def make_frame(dates, lows, highs=None, closes=None) -> pd.DataFrame:
    highs = highs if highs is not None else [lv * 1.05 for lv in lows]
    closes = closes if closes is not None else [lv * 1.02 for lv in lows]
    return pd.DataFrame(
        {'open': closes, 'high': highs, 'low': lows, 'close': closes},
        index=pd.DatetimeIndex(pd.to_datetime(dates), name='date'),
    )


def test_parse_chart_bars_normalizes_to_jst_trading_day():
    payload = chart_payload(
        [epoch(2026, 9, 16), epoch(2026, 9, 17), epoch(2026, 9, 18)],
        [100, 101, 102], [110, 111, 112], [95, 96, 97], [105, 106, 107],
    )
    frame = ba.parse_chart_bars(payload)
    assert list(frame.index.strftime('%Y-%m-%d')) == ['2026-09-16', '2026-09-17', '2026-09-18']
    assert list(frame['low']) == [95.0, 96.0, 97.0]
    assert list(frame.columns) == ['open', 'high', 'low', 'close']


def test_parse_chart_bars_drops_null_and_nonpositive_rows():
    payload = chart_payload(
        [epoch(2026, 9, 14), epoch(2026, 9, 15), epoch(2026, 9, 16), epoch(2026, 9, 17)],
        [100, None, 0, 103], [110, 111, 0, 113], [95, None, 0, 98], [105, 106, 0, 108],
    )
    frame = ba.parse_chart_bars(payload)
    assert list(frame.index.strftime('%Y-%m-%d')) == ['2026-09-14', '2026-09-17']


def test_parse_chart_bars_dedupes_and_sorts():
    payload = chart_payload(
        [epoch(2026, 9, 17), epoch(2026, 9, 16), epoch(2026, 9, 17)],
        [1, 1, 1], [2, 2, 2], [1, 1, 1], [9, 5, 7],
    )
    frame = ba.parse_chart_bars(payload)
    assert list(frame.index.strftime('%Y-%m-%d')) == ['2026-09-16', '2026-09-17']
    assert frame.loc['2026-09-17', 'close'] == 7.0  # 後勝ち


def test_parse_chart_bars_rejects_empty():
    for payload in (
        chart_payload([], [], [], [], []),
        {'chart': {'result': [{'timestamp': [epoch(2026, 9, 17)], 'indicators': {}}]}},
    ):
        try:
            ba.parse_chart_bars(payload)
        except ValueError:
            pass
        else:
            raise AssertionError('空データで ValueError にならない')


def test_bottom_profile():
    frame = make_frame(
        ['2026-09-01', '2026-09-02', '2026-09-03', '2026-09-04'],
        lows=[400, 300, 320, 500],
        highs=[450, 340, 360, 560],
    )
    profile = ba.bottom_profile(frame, current_price=600.0, near_pct=10.0)
    assert profile['trading_days'] == 4
    assert profile['low'] == 300.0
    assert profile['low_date'].strftime('%Y-%m-%d') == '2026-09-02'
    assert profile['high'] == 560.0
    assert profile['near_level'] == 330.0
    # 安値 300 と 320 が 330 以下 → 2日
    assert profile['near_days'] == 2
    assert round(profile['above_low'], 4) == 1.0        # 600 は安値の2倍
    assert round(profile['below_high'], 6) == round(600 / 560 - 1, 6)


def test_days_at_or_below_counts_trading_days_and_longest_run():
    frame = make_frame(
        ['2026-09-01', '2026-09-02', '2026-09-03', '2026-09-04',
         '2026-09-07', '2026-09-08', '2026-09-09'],
        lows=[410, 390, 380, 420, 385, 375, 430],
    )
    hit = ba.days_at_or_below(frame['low'], 400)
    assert hit['days'] == 4                       # 390, 380, 385, 375
    assert hit['longest_run'] == 2                # 390, 380 / 385, 375
    assert hit['first_date'].strftime('%Y-%m-%d') == '2026-09-02'
    assert hit['last_date'].strftime('%Y-%m-%d') == '2026-09-08'
    assert round(hit['ratio'], 4) == round(4 / 7, 4)

    miss = ba.days_at_or_below(frame['low'], 300)
    assert miss['days'] == 0 and miss['longest_run'] == 0
    assert miss['last_date'] is None


def test_days_at_or_below_run_spans_weekend_gap_only_in_trading_days():
    # 9/4(金) と 9/7(月) は連続する取引日 → 連続2日と数える
    frame = make_frame(['2026-09-03', '2026-09-04', '2026-09-07'], lows=[500, 390, 380])
    hit = ba.days_at_or_below(frame['low'], 400)
    assert hit['days'] == 2 and hit['longest_run'] == 2


def test_price_ladder_and_lot_size():
    assert ba.price_ladder(400, 25, 4) == [400, 375, 350, 325]
    assert ba.price_ladder(60, 25, 4) == [60, 35, 10]        # 正値のみ
    assert ba.lot_size_for_budget(400, 10_000_000) == 25_000  # 単元100株に丸め
    assert ba.lot_size_for_budget(333, 10_000_000) == 30_000  # 30,030 → 30,000
    assert ba.lot_size_for_budget(0, 10_000_000) == 0


def test_build_pool_series_weights_and_intersects():
    bars = {
        'A': make_frame(['2026-09-01', '2026-09-02', '2026-09-03'],
                        lows=[100, 90, 95], closes=[110, 95, 100]),
        'B': make_frame(['2026-09-02', '2026-09-03', '2026-09-04'],
                        lows=[200, 210, 220], closes=[205, 215, 225]),
    }
    pool = ba.build_pool_series(bars, {'A': 10, 'B': 5})
    assert list(pool.index.strftime('%Y-%m-%d')) == ['2026-09-02', '2026-09-03']
    assert pool.loc['2026-09-02', 'pool_low'] == 90 * 10 + 200 * 5
    assert pool.loc['2026-09-03', 'pool_close'] == 100 * 10 + 215 * 5


def test_build_pool_series_requires_every_holding():
    bars = {'A': make_frame(['2026-09-02'], lows=[100])}
    try:
        ba.build_pool_series(bars, {'A': 10, 'B': 5})
    except ValueError as error:
        assert 'B' in str(error)
    else:
        raise AssertionError('欠損銘柄があるのに例外にならない')


def test_build_pool_series_rejects_disjoint_calendars():
    bars = {
        'A': make_frame(['2026-09-01'], lows=[100]),
        'B': make_frame(['2026-09-02'], lows=[200]),
    }
    try:
        ba.build_pool_series(bars, {'A': 1, 'B': 1})
    except ValueError:
        pass
    else:
        raise AssertionError('共通営業日なしで例外にならない')


def test_worst_drawdown():
    close = pd.Series(
        [100, 120, 90, 60, 80, 130],
        index=pd.DatetimeIndex(pd.to_datetime([
            '2026-01-01', '2026-01-02', '2026-01-03',
            '2026-01-04', '2026-01-05', '2026-01-06'])),
    )
    dd = ba.worst_drawdown(close)
    assert round(dd['depth'], 4) == round(60 / 120 - 1, 4)   # -50%
    assert dd['peak_date'].strftime('%Y-%m-%d') == '2026-01-02'
    assert dd['trough_date'].strftime('%Y-%m-%d') == '2026-01-04'


def test_ltv_threshold_scan():
    pool_low = pd.Series(
        [120_000_000, 100_000_000, 92_000_000, 80_000_000],
        index=pd.DatetimeIndex(pd.to_datetime([
            '2026-09-01', '2026-09-02', '2026-09-03', '2026-09-04'])),
    )
    scan = ba.ltv_threshold_scan(pool_low, current_pool=105_300_000,
                                 loan=65_000_000, thresholds=(0.60, 0.70, 0.85))
    by_threshold = {row['threshold']: row for row in scan}

    # 60% 抵触水準 = 65,000,000 / 0.6 ≈ 108,333,333
    row60 = by_threshold[0.60]
    assert round(row60['trigger_pool']) == 108_333_333
    assert row60['days'] == 3                      # 100M, 92M, 80M
    assert row60['longest_run'] == 3
    assert row60['gap'] > 0                        # 現在すでに 60% 超過

    # 70% 抵触水準 ≈ 92,857,143 → 92M と 80M の2日
    row70 = by_threshold[0.70]
    assert row70['days'] == 2
    assert row70['gap'] < 0                        # まだ余裕あり

    # 85% 抵触水準 ≈ 76,470,588 → 到達なし
    row85 = by_threshold[0.85]
    assert row85['days'] == 0 and row85['last_date'] is None


def main() -> int:
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith('test_') and callable(fn)]
    failures = 0
    for name, fn in tests:
        try:
            fn()
        except Exception as error:  # noqa: BLE001
            failures += 1
            print(f'FAIL {name}: {type(error).__name__}: {error}')
        else:
            print(f'ok   {name}')
    print(f'\n{len(tests) - failures}/{len(tests)} passed')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
