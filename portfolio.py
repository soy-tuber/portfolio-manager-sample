"""ポートフォリオの定義と集計 (Streamlit / ネットワーク非依存)

数字の出どころをここに集約し、表示は views/ 側に置く。
このモジュールは streamlit を import しないため単体テスト可能。
"""

from __future__ import annotations

from dataclasses import dataclass

# =========================
# 保有銘柄 / 借入
# =========================
STOCKS: dict[str, dict] = {
    '2674': {'name': 'ハードオフ', 'shares': 15000, 'dividend': 92, 'role': '担保', 'fallback_price': 2406},
    '8291': {'name': '日産東京HD', 'shares': 50000, 'dividend': 30, 'role': '担保', 'fallback_price': 553},
    '5869': {'name': '早稲田学習研究会', 'shares': 20000, 'dividend': 62, 'role': '担保', 'fallback_price': 1328},
    '7222': {'name': '日産車体', 'shares': 25000, 'dividend': 40, 'role': '担保', 'fallback_price': 1000,
             'avg_cost': 966},
    '7201': {'name': '日産自動車', 'shares': 100000, 'dividend': 0, 'role': 'LTV対象外', 'fallback_price': 381},
}
COLLAT_CODES = ['2674', '8291', '5869', '7222']
NISSAN_CODE = '7201'

LOAN_BALANCE = 80_000_000       # 8,000万 (日産車体買い増しに伴う借り増し後)
LOAN_FLOOR = 50_000_000         # 下限 5,000万
CASH_BUFFER = 12_000_000        # 1,200万
ANNUAL_ADD_BUDGET = 10_000_000  # 日産買い増し 年1,000万ペース

# 約定履歴 (新しい順)。side は 'buy' / 'sell'。
# gain は売却時の確定損益のみ。amount が不明な約定は None。
TRADES: list[dict] = [
    {
        'date': '2026-09-29',
        'code': '7222',
        'name': '日産車体',
        'side': 'buy',
        'action': '買い増し',
        'shares': 10000,
        'amount': None,
        'gain': None,
        'funding': '借り増し',
        'note': '合計25,000株、平均取得価格966円。'
                '借入 6,500万 → 8,000万、現金 600万 → 1,200万。',
    },
    {
        'date': '2026-09-18',
        'code': '7203',
        'name': 'トヨタ自動車',
        'side': 'sell',
        'action': '売却 (成行)',
        'shares': 5000,
        'amount': 15_000_000,     # 売却代金 = 借入返済額
        'gain': 700_000,          # 確定益
        'funding': '借入返済',
        'note': '担保プールから除外。借入 8,000万 → 6,500万。',
    },
]

# LTV しきい値 (Rakuten Bank) と表示色。
# 色はステータス配色の固定値 (good / warning / critical)。
# Light / Dark どちらでも判読でき、記号+ラベル+位置でも区別できるようにしている
# (色単独に意味を持たせない)。
LTV_THRESHOLDS = [
    (0.60, '🟢', '通常', '#0ca30c'),
    (0.70, '🟡', '警告', '#fab219'),
    (0.85, '🔴', '強制決済', '#d03b3b'),
]
SERIES_COLOR = '#2a78d6'   # カテゴリ配色スロット1 (blue)

PERIOD_OPTIONS = {'1年': '1y', '2年': '2y', '5年': '5y', '10年': '10y'}


# =========================
# 集計
# =========================
def resolve_prices(raw: dict[str, float | None]) -> dict[str, float]:
    """取得失敗した銘柄を fallback_price で埋めた現値表を返す。"""
    return {
        code: (raw.get(code) or STOCKS[code]['fallback_price'])
        for code in STOCKS
    }


@dataclass(frozen=True)
class Snapshot:
    """現値から導かれる評価額・LTV 一式。"""
    prices: dict[str, float]
    total_value: float       # 全保有の時価
    total_dividend: float    # 年間配当合計
    collateral: float        # 担保プール (LTV対象)
    nissan_value: float      # 日産 (LTV対象外)
    ltv: float               # %
    room70: float            # 70%枠余力 (円)
    pf_total: float          # 担保 + 日産 + 現金
    nav: float               # PF - 借入


