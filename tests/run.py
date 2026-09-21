"""全テストを実行: python tests/run.py"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_bottom_analysis  # noqa: E402
import test_portfolio  # noqa: E402

MODULES = [test_portfolio, test_bottom_analysis]


def main() -> int:
    failures = 0
    total = 0
    for module in MODULES:
        print(f'\n[{module.__name__}]')
        cases = [(name, fn) for name, fn in sorted(vars(module).items())
                 if name.startswith('test_') and callable(fn)]
        total += len(cases)
        for name, fn in cases:
            try:
                fn()
            except Exception as error:  # noqa: BLE001
                failures += 1
                print(f'  FAIL {name}: {type(error).__name__}: {error}')
            else:
                print(f'  ok   {name}')
    print(f'\n{total - failures}/{total} passed')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
