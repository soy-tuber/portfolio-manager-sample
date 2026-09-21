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
    '7222': {'name': '日産車体', 'shares': 15000, 'dividend': 40, 'role': '担保', 'fallback_price': 1000},
    '7201': {'name': '日産自動車', 'shares': 100000, 'dividend': 0, 'role': 'LTV対象外', 'fallback_price': 381},
}
COLLAT_CODES = ['2674', '8291', '5869', '7222']
NISSAN_CODE = '7201'

LOAN_BALANCE = 65_000_000       # 6,500万 (トヨタ売却代金1,500万を返済充当後)
LOAN_FLOOR = 50_000_000         # 下限 5,000万
CASH_BUFFER = 6_000_000         # 600万
ANNUAL_ADD_BUDGET = 10_000_000  # 日産買い増し 年1,000万ペース

# 確定済みの売買 (新しい順)。売却代金の使途まで記録する。
REALIZED_TRADES: list[dict] = [
    {
        'date': '2026-09-18',
        'code': '7203',
        'name': 'トヨタ自動車',
        'action': '売却 (成行)',
        'shares': 5000,
        'proceeds': 15_000_000,   # 売却代金 = 借入返済額
        'gain': 700_000,          # 確定益
        'use': '借入返済',
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


def realized_summary(collateral: float, loan: float = LOAN_BALANCE,
                     trades: list[dict] | None = None) -> dict:
    """確定売買の累計と、借入返済によるLTV改善の概算。

    売却前の姿は「売却銘柄の時価 = 売却代金」「残り銘柄は現値」とみなして
    再構成する (あくまで概算)。
    """
    trades = REALIZED_TRADES if trades is None else trades
    repaid = sum(t['proceeds'] for t in trades if t['use'] == '借入返済')
    gain = sum(t['gain'] for t in trades)
    pre_collateral = collateral + repaid
    pre_loan = loan + repaid
    pre_ltv = pre_loan / pre_collateral * 100 if pre_collateral else float('nan')
    ltv = loan / collateral * 100 if collateral else float('nan')
    return {
        'repaid': repaid,
        'gain': gain,
        'pre_loan': pre_loan,
        'pre_ltv': pre_ltv,
        'ltv': ltv,
        'ltv_delta': ltv - pre_ltv,
    }


def threshold_progress(collateral: float, loan: float = LOAN_BALANCE) -> list[dict]:
    """各しきい値の枠と、借入がその枠を何割埋めているか。"""
    return [
        {
            'threshold': threshold,
            'icon': icon,
            'label': label,
            'color': color,
            'cap': collateral * threshold,
            'fill': loan / (collateral * threshold) if collateral else float('inf'),
        }
        for threshold, icon, label, color in LTV_THRESHOLDS
    ]