def summarize(prices: dict[str, float], loan: float = LOAN_BALANCE) -> Snapshot:
    collateral = sum(STOCKS[c]['shares'] * prices[c] for c in COLLAT_CODES)
    nissan_value = STOCKS[NISSAN_CODE]['shares'] * prices[NISSAN_CODE]
    total_value = sum(STOCKS[c]['shares'] * prices[c] for c in STOCKS)
    total_dividend = sum(STOCKS[c]['shares'] * STOCKS[c]['dividend'] for c in STOCKS)
    pf_total = collateral + nissan_value + CASH_BUFFER
    return Snapshot(
        prices=prices,
        total_value=total_value,
        total_dividend=total_dividend,
        collateral=collateral,
        nissan_value=nissan_value,
        ltv=loan / collateral * 100,
        room70=collateral * 0.70 - loan,
        pf_total=pf_total,
        nav=pf_total - loan,
    )


def trade_summary(trades: list[dict] | None = None) -> dict:
    """約定履歴の集計。確定損益は売却のみから積む。"""
    trades = TRADES if trades is None else trades
    sells = [t for t in trades if t['side'] == 'sell']
    buys = [t for t in trades if t['side'] == 'buy']
    return {
        'realized_gain': sum(t.get('gain') or 0 for t in sells),
        'sell_count': len(sells),
        'buy_count': len(buys),
        'sold_shares': sum(t['shares'] for t in sells),
        'bought_shares': sum(t['shares'] for t in buys),
    }


def position_costs(prices: dict[str, float]) -> tuple[list[dict], dict]:
    """平均取得価格が分かっている銘柄の取得原価と含み損益。

    avg_cost を持たない銘柄は対象外 (行を作らない)。
    合計は「原価が分かっている分だけ」の合計であることに注意。
    """
    rows = []
    for code, info in STOCKS.items():
        avg_cost = info.get('avg_cost')
        if avg_cost is None:
            continue
        cost = info['shares'] * avg_cost
        value = info['shares'] * prices[code]
        rows.append({
            'code': code,
            'name': info['name'],
            'shares': info['shares'],
            'avg_cost': float(avg_cost),
            'cost': cost,
            'value': value,
            'pl': value - cost,
            'pl_pct': (value / cost - 1) * 100 if cost else float('nan'),
        })
    total_cost = sum(r['cost'] for r in rows)
    total_value = sum(r['value'] for r in rows)
    totals = {
        'cost': total_cost,
        'value': total_value,
        'pl': total_value - total_cost,
        'pl_pct': (total_value / total_cost - 1) * 100 if total_cost else float('nan'),
        'covered': len(rows),
        'total_positions': len(STOCKS),
    }
    return rows, totals


def threshold_progress(collateral: float, loan: float = LOAN_BALANCE) -> list[dict]:
    """各しきい値について、枠の消化率と抵触までの距離。

    trigger = そのしきい値に触れる担保プール水準 (借入 / しきい値)。
    drop    = 現在の担保からそこまでの変化率 (負なら余裕、正なら超過済み)。
    """
    steps = []
    for threshold, icon, label, color in LTV_THRESHOLDS:
        cap = collateral * threshold
        trigger = loan / threshold
        steps.append({
            'threshold': threshold,
            'icon': icon,
            'label': label,
            'color': color,
            'cap': cap,                                     # 借りられる上限
            'room': cap - loan,                             # 枠の残り (円)
            'fill': loan / cap if cap else float('inf'),    # 枠の消化率
            'trigger': trigger,                             # 抵触する担保水準
            'drop': trigger / collateral - 1 if collateral else float('nan'),
        })
    return steps


def ltv_status(ltv: float) -> dict:
    """現在のLTVが属するバンドと、次に触れるしきい値。

    バンドの深刻度は「次に向かっている線」で表す。60%を超えた時点で
    次は70%(警告)なので 🟡 になる — 超えた線の色ではない。
    """
    breached = [s for s in LTV_THRESHOLDS if ltv >= s[0] * 100]
    upcoming = [s for s in LTV_THRESHOLDS if ltv < s[0] * 100]
    following = upcoming[0] if upcoming else None
    return {
        'breached': [s[0] for s in breached],
        'icon': following[1] if following else LTV_THRESHOLDS[-1][1],
        'label': (f"{breached[-1][0]*100:.0f}%超過" if breached else '目標レンジ内'),
        'next_threshold': following[0] if following else None,
        'next_icon': following[1] if following else None,
        'next_label': following[2] if following else None,
    }
