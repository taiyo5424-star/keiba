import argparse
import csv
from collections import defaultdict
from pathlib import Path

from predict_historical_win_ev import clamp
from score_live_win_ev import gate_bucket, read_csv


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def is_finished(row: dict[str, str]) -> bool:
    value = (row.get("finish_position") or row.get("finish_rank") or "").strip()
    return value.isdigit() and int(value) > 0


def is_winner(row: dict[str, str]) -> bool:
    if (row.get("label_win") or row.get("win_result") or "").strip() == "1":
        return True
    value = (row.get("finish_position") or row.get("finish_rank") or "").strip()
    return value == "1"


def hhmm(value: str) -> str:
    value = (value or "").strip()
    return value.zfill(4) if value else ""


def parse_float(value: str | None) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except ValueError:
        return None


def race_scope_rows(
    completed_race_ids: set[str],
    race_meta: dict[str, dict[str, str]],
    course_code: str,
    surface_group: str,
) -> set[str]:
    selected = set()
    for race_id in completed_race_ids:
        meta = race_meta.get(race_id, {})
        if course_code and meta.get("course_code") != course_code:
            continue
        if surface_group and meta.get("surface_group") != surface_group:
            continue
        selected.add(race_id)
    return selected


def build_scope_bias(
    race_date: str,
    as_of_post_time: str,
    scope: str,
    course_code: str,
    surface_group: str,
    selected_race_ids: set[str],
    results_by_race: dict[str, list[dict[str, str]]],
    starts_by_race: dict[str, list[dict[str, str]]],
) -> dict[str, str]:
    starters = []
    winners = []
    fastest_last3f_wins = 0
    winner_last3f_ranks: list[int] = []
    for race_id in selected_race_ids:
        starts = starts_by_race.get(race_id, [])
        by_horse_id = {row.get("horse_id", ""): row for row in starts}
        by_horse_no = {row.get("horse_no", ""): row for row in starts}
        field_size = len(starts)
        race_results = results_by_race.get(race_id, [])
        last3f_sorted = sorted(
            [
                (parse_float(result.get("runner_last3f_time")), result)
                for result in race_results
                if parse_float(result.get("runner_last3f_time")) is not None
            ],
            key=lambda item: item[0],
        )
        last3f_rank_by_key = {}
        for index, (_, result) in enumerate(last3f_sorted, start=1):
            last3f_rank_by_key[(result.get("horse_id", ""), result.get("horse_no", ""))] = index
        for start in starts:
            starters.append({**start, "gate_bucket": gate_bucket(start, field_size)})
        for result in race_results:
            if not is_winner(result):
                continue
            start = by_horse_id.get(result.get("horse_id", "")) or by_horse_no.get(result.get("horse_no", ""))
            if not start:
                continue
            winners.append({**result, **start, "gate_bucket": gate_bucket(start, field_size)})
            key = (result.get("horse_id", ""), result.get("horse_no", ""))
            last3f_rank = last3f_rank_by_key.get(key)
            if last3f_rank is not None:
                winner_last3f_ranks.append(last3f_rank)
                if last3f_rank == 1:
                    fastest_last3f_wins += 1

    completed_races = len(selected_race_ids)
    completed_starters = len(starters)
    observed_wins = len(winners)
    starter_bucket_counts = defaultdict(int)
    winner_bucket_counts = defaultdict(int)
    for row in starters:
        starter_bucket_counts[row.get("gate_bucket", "unknown")] += 1
    for row in winners:
        winner_bucket_counts[row.get("gate_bucket", "unknown")] += 1

    favored_gate_bucket = ""
    favored_gate_edge = 1.0
    for bucket, win_count in winner_bucket_counts.items():
        if bucket == "unknown" or completed_starters == 0 or observed_wins == 0:
            continue
        starter_share = starter_bucket_counts[bucket] / completed_starters
        winner_share = win_count / observed_wins
        if starter_share <= 0:
            continue
        edge = winner_share / starter_share
        if edge > favored_gate_edge:
            favored_gate_bucket = bucket
            favored_gate_edge = edge

    longshot_wins = 0
    favorite_wins = 0
    for row in winners:
        pop = (row.get("win_popularity") or row.get("popularity") or "").strip()
        if pop == "1":
            favorite_wins += 1
        if pop.isdigit() and int(pop) >= 6:
            longshot_wins += 1

    has_enough_sample = completed_races >= 2 and completed_starters >= 16 and observed_wins >= 2
    bias_factor = 1.0
    bias_status = "ok" if has_enough_sample else "sample_too_small"
    if has_enough_sample:
        if favorite_wins / observed_wins >= 0.5:
            bias_factor *= 0.98
        if longshot_wins / observed_wins >= 0.4:
            bias_factor *= 1.02
        if fastest_last3f_wins / observed_wins >= 0.4:
            bias_factor *= 1.01

    raw_edge = 1.0
    smoothed_edge = 1.0
    avg_winner_last3f_rank = sum(winner_last3f_ranks) / len(winner_last3f_ranks) if winner_last3f_ranks else 0.0
    favored_gate_edge = clamp(favored_gate_edge, 0.90, 1.10)
    bias_factor = clamp(bias_factor, 0.90, 1.10)
    summary = (
        f"completed={completed_races}; starters={completed_starters}; "
        f"fav_gate={favored_gate_bucket or 'none'}; fav_wins={favorite_wins}; "
        f"longshot_wins={longshot_wins}; fastest_last3f_wins={fastest_last3f_wins}"
    )
    return {
        "race_date": race_date,
        "as_of_post_time": as_of_post_time,
        "scope": scope,
        "course_code": course_code,
        "surface_group": surface_group,
        "completed_races": str(completed_races),
        "completed_starters": str(completed_starters),
        "observed_wins": str(observed_wins),
        "expected_wins": f"{float(observed_wins):.4f}",
        "raw_edge": f"{raw_edge:.4f}",
        "smoothed_edge": f"{smoothed_edge:.4f}",
        "bias_factor": f"{bias_factor:.4f}",
        "favored_gate_bucket": favored_gate_bucket,
        "favored_gate_edge": f"{favored_gate_edge:.4f}",
        "favorite_wins": str(favorite_wins),
        "longshot_wins": str(longshot_wins),
        "fastest_last3f_wins": str(fastest_last3f_wins),
        "avg_winner_last3f_rank": f"{avg_winner_last3f_rank:.2f}",
        "bias_status": bias_status,
        "bias_summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build same-day bias context from completed JRA races.")
    parser.add_argument("--race-date", required=True)
    parser.add_argument("--as-of-post-time", required=True, help="HHMM. Only races before this post time are used.")
    parser.add_argument("--races", default="data/jra_van_exports/races_minimal.csv")
    parser.add_argument("--starts", default="data/jra_van_exports/starts_minimal.csv")
    parser.add_argument("--results", default="data/model/win_training_minimal.csv")
    parser.add_argument("--output", default="outputs/live_predictions/day_bias_context.csv")
    args = parser.parse_args()

    races = [row for row in read_csv(Path(args.races)) if row.get("race_date") == args.race_date]
    starts = [row for row in read_csv(Path(args.starts)) if row.get("race_date") == args.race_date]
    results_path = Path(args.results)
    results = [row for row in read_csv(results_path) if row.get("race_id", "").startswith(args.race_date)] if results_path.exists() else []

    race_meta = {row["race_id"]: row for row in races}
    starts_by_race: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in starts:
        starts_by_race[row["race_id"]].append(row)
    results_by_race: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in results:
        if is_finished(row):
            results_by_race[row["race_id"]].append(row)

    as_of = hhmm(args.as_of_post_time)
    completed_race_ids = {
        race_id
        for race_id, rows in results_by_race.items()
        if race_id in race_meta and hhmm(race_meta[race_id].get("post_time", "")) < as_of
    }

    rows: list[dict[str, str]] = []
    rows.append(
        build_scope_bias(
            args.race_date,
            as_of,
            "all_day",
            "",
            "",
            completed_race_ids,
            results_by_race,
            starts_by_race,
        )
    )
    for course_code in sorted({row.get("course_code", "") for row in races if row.get("course_code")}):
        rows.append(
            build_scope_bias(
                args.race_date,
                as_of,
                "same_course",
                course_code,
                "",
                race_scope_rows(completed_race_ids, race_meta, course_code, ""),
                results_by_race,
                starts_by_race,
            )
        )
        for surface_group in sorted(
            {row.get("surface_group", "") for row in races if row.get("course_code") == course_code and row.get("surface_group")}
        ):
            rows.append(
                build_scope_bias(
                    args.race_date,
                    as_of,
                    "same_course_surface",
                    course_code,
                    surface_group,
                    race_scope_rows(completed_race_ids, race_meta, course_code, surface_group),
                    results_by_race,
                    starts_by_race,
                )
            )

    fields = [
        "race_date",
        "as_of_post_time",
        "scope",
        "course_code",
        "surface_group",
        "completed_races",
        "completed_starters",
        "observed_wins",
        "expected_wins",
        "raw_edge",
        "smoothed_edge",
        "bias_factor",
        "favored_gate_bucket",
        "favored_gate_edge",
        "favorite_wins",
        "longshot_wins",
        "fastest_last3f_wins",
        "avg_winner_last3f_rank",
        "bias_status",
        "bias_summary",
    ]
    write_csv(Path(args.output), rows, fields)
    print(f"rows={len(rows)} completed_races={len(completed_race_ids)} output={args.output}")


if __name__ == "__main__":
    main()
