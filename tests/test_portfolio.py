"""portfolio.py の単体テスト (現値を与えるだけ / ネットワーク不要)"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import portfolio as pf  # noqa: E402

# fallback_price をそのまま現値として使ったときの期待値
FALLBACK = {code: float(info['fallback_price']) for code, info in pf.STOCKS.items()}
COLLATERAL = 15000 * 2406 + 50000 * 553 + 20000 * 1328 + 25000 * 1000   # 115,300,000
NISSAN = 100000 * 381                                                    # 38,100,000
DIVIDEND = 15000 * 92 + 50000 * 30 + 20000 * 62 + 25000 * 40             # 5,120,000
NISSAN_SHATAI_COST = 25000 * 966                                         # 24,150,000


def test_current_state():
    """保持するのは現在の状態だけ (約定履歴は持たない)。"""
    assert not hasattr(pf, 'TRADES')
    assert not hasattr(pf, 'REALIZED_TRADES')
    assert not hasattr(pf, 'trade_summary')

    assert '7203' not in pf.STOCKS                   # トヨタは売却済みで不在
    assert pf.COLLAT_CODES == ['2674', '8291', '5869', '7222']
    # 日産車体は買い増し分を含む全25,000株が担保、平均取得 966円
    assert pf.STOCKS['7222']['shares'] == 25000
    assert pf.STOCKS['7222']['avg_cost'] == 966
    assert '7222' in pf.COLLAT_CODES
    assert pf.LOAN_BALANCE == 80_000_000
    assert pf.CASH_BUFFER == 12_000_000
    assert pf.LOAN_FLOOR == 50_000_000
    assert pf.LOAN_BALANCE > pf.LOAN_FLOOR


def test_collateral_includes_every_share_of_pledged_stocks():
    """担保銘柄は保有全株が担保プールに入る (一部だけ差入れはしない)。"""
    snap = pf.summarize(FALLBACK)
    expected = sum(pf.STOCKS[c]['shares'] * FALLBACK[c] for c in pf.COLLAT_CODES)
    assert snap.collateral == expected
    # 日産車体の寄与は 25,000株ぶん
    assert 25000 * FALLBACK['7222'] == 25_000_000
    # 日産(LTV対象外)は含まれない
    assert pf.NISSAN_CODE not in pf.COLLAT_CODES
    assert snap.collateral + snap.nissan_value == snap.total_value


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
    assert snap.collateral == COLLATERAL == 115_300_000
    assert snap.nissan_value == NISSAN
    assert snap.total_value == COLLATERAL + NISSAN
    assert snap.total_dividend == DIVIDEND
    assert round(snap.ltv, 2) == 69.38
    assert snap.room70 == COLLATERAL * 0.70 - 80_000_000 == 710_000
    assert snap.pf_total == COLLATERAL + NISSAN + pf.CASH_BUFFER
    assert snap.nav == snap.pf_total - 80_000_000 == 85_400_000


def test_summarize_accepts_alternative_loan():
    snap = pf.summarize(FALLBACK, loan=65_000_000)
    assert round(snap.ltv, 2) == round(65_000_000 / COLLATERAL * 100, 2)
    assert snap.room70 == COLLATERAL * 0.70 - 65_000_000
    # 担保・配当は借入に依存しない
    assert snap.collateral == COLLATERAL and snap.total_dividend == DIVIDEND


def test_position_costs_covers_only_registered_avg_cost():
    rows, totals = pf.position_costs(FALLBACK)
    assert [r['code'] for r in rows] == ['7222']   # avg_cost を持つのは日産車体だけ
    row = rows[0]
    assert row['shares'] == 25000 and row['avg_cost'] == 966.0
    assert row['cost'] == NISSAN_SHATAI_COST == 24_150_000
    assert row['value'] == 25_000_000
    assert row['pl'] == 850_000
    assert round(row['pl_pct'], 2) == 3.52
    assert totals['cost'] == row['cost'] and totals['pl'] == row['pl']
    assert totals['covered'] == 1 and totals['total_positions'] == len(pf.STOCKS)


def test_position_costs_tracks_losses():
    prices = dict(FALLBACK, **{'7222': 800.0})
    rows, totals = pf.position_costs(prices)
    assert rows[0]['pl'] == 25000 * 800 - NISSAN_SHATAI_COST == -4_150_000
    assert totals['pl_pct'] < 0


def test_threshold_progress():
    steps = pf.threshold_progress(COLLATERAL)
    assert [s['threshold'] for s in steps] == [0.60, 0.70, 0.85]
    by = {s['threshold']: s for s in steps}

    # 60%枠はすでに超過
    assert by[0.60]['cap'] == COLLATERAL * 0.60 == 69_180_000
    assert by[0.60]['room'] < 0 and by[0.60]['fill'] > 1.0

    # 70%枠は残り710万。担保が0.9%下げると抵触水準 (借入/0.7) に届く
    assert by[0.70]['room'] == 710_000
    assert round(by[0.70]['trigger']) == round(80_000_000 / 0.70) == 114_285_714
    assert round(by[0.70]['drop'] * 100, 2) == -0.88

    # 85%枠まではまだ18%の余地
    assert round(by[0.85]['drop'] * 100, 1) == -18.4
    assert round(by[0.85]['fill'], 4) == round(80_000_000 / (COLLATERAL * 0.85), 4)


def test_threshold_progress_handles_zero_collateral():
    steps = pf.threshold_progress(0.0)
    assert all(math.isinf(s['fill']) for s in steps)
    assert all(math.isnan(s['drop']) for s in steps)


def test_ltv_status_bands_point_at_the_next_line():
    # バンドの色は「超えた線」ではなく「次に向かう線」で決まる
    assert pf.ltv_status(55.0)['icon'] == '🟢'
    assert pf.ltv_status(55.0)['label'] == '目標レンジ内'
    assert pf.ltv_status(55.0)['next_threshold'] == 0.60

    warned = pf.ltv_status(69.38)
    assert warned['icon'] == '🟡' and warned['label'] == '60%超過'
    assert warned['next_threshold'] == 0.70 and warned['next_label'] == '警告'

    serious = pf.ltv_status(72.0)
    assert serious['icon'] == '🔴' and serious['next_threshold'] == 0.85

    worst = pf.ltv_status(90.0)
    assert worst['icon'] == '🔴' and worst['next_threshold'] is None
    assert worst['breached'] == [0.60, 0.70, 0.85]


def test_ltv_status_boundaries_are_inclusive():
    # ちょうど 60.0% は「60%超過」側に入れる (枠を使い切っている)
    assert pf.ltv_status(60.0)['label'] == '60%超過'
    assert pf.ltv_status(59.99)['label'] == '目標レンジ内'
