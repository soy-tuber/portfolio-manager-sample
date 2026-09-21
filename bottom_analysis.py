"""底値分析ユーティリティ (ネットワーク / Streamlit 非依存の純関数群)

Yahoo Finance chart API の日足レスポンスを DataFrame に整形し、
このポートフォリオ固有の底値指標を計算する。

設計方針:
  - 「単一銘柄がいくら以下だった日数」ではなく、**担保プール全体**を
    保有株数で重み付けした合成系列として扱い、借入残高に対する
    LTV しきい値 (60/70/85%) が過去にどれだけ踏まれたかを数える。
  - 買い増し対象銘柄については、年間予算から逆算した
    指値ラダーの「約定機会 (日数・最長連続・直近該当日)」を出す。
  - 日数は暦日ではなく**取引日**で数える (連続性も取引日ベース)。
"""

from __future__ import annotations

from datetime import timedelta, timezone

import pandas as pd

JST = timezone(timedelta(hours=9))

OHLC_KEYS = ('open', 'high', 'low', 'close')


# =========================
# パース
# =========================
def parse_chart_bars(payload: dict) -> pd.DataFrame:
    """chart API の JSON から日足 OHLC を取り出す。

    JP 銘柄の日足タイムスタンプは 00:00 UTC (= 09:00 JST) のため、
    JST に変換してから日付へ正規化すると取引日と一致する。
    """
    result = payload['chart']['result'][0]
    stamps = result.get('timestamp') or []
    quote_list = (result.get('indicators') or {}).get('quote') or []
    quote = quote_list[0] if quote_list else {}
    if not stamps or not quote.get('low'):
        raise ValueError('日足データが空です')

    index = (
        pd.to_datetime(pd.Series(stamps), unit='s', utc=True)
        .dt.tz_convert(JST)
        .dt.normalize()
        .dt.tz_localize(None)
    )
    frame = pd.DataFrame(
        {key: quote.get(key) for key in OHLC_KEYS},
        index=pd.DatetimeIndex(index, name='date'),
    )
    frame = frame.apply(pd.to_numeric, errors='coerce').dropna()
    # 気配のみ / 値付かずの行は落とす (0 や負値は使わない)
    frame = frame[(frame > 0).all(axis=1)]
    frame = frame[~frame.index.duplicated(keep='last')].sort_index()
    if frame.empty:
        raise ValueError('有効な日足がありません')
    return frame


# =========================
# 銘柄単位の底値プロファイル
# =========================
def bottom_profile(frame: pd.DataFrame, current_price: float,
                   near_pct: float = 10.0) -> dict:
    """期間安値・高値と、現値からの位置関係。

    near_days は「安値から near_pct% 以内」で寄り付いた取引日数 =
    その水準を拾うチャンスが実際に何日あったかの目安。
    """
    low = frame['low']
    high = frame['high']
    low_min = float(low.min())
    high_max = float(high.max())
    near_level = low_min * (1 + near_pct / 100)
    return {
        'trading_days': int(len(frame)),
        'start': frame.index[0],
        'end': frame.index[-1],
        'low': low_min,
        'low_date': low.idxmin(),
        'high': high_max,
        'high_date': high.idxmax(),
        'near_level': near_level,
        'near_days': int((low <= near_level).sum()),
        # 現値が安値からどれだけ上か / 高値からどれだけ下か
        'above_low': current_price / low_min - 1 if low_min else float('nan'),
        'below_high': current_price / high_max - 1 if high_max else float('nan'),
    }


# =========================
# 水準別の到達日数
# =========================
def days_at_or_below(low: pd.Series, level: float) -> dict:
    """安値が level 以下だった取引日数・最長連続取引日数・直近該当日。"""
    hit = (low <= level).to_numpy()
    longest = 0
    run = 0
    for flag in hit:
        run = run + 1 if flag else 0
        longest = max(longest, run)
    hit_index = low.index[hit]
    return {
        'level': float(level),
        'days': int(hit.sum()),
        'ratio': float(hit.sum()) / len(low) if len(low) else 0.0,
        'longest_run': int(longest),
        'last_date': hit_index[-1] if len(hit_index) else None,
        'first_date': hit_index[0] if len(hit_index) else None,
    }


def price_ladder(top: float, step: float, count: int) -> list[float]:
    """top から step 刻みで下へ count 本の指値ラダー (正値のみ)。"""
    levels = [top - step * i for i in range(count)]
    return [lv for lv in levels if lv > 0]


def lot_size_for_budget(level: float, budget: float, unit: int = 100) -> int:
    """予算 budget で level の指値が何株 (単元 unit) 買えるか。"""
    if level <= 0:
        return 0
    return int(budget // (level * unit)) * unit


# =========================
# 担保プールの合成系列
# =========================
def build_pool_series(bars: dict[str, pd.DataFrame],
                      holdings: dict[str, int]) -> pd.DataFrame:
    """保有株数で重み付けした担保プールの日次系列。

    全対象銘柄に日足が揃っている取引日 (共通営業日) のみを使う。
    1銘柄でも欠けた日を混ぜるとプール評価額が過小になるため。
    """
    codes = [code for code in holdings if code in bars and not bars[code].empty]
    missing = [code for code in holdings if code not in codes]
    if missing:
        raise ValueError(f'日足が取得できない銘柄があります: {", ".join(missing)}')

    index = None
    for code in codes:
        index = bars[code].index if index is None else index.intersection(bars[code].index)
    if index is None or len(index) == 0:
        raise ValueError('共通営業日がありません')

    def weighted(column: str) -> pd.Series:
        total = None
        for code in codes:
            series = bars[code][column].reindex(index) * holdings[code]
            total = series if total is None else total + series
        return total

    return pd.DataFrame(
        {'pool_low': weighted('low'), 'pool_close': weighted('close')},
        index=index,
    )


def worst_drawdown(close: pd.Series) -> dict:
    """終値ベースの最大ドローダウン (深さ・天井日・底日)。"""
    drawdown = close / close.cummax() - 1
    trough = drawdown.idxmin()
    return {
        'depth': float(drawdown.min()),
        'trough_date': trough,
        'peak_date': close.loc[:trough].idxmax(),
    }


def ltv_threshold_scan(pool_low: pd.Series, current_pool: float, loan: float,
                       thresholds=(0.60, 0.70, 0.85)) -> list[dict]:
    """各 LTV しきい値を踏む担保プール水準と、その過去到達実績。

    trigger_pool = 借入 / しきい値。現在のプールからここまで何%下げれば
    抵触するか (gap) と、期間中に実際に抵触した取引日数を返す。
    """
    scan = []
    for threshold in thresholds:
        trigger_pool = loan / threshold
        hit = days_at_or_below(pool_low, trigger_pool)
        hit.update({
            'threshold': threshold,
            'trigger_pool': trigger_pool,
            'gap': trigger_pool / current_pool - 1 if current_pool else float('nan'),
        })
        scan.append(hit)
    return scan
