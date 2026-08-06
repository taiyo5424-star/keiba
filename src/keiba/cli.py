"""keiba CLI — ローカル運用の入口。

使用例:
  keiba ev      --probs 0.28,0.18,0.14 --odds 2.4,5.1,8.0
  keiba kelly   --probs 0.28,0.18 --odds 2.4,5.1 --fraction 0.25 --bankroll 100000
  keiba decide  --probs 0.28,0.18 --odds 2.4,5.1 --bankroll 100000 --min-ev 1.05
  keiba win5    --pool 4e8 --carryover 2e8
  keiba summary --db data/keiba.sqlite
"""

from __future__ import annotations

import argparse
import sys


def _floats(s: str) -> list[float]:
    return [float(x) for x in s.split(",") if x.strip()]


def cmd_ev(args) -> int:
    from keiba.ev import ev_table

    df = ev_table(_floats(args.probs), _floats(args.odds), min_ev=args.min_ev)
    print(df.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    return 0


def cmd_kelly(args) -> int:
    from keiba.kelly import kelly_exclusive_outcomes

    probs, odds = _floats(args.probs), _floats(args.odds)
    f = kelly_exclusive_outcomes(probs, odds, fraction=args.fraction)
    total = 0.0
    for i, (frac, o) in enumerate(zip(f, odds), start=1):
        if frac > 0:
            stake = int(frac * args.bankroll // 100) * 100
            total += frac
            print(f"  {i}番 (odds {o}): {frac*100:.2f}% = {stake:,}円")
    print(f"  合計投下率: {total*100:.2f}%")
    return 0


def cmd_decide(args) -> int:
    from keiba.decision import DecisionPolicy, decide_win_bets

    policy = DecisionPolicy(min_ev=args.min_ev, kelly_fraction=args.fraction)
    orders = decide_win_bets(
        args.race_id, _floats(args.probs), _floats(args.odds),
        bankroll=args.bankroll, policy=policy,
    )
    if not orders:
        print("発注なし(条件を満たす馬券がありません)")
        return 0
    for o in orders:
        print(f"  {o.race_id} 単勝 {o.selection}番 {o.stake:,}円 "
              f"(EV {o.ev:.3f} / p={o.prob:.3f} / odds {o.odds})")
    print(f"  合計 {sum(o.stake for o in orders):,}円")
    return 0


def cmd_win5(args) -> int:
    from keiba.win5 import breakeven_carryover, effective_payout_rate

    r_eff = effective_payout_rate(args.pool, args.carryover, args.rate)
    be = breakeven_carryover(args.pool, args.rate)
    print(f"実効還元率: {r_eff:.4f} ({'プラスサム' if r_eff > 1 else 'マイナスサム'})")
    print(f"損益分岐キャリーオーバー: {be:,.0f}円 (現在 {args.carryover:,.0f}円)")
    return 0


def cmd_summary(args) -> int:
    from keiba.store import connect, yearly_betting_summary

    conn = connect(args.db)
    df = yearly_betting_summary(conn)
    if df.empty:
        print("購入記録がありません")
    else:
        print(df.to_string(index=False))
    return 0


def cmd_test(args) -> int:
    import pytest

    return pytest.main(["-q", "tests/"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="keiba", description="期待値ベース馬券分析CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ev", help="EVテーブルを表示")
    p.add_argument("--probs", required=True)
    p.add_argument("--odds", required=True)
    p.add_argument("--min-ev", type=float, default=0.0)
    p.set_defaults(fn=cmd_ev)

    p = sub.add_parser("kelly", help="レース内ケリー配分")
    p.add_argument("--probs", required=True)
    p.add_argument("--odds", required=True)
    p.add_argument("--fraction", type=float, default=0.25)
    p.add_argument("--bankroll", type=float, default=100_000)
    p.set_defaults(fn=cmd_kelly)

    p = sub.add_parser("decide", help="ポリシー適用済みの発注案を出力")
    p.add_argument("--race-id", default="RACE")
    p.add_argument("--probs", required=True)
    p.add_argument("--odds", required=True)
    p.add_argument("--bankroll", type=float, required=True)
    p.add_argument("--min-ev", type=float, default=1.05)
    p.add_argument("--fraction", type=float, default=0.25)
    p.set_defaults(fn=cmd_decide)

    p = sub.add_parser("win5", help="WIN5のキャリーオーバー込み実効還元率")
    p.add_argument("--pool", type=float, required=True)
    p.add_argument("--carryover", type=float, default=0.0)
    p.add_argument("--rate", type=float, default=0.70)
    p.set_defaults(fn=cmd_win5)

    p = sub.add_parser("summary", help="購入記録の年別収支(税務・検証用)")
    p.add_argument("--db", required=True)
    p.set_defaults(fn=cmd_summary)

    p = sub.add_parser("test", help="テストスイートを実行")
    p.set_defaults(fn=cmd_test)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
