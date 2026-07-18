import argparse
import csv
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from build_same_day_bias_context import is_finished
from normalize_jv_odds_o1 import normalize as normalize_odds_file
from score_live_place_ev import (
    build_place_model,
    latest_odds,
    score_race as score_place_race,
)
from score_live_win_ev import build_aggs, group_by_race, read_csv
from score_live_win_ev import score_race as score_win_race
from simulate_intraday_live_ev import build_bias_for_race


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def all_fields(rows: list[dict[str, str]]) -> list[str]:
    return list(dict.fromkeys(key for row in rows for key in row.keys()))


def fmt_pct(raw: str) -> str:
    try:
        return f"{float(raw) * 100:.1f}%"
    except (TypeError, ValueError):
        return "-"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-command live cutoff run: normalize odds, same-day bias, win EV + place EV, daily summary."
    )
    parser.add_argument("--race-date", required=True)
    parser.add_argument("--race-id", default="", help="score only this race (default: every race with odds)")
    parser.add_argument("--races", required=True, help="normalized race card CSV (check race_date inside!)")
    parser.add_argument("--starts", required=True)
    parser.add_argument("--raw-odds-dir", default="", help="directory with raw_rt_0b31_*.csv snapshots")
    parser.add_argument("--odds", default="", help="already-normalized odds CSV (alternative to --raw-odds-dir)")
    parser.add_argument("--results", default="data/model/win_training_minimal.csv", help="same-day finished results for bias")
    parser.add_argument("--training", default="data/model/target_win_training_2004_2025.csv")
    parser.add_argument("--race-history", default="data/model/target_races_2004_2026.csv")
    parser.add_argument("--pedigree", default="data/model/target_pedigree_1986_2026.csv")
    parser.add_argument("--min-ev", type=float, default=0.20)
    parser.add_argument("--min-condition-count", type=int, default=500)
    parser.add_argument("--min-condition-edge", type=float, default=1.02)
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else Path("outputs/live_predictions") / args.race_date
    output_dir.mkdir(parents=True, exist_ok=True)

    races = [row for row in read_csv(Path(args.races)) if row["race_date"] == args.race_date]
    if not races:
        raise SystemExit(f"no races for {args.race_date} in {args.races} — check race_date inside the file")
    races.sort(key=lambda row: (row.get("post_time", ""), row["race_id"]))
    race_meta = {row["race_id"]: row for row in races}
    starts_by_race = group_by_race([row for row in read_csv(Path(args.starts)) if row["race_date"] == args.race_date])

    if args.raw_odds_dir:
        odds_rows: list[dict[str, str]] = []
        for path in sorted(Path(args.raw_odds_dir).glob("raw_rt_0b31_*.csv")):
            odds_rows.extend(normalize_odds_file(path, Path(args.starts)))
        write_csv(output_dir / "combined_odds.csv", odds_rows, all_fields(odds_rows))
    elif args.odds:
        odds_rows = read_csv(Path(args.odds))
    else:
        raise SystemExit("provide --raw-odds-dir or --odds")
    win_lookup = latest_odds(odds_rows, "win")
    place_lookup = latest_odds(odds_rows, "place")

    results_rows = []
    if args.results and Path(args.results).exists():
        results_rows = [
            row
            for row in read_csv(Path(args.results))
            if row.get("race_date") == args.race_date and is_finished(row)
        ]
    results_by_race = group_by_race(results_rows)

    print("building win model aggregates...")
    race_history = {row["race_id"]: row for row in read_csv(Path(args.race_history))}
    pedigree = {row["horse_id"]: row for row in read_csv(Path(args.pedigree))} if args.pedigree else {}
    aggs = build_aggs(read_csv(Path(args.training)), race_history, pedigree, args.race_date)
    print("building place model...")
    place_model = build_place_model(Path(args.training), args.race_date)

    summary_rows: list[dict[str, str]] = []
    buy_rows: list[dict[str, str]] = []
    targets = [race for race in races if not args.race_id or race["race_id"] == args.race_id]
    for race in targets:
        race_id = race["race_id"]
        race_starts = starts_by_race.get(race_id, [])
        if not race_starts:
            continue
        has_odds = any((race_id, s["horse_no"]) in win_lookup for s in race_starts)
        if not has_odds and not args.race_id:
            continue

        same_day_bias = build_bias_for_race(race, race_meta, results_by_race, starts_by_race)
        win_scored = score_win_race(
            race_starts, race, win_lookup, aggs, pedigree, same_day_bias,
            args.min_ev, args.min_condition_count, args.min_condition_edge,
        )
        win_scored.sort(key=lambda row: -float(row.get("ev_per_yen") or "-999"))
        place_scored = score_place_race(
            race_starts, race, win_lookup, place_lookup, place_model, allow_buy=False, min_ev=1.20,
        )
        write_csv(output_dir / f"race_{race_id}_win_ev.csv", win_scored, all_fields(win_scored))
        write_csv(output_dir / f"race_{race_id}_place_ev.csv", place_scored, all_fields(place_scored))

        top_win = win_scored[0] if win_scored else {}
        top_place = place_scored[0] if place_scored else {}
        buys = [row for row in win_scored if row.get("decision") == "BUY"]
        buy_rows.extend(buys)
        summary_rows.append(
            {
                "race_id": race_id,
                "race_no": race.get("race_no", ""),
                "race_name": race.get("race_name", ""),
                "course_code": race.get("course_code", ""),
                "post_time": race.get("post_time", ""),
                "top_win_horse_no": top_win.get("horse_no", ""),
                "top_win_horse_name": top_win.get("horse_name", ""),
                "top_win_odds": top_win.get("win_odds", ""),
                "top_win_probability": top_win.get("probability", ""),
                "top_win_ev_per_yen": top_win.get("ev_per_yen", ""),
                "top_win_decision": top_win.get("decision", ""),
                "top_win_reason": top_win.get("reason", ""),
                "top_place_horse_no": top_place.get("horse_no", ""),
                "top_place_horse_name": top_place.get("horse_name", ""),
                "top_place_odds_min": top_place.get("place_odds_min", ""),
                "top_place_odds_max": top_place.get("place_odds_max", ""),
                "top_place_probability": top_place.get("place_probability", ""),
                "top_place_ev_lower": top_place.get("ev_return_per_yen_lower", ""),
                "top_place_decision": top_place.get("decision", ""),
                "day_bias_status": top_win.get("day_bias_status", ""),
                "day_bias_factor": top_win.get("day_bias_factor", ""),
                "buy_count": str(len(buys)),
            }
        )

        course = race.get("course_code", "")
        print(
            f"race {race.get('race_no', '?')}R course {course} post {race.get('post_time', '?')} | "
            f"win #{top_win.get('horse_no', '-')} {top_win.get('horse_name', '-')} "
            f"odds {top_win.get('win_odds', '-')} p {fmt_pct(top_win.get('probability'))} "
            f"ev {top_win.get('ev_per_yen', '-')} {top_win.get('decision', '-')} | "
            f"place #{top_place.get('horse_no', '-')} {top_place.get('horse_name', '-')} "
            f"odds {top_place.get('place_odds_min', '-')}-{top_place.get('place_odds_max', '-')} "
            f"p {fmt_pct(top_place.get('place_probability'))} "
            f"evL {top_place.get('ev_return_per_yen_lower', '-')} {top_place.get('decision', '-')} | "
            f"buys {len(buys)}"
        )

    scored_now = len(summary_rows)
    # merge with prior invocations so per-race cutoff runs accumulate over the day
    summary_path = output_dir / f"daily_summary_{args.race_date}.csv"
    if summary_path.exists():
        scored_ids = {row["race_id"] for row in summary_rows}
        summary_rows = [row for row in read_csv(summary_path) if row["race_id"] not in scored_ids] + summary_rows
        summary_rows.sort(key=lambda row: (row.get("post_time", ""), row["race_id"]))
    if summary_rows:
        write_csv(summary_path, summary_rows, all_fields(summary_rows))

    buy_path = output_dir / f"buy_candidates_{args.race_date}.csv"
    if buy_path.exists():
        scored_ids = {race["race_id"] for race in targets}
        buy_rows = [row for row in read_csv(buy_path) if row["race_id"] not in scored_ids] + buy_rows
    write_csv(
        buy_path,
        buy_rows,
        all_fields(buy_rows) if buy_rows else ["decision", "race_id", "horse_no", "horse_name", "ev_per_yen"],
    )
    print(f"races_scored={scored_now} day_total={len(summary_rows)} win_buys={len(buy_rows)} output_dir={output_dir}")
    if not buy_rows:
        print("no BUY candidates - PASS day (expected under current gates)")


if __name__ == "__main__":
    main()
