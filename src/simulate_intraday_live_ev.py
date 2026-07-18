import argparse
import csv
from pathlib import Path

from build_same_day_bias_context import build_scope_bias, is_finished, race_scope_rows
from normalize_jv_odds_o1 import normalize as normalize_odds_file
from score_live_win_ev import build_aggs, group_by_race, latest_win_odds, read_csv, score_race


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def combine_odds(raw_odds_dir: Path, starts_path: Path, output_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(raw_odds_dir.glob("raw_rt_0b31_*.csv")):
        rows.extend(normalize_odds_file(path, starts_path))
    fields = [
        "race_id",
        "race_date",
        "course_code",
        "meeting",
        "day",
        "race_no",
        "bet_type",
        "horse_no",
        "selection",
        "odds",
        "odds_min",
        "odds_max",
        "popularity",
        "source",
        "observed_at",
        "record_type",
        "data_kubun",
        "created_date",
    ]
    write_csv(output_path, rows, fields)
    return rows


def build_bias_for_race(
    race: dict[str, str],
    race_meta: dict[str, dict[str, str]],
    results_by_race: dict[str, list[dict[str, str]]],
    starts_by_race: dict[str, list[dict[str, str]]],
) -> dict[tuple[str, str, str], dict[str, str]]:
    race_date = race["race_date"]
    as_of = race.get("post_time", "")
    completed_race_ids = {
        race_id
        for race_id, rows in results_by_race.items()
        if race_id in race_meta
        and race_meta[race_id].get("race_date") == race_date
        and race_meta[race_id].get("post_time", "") < as_of
    }
    course_code = race.get("course_code", "")
    surface_group = race.get("surface_group", "")
    bias_rows = [
        build_scope_bias(race_date, as_of, "all_day", "", "", completed_race_ids, results_by_race, starts_by_race),
        build_scope_bias(
            race_date,
            as_of,
            "same_course",
            course_code,
            "",
            race_scope_rows(completed_race_ids, race_meta, course_code, ""),
            results_by_race,
            starts_by_race,
        ),
        build_scope_bias(
            race_date,
            as_of,
            "same_course_surface",
            course_code,
            surface_group,
            race_scope_rows(completed_race_ids, race_meta, course_code, surface_group),
            results_by_race,
            starts_by_race,
        ),
    ]
    return {(row["race_date"], row["course_code"], row["surface_group"]): row for row in bias_rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run intraday rolling EV simulation for one race date.")
    parser.add_argument("--race-date", required=True)
    parser.add_argument("--training", default="data/model/target_win_training_2004_2025.csv")
    parser.add_argument("--race-history", default="data/model/target_races_2004_2026.csv")
    parser.add_argument("--pedigree", default="data/model/target_pedigree_1986_2026.csv")
    parser.add_argument("--races", required=True)
    parser.add_argument("--starts", required=True)
    parser.add_argument("--results", default="")
    parser.add_argument("--odds", default="")
    parser.add_argument("--raw-odds-dir", default="")
    parser.add_argument("--output-dir", default="outputs/intraday_simulations")
    parser.add_argument("--min-ev", type=float, default=0.20)
    parser.add_argument("--min-condition-count", type=int, default=500)
    parser.add_argument("--min-condition-edge", type=float, default=1.02)
    args = parser.parse_args()

    output_dir = Path(args.output_dir) / args.race_date
    races = [row for row in read_csv(Path(args.races)) if row["race_date"] == args.race_date]
    races.sort(key=lambda row: (row.get("post_time", ""), row["race_id"]))
    starts = [row for row in read_csv(Path(args.starts)) if row["race_date"] == args.race_date]
    starts_by_race = group_by_race(starts)
    race_meta = {row["race_id"]: row for row in races}

    if args.raw_odds_dir:
        odds_rows = combine_odds(Path(args.raw_odds_dir), Path(args.starts), output_dir / "combined_odds.csv")
    else:
        odds_rows = read_csv(Path(args.odds))
    odds_lookup = latest_win_odds(odds_rows)

    results_rows = []
    if args.results and Path(args.results).exists():
        results_rows = [row for row in read_csv(Path(args.results)) if row.get("race_id", "").startswith(args.race_date) and is_finished(row)]
    results_by_race = group_by_race(results_rows)

    race_history = {row["race_id"]: row for row in read_csv(Path(args.race_history))}
    pedigree = {row["horse_id"]: row for row in read_csv(Path(args.pedigree))} if args.pedigree else {}
    aggs = build_aggs(read_csv(Path(args.training)), race_history, pedigree, args.race_date)

    all_rows: list[dict[str, str]] = []
    top_rows: list[dict[str, str]] = []
    buy_rows: list[dict[str, str]] = []
    summary_rows: list[dict[str, str]] = []
    for race in races:
        race_id = race["race_id"]
        race_starts = starts_by_race.get(race_id, [])
        same_day_bias = build_bias_for_race(race, race_meta, results_by_race, starts_by_race)
        scored = score_race(
            race_starts,
            race,
            odds_lookup,
            aggs,
            pedigree,
            same_day_bias,
            args.min_ev,
            args.min_condition_count,
            args.min_condition_edge,
        )
        scored.sort(key=lambda row: -float(row.get("ev_per_yen") or "-999"))
        for rank, row in enumerate(scored, start=1):
            row["intraday_rank"] = str(rank)
            all_rows.append(row)
        top = scored[0] if scored else {}
        if top:
            top_rows.append(top)
        buys = [row for row in scored if row.get("decision") == "BUY"]
        buy_rows.extend(buys)
        bias_row = next(iter(same_day_bias.values()), {})
        summary_rows.append(
            {
                "race_id": race_id,
                "race_date": race["race_date"],
                "post_time": race.get("post_time", ""),
                "race_no": race.get("race_no", ""),
                "race_name": race.get("race_name", ""),
                "course_code": race.get("course_code", ""),
                "surface_group": race.get("surface_group", ""),
                "top_horse_no": top.get("horse_no", ""),
                "top_horse_name": top.get("horse_name", ""),
                "top_win_odds": top.get("win_odds", ""),
                "top_ev_per_yen": top.get("ev_per_yen", ""),
                "top_decision": top.get("decision", ""),
                "top_reason": top.get("reason", ""),
                "day_bias_scope": top.get("day_bias_scope", ""),
                "day_bias_status": top.get("day_bias_status", ""),
                "day_bias_completed_races": top.get("day_bias_completed_races", bias_row.get("completed_races", "")),
                "day_bias_factor": top.get("day_bias_factor", ""),
                "day_bias_summary": top.get("day_bias_summary", ""),
                "buy_count": str(len(buys)),
            }
        )
        write_csv(output_dir / f"race_{race_id}_ranking.csv", scored, list(dict.fromkeys([key for row in scored for key in row.keys()])))

    all_fields = list(dict.fromkeys([key for row in all_rows for key in row.keys()]))
    summary_fields = list(summary_rows[0].keys()) if summary_rows else []
    write_csv(output_dir / "all_rankings.csv", all_rows, all_fields)
    write_csv(output_dir / "top_candidates.csv", top_rows, all_fields)
    write_csv(output_dir / "buy_candidates.csv", buy_rows, all_fields)
    write_csv(output_dir / "race_summary.csv", summary_rows, summary_fields)
    print(f"races={len(races)} rows={len(all_rows)} buys={len(buy_rows)} output_dir={output_dir}")
    print(f"results_rows={len(results_rows)} odds_rows={len(odds_rows)}")


if __name__ == "__main__":
    main()
