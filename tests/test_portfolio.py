"""portfolio.py の単体テスト (現値を与えるだけ / ネットワーク不要)"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import portfolio as pf  # noqa: E402

# fallback_price をそのまま現値として使ったときの期待値
FALLBACK = {code: float(info['fallback_price']) for code, info in pf.STOCKS.items()}
COLLATERAL = 15000 * 2406 + 50000 * 553 + 20000 * 1328 + 15000 * 1000   # 105,300,000
NISSAN = 100000 * 381                                                    # 38,100,000
DIVIDEND = 15000 * 92 + 50000 * 30 + 20000 * 62 + 15000 * 40             # 4,720,000


def test_constants_reflect_toyota_sale():
    assert '7203' not in pf.STOCKS
    assert pf.COLLAT_CODES == ['2674', '8291', '5869', '7222']
    assert pf.LOAN_BALANCE == 65_000_000
    assert pf.LOAN_FLOOR == 50_000_000
    trade = pf.REALIZED_TRADES[0]
    assert trade['code'] == '7203' and trade['shares'] == 5000
    assert trade['proceeds'] == 15_000_000 and trade['gain'] == 700_000
    # 売却代金と返済額が一致していること (借入 8,000万 → 6,500万)
    assert pf.LOAN_BALANCE + trade['proceeds'] == 80_000_000


def test_resolve_prices_falls_back_per_code():
    raw = {'2674': 2500.0, '8291': None, '5869': 0, '7222': 1100.0}
    prices = pf.resolve_prices(raw)
    assert prices['2674'] == 2500.0                     # 取得できた値
    assert prices['8291'] == 553                        # None → fallback
    assert prices['5869'] == 1328                       # 0 も fallback 扱い
    assert prices['7201'] == 381                        # raw に無い銘柄も埋まる
    assert set(prices) == set(pf.STOCKS)


def test_summarize():
    snap = pf.summarize(FALLBACK)
    assert snap.collateral == COLLATERAL
    assert snap.nissan_value == NISSAN
    assert snap.total_value == COLLATERAL + NISSAN
    assert snap.total_dividend == DIVIDEND
    assert round(snap.ltv, 2) == round(65_000_000 / COLLATERAL * 100, 2) == 61.73
    assert snap.room70 == COLLATERAL * 0.70 - 65_000_000 == 8_710_000
    assert snap.pf_total == COLLATERAL + NISSAN + pf.CASH_BUFFER
    assert snap.nav == snap.pf_total - 65_000_000 == 84_400_000


def test_summarize_accepts_alternative_loan():
    snap = pf.summarize(FALLBACK, loan=80_000_000)
    assert round(snap.ltv, 2) == round(80_000_000 / COLLATERAL * 100, 2)
    assert snap.room70 == COLLATERAL * 0.70 - 80_000_000
    # 担保・配当は借入に依存しない
    assert snap.collateral == COLLATERAL and snap.total_dividend == DIVIDEND


def test_realized_summary_reconstructs_pre_sale_ltv():
    realized = pf.realized_summary(COLLATERAL)
    assert realized['repaid'] == 15_000_000
    assert realized['gain'] == 700_000
    assert realized['pre_loan'] == 80_000_000
    # 売却前: 借入8,000万 / 担保 105,300,000 + 15,000,000
    assert round(realized['pre_ltv'], 1) == 66.5
    assert round(realized['ltv'], 1) == 61.7
    assert round(realized['ltv_delta'], 1) == -4.8
    assert realized['ltv_delta'] < 0          # 返済なので必ず改善


def test_realized_summary_ignores_non_repayment_uses():
    trades = [
        {'proceeds': 3_000_000, 'gain': 100_000, 'use': '現金化'},
        {'proceeds': 5_000_000, 'gain': -200_000, 'use': '借入返済'},
    ]
    realized = pf.realized_summary(COLLATERAL, trades=trades)
    assert realized['repaid'] == 5_000_000     # 現金化ぶんは返済に数えない
    assert realized['gain'] == -100_000        # 損益は全件合算


def test_realized_summary_handles_zero_collateral():
    realized = pf.realized_summary(0.0, trades=[])
    assert math.isnan(realized['ltv'])
    assert realized['repaid'] == 0 and realized['gain'] == 0


def test_threshold_progress():
    steps = pf.threshold_progress(COLLATERAL)
    assert [s['threshold'] for s in steps] == [0.60, 0.70, 0.85]
    assert [s['icon'] for s in steps] == ['🟢', '🟡', '🔴']
    by_threshold = {s['threshold']: s for s in steps}
    assert by_threshold[0.60]['cap'] == COLLATERAL * 0.60 == 63_180_000
    # 現在LTV 61.7% なので 60%枠は超過 (fill > 1)、70%/85%枠は未達
    assert by_threshold[0.60]['fill'] > 1.0
    assert by_threshold[0.70]['fill'] < 1.0
    assert round(by_threshold[0.85]['fill'], 4) == round(65_000_000 / (COLLATERAL * 0.85), 4)


def test_threshold_progress_handles_zero_collateral():
    steps = pf.threshold_progress(0.0)
    assert all(math.isinf(s['fill']) for s in steps)
