import argparse
import csv
from collections import defaultdict
from pathlib import Path

from predict_historical_win_ev import clamp, odds_bucket
from rolling_backtest_race_features import Agg, add_market_probabilities, distance_bucket, field_bucket, race_class


def signed_weight_diff(row: dict[str, str]) -> int | None:
    raw_diff = (row.get("weight_diff") or "").strip()
    if not raw_diff or not raw_diff.isdigit():
        return None
    diff = int(raw_diff)
    if (row.get("weight_diff_sign") or "").strip() == "-":
        return -diff
    return diff


def weight_diff_bucket(row: dict[str, str]) -> str:
    diff = signed_weight_diff(row)
    if diff is None:
        return "unknown"
    if diff <= -12:
        return "<=-12"
    if diff <= -7:
        return "-11..-7"
    if diff <= -3:
        return "-6..-3"
    if diff <= 3:
        return "-2..+3"
    if diff <= 7:
        return "+4..+7"
    if diff <= 11:
        return "+8..+11"
    return ">=+12"


def horse_weight_bucket(row: dict[str, str]) -> str:
    raw_weight = (row.get("horse_weight") or "").strip()
    if not raw_weight or not raw_weight.isdigit():
        return "unknown"
    weight = int(raw_weight)
    if weight < 420:
        return "<420"
    if weight < 460:
        return "420-459"
    if weight < 500:
        return "460-499"
    if weight < 540:
        return "500-539"
    return "540+"


def gate_bucket(row: dict[str, str], field_size: int) -> str:
    raw_gate = (row.get("gate") or "").strip()
    if not raw_gate or not raw_gate.isdigit() or field_size <= 0:
        return "unknown"
    gate = int(raw_gate)
    if field_size <= 8:
        return "inner" if gate <= 2 else "middle" if gate <= 5 else "outer"
    if field_size <= 14:
        return "inner" if gate <= 3 else "middle" if gate <= 6 else "outer"
    if gate <= 3:
        return "inner"
    if gate <= 6:
        return "middle"
    if gate <= 8:
        return "outer"
    return "far_outer"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def group_by_race(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    by_race: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_race[row["race_id"]].append(row)
    return by_race


def build_aggs(
    training_rows: list[dict[str, str]],
    race_meta: dict[str, dict[str, str]],
    pedigree: dict[str, dict[str, str]],
    before_date: str,
):
    pop_bucket_aggs: dict[tuple[str, str], Agg] = defaultdict(Agg)
    cond_pop_aggs: dict[tuple[str, str, str, str], Agg] = defaultdict(Agg)
    course_cond_pop_aggs: dict[tuple[str, str, str, str, str], Agg] = defaultdict(Agg)
    class_pop_aggs: dict[tuple[str, str, str], Agg] = defaultdict(Agg)
    field_pop_aggs: dict[tuple[str, str, str], Agg] = defaultdict(Agg)
    sire_cond_pop_aggs: dict[tuple[str, str, str, str], Agg] = defaultdict(Agg)
    damsire_cond_pop_aggs: dict[tuple[str, str, str, str], Agg] = defaultdict(Agg)
    jockey_aggs: dict[str, Agg] = defaultdict(Agg)
    trainer_aggs: dict[str, Agg] = defaultdict(Agg)
    weight_diff_aggs: dict[tuple[str, str], Agg] = defaultdict(Agg)
    weight_diff_cond_aggs: dict[tuple[str, str, str, str], Agg] = defaultdict(Agg)
    horse_weight_cond_aggs: dict[tuple[str, str, str], Agg] = defaultdict(Agg)
    gate_cond_aggs: dict[tuple[str, str, str, str], Agg] = defaultdict(Agg)
    jockey_course_cond_aggs: dict[tuple[str, str, str, str], Agg] = defaultdict(Agg)
    jockey_surface_distance_pop_aggs: dict[tuple[str, str, str, str], Agg] = defaultdict(Agg)
    trainer_course_cond_aggs: dict[tuple[str, str, str], Agg] = defaultdict(Agg)

    for race_id, race_rows in sorted(group_by_race(training_rows).items()):
        if race_rows[0]["race_date"] >= before_date:
            continue
        meta = race_meta.get(race_id)
        if not meta:
            continue
        for row in race_rows:
            row.update(meta)
            ped = pedigree.get(row["horse_id"], {})
            row["sire_id"] = ped.get("sire_id", "")
            row["sire_name"] = ped.get("sire_name", "")
            row["dam_sire_id"] = ped.get("dam_sire_id", "")
            row["dam_sire_name"] = ped.get("dam_sire_name", "")
            row["field_bucket"] = field_bucket(len(race_rows))
            row["distance_bucket"] = distance_bucket(row.get("distance", ""))
            row["race_class"] = race_class(row)
            row["weight_diff_bucket"] = weight_diff_bucket(row)
            row["horse_weight_bucket"] = horse_weight_bucket(row)
            row["gate_bucket"] = gate_bucket(row, len(race_rows))
        ok, _ = add_market_probabilities(race_rows)
        if not ok:
            continue
        for row in race_rows:
            bucket = odds_bucket(float(row["win_odds"]))
            pop_bucket_aggs[(row["win_popularity"], bucket)].update(row)
            cond_pop_aggs[(row["surface_group"], row["distance_bucket"], row["win_popularity"], bucket)].update(row)
            course_cond_pop_aggs[
                (row["course_code"], row["surface_group"], row["distance_bucket"], row["win_popularity"], bucket)
            ].update(row)
            class_pop_aggs[(row["race_class"], row["win_popularity"], bucket)].update(row)
            field_pop_aggs[(row["field_bucket"], row["win_popularity"], bucket)].update(row)
            sire_cond_pop_aggs[(row.get("sire_id", ""), row["surface_group"], row["distance_bucket"], bucket)].update(row)
            damsire_cond_pop_aggs[(row.get("dam_sire_id", ""), row["surface_group"], row["distance_bucket"], bucket)].update(row)
            jockey_aggs[row["jockey_code"]].update(row)
            trainer_aggs[row["trainer_code"]].update(row)
            weight_diff_aggs[(row["weight_diff_bucket"], bucket)].update(row)
            weight_diff_cond_aggs[(row["surface_group"], row["distance_bucket"], row["weight_diff_bucket"], bucket)].update(row)
            horse_weight_cond_aggs[(row["surface_group"], row["distance_bucket"], row["horse_weight_bucket"])].update(row)
            gate_cond_aggs[(row["course_code"], row["distance_bucket"], row["field_bucket"], row["gate_bucket"])].update(row)
            jockey_course_cond_aggs[
                (row["jockey_code"], row["course_code"], row["surface_group"], row["distance_bucket"])
            ].update(row)
            jockey_surface_distance_pop_aggs[
                (row["jockey_code"], row["surface_group"], row["distance_bucket"], row["win_popularity"])
            ].update(row)
            trainer_course_cond_aggs[(row["trainer_code"], row["course_code"], row["surface_group"])].update(row)

    return {
        "pop_bucket": pop_bucket_aggs,
        "cond_pop": cond_pop_aggs,
        "course_cond_pop": course_cond_pop_aggs,
        "class_pop": class_pop_aggs,
        "field_pop": field_pop_aggs,
        "sire_cond_pop": sire_cond_pop_aggs,
        "damsire_cond_pop": damsire_cond_pop_aggs,
        "jockey": jockey_aggs,
        "trainer": trainer_aggs,
        "weight_diff": weight_diff_aggs,
        "weight_diff_cond": weight_diff_cond_aggs,
        "horse_weight_cond": horse_weight_cond_aggs,
        "gate_cond": gate_cond_aggs,
        "jockey_course_cond": jockey_course_cond_aggs,
        "jockey_surface_distance_pop": jockey_surface_distance_pop_aggs,
        "trainer_course_cond": trainer_course_cond_aggs,
    }


def latest_win_odds(odds_rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    rows = [row for row in odds_rows if row.get("bet_type") == "win" and row.get("horse_no")]
    rows.sort(key=lambda row: row.get("observed_at", ""))
    return {(row["race_id"], row["horse_no"]): row for row in rows}


def parse_float(raw: str | None, default: float = 1.0) -> float:
    try:
        if raw is None or raw == "":
            return default
        return float(raw)
    except ValueError:
        return default


def read_same_day_bias(path: Path | None) -> dict[tuple[str, str, str], dict[str, str]]:
    if not path or not path.exists():
        return {}
    rows = read_csv(path)
    lookup: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (row.get("race_date", ""), row.get("course_code", ""), row.get("surface_group", ""))
        lookup[key] = row
    return lookup


def same_day_bias_for_race(
    same_day_bias: dict[tuple[str, str, str], dict[str, str]],
    race: dict[str, str],
) -> dict[str, str]:
    race_date = race.get("race_date", "")
    course_code = race.get("course_code", "")
    surface_group = race.get("surface_group", "")
    candidates = [
        same_day_bias.get((race_date, course_code, surface_group)),
        same_day_bias.get((race_date, course_code, "")),
        same_day_bias.get((race_date, "", "")),
    ]
    for row in candidates:
        if row and row.get("bias_status") == "ok":
            return row
    for row in candidates:
        if row:
            return row
    return {}


def score_race(
    starts: list[dict[str, str]],
    race: dict[str, str],
    odds_lookup: dict[tuple[str, str], dict[str, str]],
    aggs,
    pedigree: dict[str, dict[str, str]],
    same_day_bias: dict[tuple[str, str, str], dict[str, str]],
    min_ev: float,
    min_condition_count: int,
    min_condition_edge: float,
) -> list[dict[str, str]]:
    scored_rows = []
    race_rows = []
    for start in starts:
        odds = odds_lookup.get((start["race_id"], start["horse_no"]))
        if not odds:
            scored_rows.append({**start, **race, "decision": "PASS", "reason": "missing_latest_win_odds"})
            continue
        race_rows.append(
            {
                **start,
                **race,
                **{
                    "sire_id": pedigree.get(start["horse_id"], {}).get("sire_id", ""),
                    "sire_name": pedigree.get(start["horse_id"], {}).get("sire_name", ""),
                    "dam_sire_id": pedigree.get(start["horse_id"], {}).get("dam_sire_id", ""),
                    "dam_sire_name": pedigree.get(start["horse_id"], {}).get("dam_sire_name", ""),
                },
                "win_odds": odds["odds"],
                "win_popularity": odds.get("popularity", ""),
                "observed_at": odds.get("observed_at", ""),
            }
        )

    ok, reason = add_market_probabilities(race_rows)
    if not ok:
        return [
            {
                **row,
                "decision": "PASS",
                "reason": reason,
                "ev_per_yen": "",
                "probability": "",
                "condition_count": "",
                "condition_edge": "",
            }
            for row in race_rows
        ] + scored_rows

    field = field_bucket(len(race_rows))
    race_bias = same_day_bias_for_race(same_day_bias, race)
    base_day_bias_factor = parse_float(race_bias.get("bias_factor"), 1.0)
    favored_gate_bucket = race_bias.get("favored_gate_bucket", "")
    favored_gate_edge = parse_float(race_bias.get("favored_gate_edge"), 1.0)
    for row in race_rows:
        odds = float(row["win_odds"])
        bucket = odds_bucket(odds)
        row["field_bucket"] = field
        row["distance_bucket"] = distance_bucket(row.get("distance", ""))
        row["race_class"] = race_class(row)
        row["weight_diff_bucket"] = weight_diff_bucket(row)
        row["horse_weight_bucket"] = horse_weight_bucket(row)
        row["gate_bucket"] = gate_bucket(row, len(race_rows))

        pop_bucket = (row["win_popularity"], bucket)
        cond_pop = (row["surface_group"], row["distance_bucket"], row["win_popularity"], bucket)
        course_cond_pop = (row["course_code"], row["surface_group"], row["distance_bucket"], row["win_popularity"], bucket)
        class_pop = (row["race_class"], row["win_popularity"], bucket)
        field_pop = (row["field_bucket"], row["win_popularity"], bucket)
        sire_cond_pop = (row.get("sire_id", ""), row["surface_group"], row["distance_bucket"], bucket)
        damsire_cond_pop = (row.get("dam_sire_id", ""), row["surface_group"], row["distance_bucket"], bucket)
        weight_diff_key = (row["weight_diff_bucket"], bucket)
        weight_diff_cond_key = (row["surface_group"], row["distance_bucket"], row["weight_diff_bucket"], bucket)
        horse_weight_cond_key = (row["surface_group"], row["distance_bucket"], row["horse_weight_bucket"])
        gate_cond_key = (row["course_code"], row["distance_bucket"], row["field_bucket"], row["gate_bucket"])
        jockey_course_cond_key = (
            row.get("jockey_code", ""),
            row["course_code"],
            row["surface_group"],
            row["distance_bucket"],
        )
        jockey_surface_distance_pop_key = (
            row.get("jockey_code", ""),
            row["surface_group"],
            row["distance_bucket"],
            row["win_popularity"],
        )
        trainer_course_cond_key = (row.get("trainer_code", ""), row["course_code"], row["surface_group"])

        cond_agg = aggs["cond_pop"][cond_pop]
        combo_edge = aggs["pop_bucket"][pop_bucket].edge(50.0)
        cond_edge = cond_agg.edge(80.0)
        course_edge = aggs["course_cond_pop"][course_cond_pop].edge(120.0)
        class_edge = aggs["class_pop"][class_pop].edge(80.0)
        field_edge = aggs["field_pop"][field_pop].edge(80.0)
        sire_edge = aggs["sire_cond_pop"][sire_cond_pop].edge(120.0)
        damsire_edge = aggs["damsire_cond_pop"][damsire_cond_pop].edge(120.0)
        jockey_edge = aggs["jockey"][row.get("jockey_code", "")].edge(120.0)
        trainer_edge = aggs["trainer"][row.get("trainer_code", "")].edge(120.0)
        weight_diff_edge = aggs["weight_diff"][weight_diff_key].edge(100.0)
        weight_diff_cond_edge = aggs["weight_diff_cond"][weight_diff_cond_key].edge(120.0)
        horse_weight_edge = aggs["horse_weight_cond"][horse_weight_cond_key].edge(120.0)
        gate_edge = aggs["gate_cond"][gate_cond_key].edge(120.0)
        jockey_course_edge = aggs["jockey_course_cond"][jockey_course_cond_key].edge(120.0)
        jockey_surface_distance_pop_edge = aggs["jockey_surface_distance_pop"][jockey_surface_distance_pop_key].edge(120.0)
        trainer_course_edge = aggs["trainer_course_cond"][trainer_course_cond_key].edge(120.0)
        blended_edge = clamp(
            0.12 * combo_edge
            + 0.18 * cond_edge
            + 0.10 * course_edge
            + 0.08 * class_edge
            + 0.05 * field_edge
            + 0.07 * sire_edge
            + 0.05 * damsire_edge
            + 0.03 * jockey_edge
            + 0.03 * trainer_edge
            + 0.05 * weight_diff_edge
            + 0.06 * weight_diff_cond_edge
            + 0.03 * horse_weight_edge
            + 0.04 * gate_edge
            + 0.05 * jockey_course_edge
            + 0.04 * jockey_surface_distance_pop_edge
            + 0.04 * trainer_course_edge,
            0.75,
            1.30,
        )
        probability_before_day_bias = float(row["market_probability"]) * blended_edge
        day_bias_factor = base_day_bias_factor
        if favored_gate_bucket and row["gate_bucket"] == favored_gate_bucket:
            day_bias_factor *= favored_gate_edge
        day_bias_factor = clamp(day_bias_factor, 0.90, 1.10)
        probability = probability_before_day_bias * day_bias_factor
        ev_before_day_bias = probability_before_day_bias * odds - 1
        ev = probability * odds - 1
        can_buy = (
            ev >= min_ev
            and cond_agg.count >= min_condition_count
            and cond_edge >= min_condition_edge
            and 2.0 <= odds <= 50.0
        )
        scored_rows.append(
            {
                **row,
                "decision": "BUY" if can_buy else "PASS",
                "reason": "meets_quality_and_ev_gate" if can_buy else "ev_or_quality_gate_not_met",
                "probability": f"{probability:.4f}",
                "ev_per_yen": f"{ev:.4f}",
                "probability_before_day_bias": f"{probability_before_day_bias:.4f}",
                "ev_before_day_bias": f"{ev_before_day_bias:.4f}",
                "day_bias_scope": race_bias.get("scope", "none"),
                "day_bias_status": race_bias.get("bias_status", "unavailable"),
                "day_bias_completed_races": race_bias.get("completed_races", "0"),
                "day_bias_completed_starters": race_bias.get("completed_starters", "0"),
                "day_bias_expected_wins": race_bias.get("expected_wins", ""),
                "day_bias_observed_wins": race_bias.get("observed_wins", ""),
                "day_bias_raw_edge": race_bias.get("raw_edge", ""),
                "day_bias_favorite_wins": race_bias.get("favorite_wins", ""),
                "day_bias_longshot_wins": race_bias.get("longshot_wins", ""),
                "day_bias_fastest_last3f_wins": race_bias.get("fastest_last3f_wins", ""),
                "day_bias_avg_winner_last3f_rank": race_bias.get("avg_winner_last3f_rank", ""),
                "day_bias_factor": f"{day_bias_factor:.4f}",
                "day_bias_summary": race_bias.get("bias_summary", ""),
                "blended_edge": f"{blended_edge:.4f}",
                "condition_count": str(cond_agg.count),
                "condition_edge": f"{cond_edge:.4f}",
                "sire_condition_count": str(aggs["sire_cond_pop"][sire_cond_pop].count),
                "sire_condition_edge": f"{sire_edge:.4f}",
                "dam_sire_condition_count": str(aggs["damsire_cond_pop"][damsire_cond_pop].count),
                "dam_sire_condition_edge": f"{damsire_edge:.4f}",
                "weight_diff_bucket": row["weight_diff_bucket"],
                "weight_diff_count": str(aggs["weight_diff"][weight_diff_key].count),
                "weight_diff_edge": f"{weight_diff_edge:.4f}",
                "weight_diff_condition_count": str(aggs["weight_diff_cond"][weight_diff_cond_key].count),
                "weight_diff_condition_edge": f"{weight_diff_cond_edge:.4f}",
                "horse_weight_bucket": row["horse_weight_bucket"],
                "horse_weight_condition_count": str(aggs["horse_weight_cond"][horse_weight_cond_key].count),
                "horse_weight_condition_edge": f"{horse_weight_edge:.4f}",
                "gate_bucket": row["gate_bucket"],
                "gate_condition_count": str(aggs["gate_cond"][gate_cond_key].count),
                "gate_condition_edge": f"{gate_edge:.4f}",
                "jockey_condition_count": str(aggs["jockey"][row.get("jockey_code", "")].count),
                "jockey_condition_edge": f"{jockey_edge:.4f}",
                "jockey_course_condition_count": str(aggs["jockey_course_cond"][jockey_course_cond_key].count),
                "jockey_course_condition_edge": f"{jockey_course_edge:.4f}",
                "jockey_surface_distance_pop_count": str(aggs["jockey_surface_distance_pop"][jockey_surface_distance_pop_key].count),
                "jockey_surface_distance_pop_edge": f"{jockey_surface_distance_pop_edge:.4f}",
                "trainer_condition_count": str(aggs["trainer"][row.get("trainer_code", "")].count),
                "trainer_condition_edge": f"{trainer_edge:.4f}",
                "trainer_course_condition_count": str(aggs["trainer_course_cond"][trainer_course_cond_key].count),
                "trainer_course_condition_edge": f"{trainer_course_edge:.4f}",
            }
        )
    return scored_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Score latest win odds for live BUY/PASS decisions.")
    parser.add_argument("--training", default="data/model/target_win_training_2004_2025.csv")
    parser.add_argument("--race-history", default="data/model/target_races_2004_2026.csv")
    parser.add_argument("--pedigree", default="data/model/target_pedigree_1986_2026.csv")
    parser.add_argument("--races", default="data/jra_van_exports/races_minimal.csv")
    parser.add_argument("--starts", default="data/jra_van_exports/starts_minimal.csv")
    parser.add_argument("--odds", default="data/jra_van_exports/odds_win_place_minimal.csv")
    parser.add_argument("--same-day-bias", default="")
    parser.add_argument("--race-date", required=True)
    parser.add_argument("--min-ev", type=float, default=0.20)
    parser.add_argument("--min-condition-count", type=int, default=500)
    parser.add_argument("--min-condition-edge", type=float, default=1.02)
    parser.add_argument("--output", default="outputs/live_predictions/live_win_ev.csv")
    args = parser.parse_args()

    race_history = {row["race_id"]: row for row in read_csv(Path(args.race_history))}
    pedigree = {row["horse_id"]: row for row in read_csv(Path(args.pedigree))} if args.pedigree else {}
    aggs = build_aggs(read_csv(Path(args.training)), race_history, pedigree, args.race_date)

    race_rows = {row["race_id"]: row for row in read_csv(Path(args.races)) if row["race_date"] == args.race_date}
    starts_by_race = group_by_race([row for row in read_csv(Path(args.starts)) if row["race_date"] == args.race_date])
    odds_lookup = latest_win_odds(read_csv(Path(args.odds)))
    same_day_bias = read_same_day_bias(Path(args.same_day_bias)) if args.same_day_bias else {}

    output_rows = []
    for race_id, starts in sorted(starts_by_race.items()):
        race = race_rows.get(race_id)
        if not race:
            continue
        output_rows.extend(
            score_race(
                starts,
                race,
                odds_lookup,
                aggs,
                pedigree,
                same_day_bias,
                args.min_ev,
                args.min_condition_count,
                args.min_condition_edge,
            )
        )

    output_rows.sort(key=lambda row: (row["race_id"], row["decision"] != "BUY", -float(row.get("ev_per_yen") or "-999")))
    fields = [
        "decision",
        "reason",
        "race_id",
        "race_date",
        "race_no",
        "race_name",
        "post_time",
        "horse_no",
        "horse_name",
        "jockey_name",
        "trainer_name",
        "win_odds",
        "win_popularity",
        "probability",
        "ev_per_yen",
        "probability_before_day_bias",
        "ev_before_day_bias",
        "day_bias_scope",
        "day_bias_status",
        "day_bias_completed_races",
        "day_bias_completed_starters",
        "day_bias_expected_wins",
        "day_bias_observed_wins",
        "day_bias_raw_edge",
        "day_bias_favorite_wins",
        "day_bias_longshot_wins",
        "day_bias_fastest_last3f_wins",
        "day_bias_avg_winner_last3f_rank",
        "day_bias_factor",
        "day_bias_summary",
        "blended_edge",
        "condition_count",
        "condition_edge",
        "sire_name",
        "sire_condition_count",
        "sire_condition_edge",
        "dam_sire_name",
        "dam_sire_condition_count",
        "dam_sire_condition_edge",
        "weight_diff_bucket",
        "weight_diff_count",
        "weight_diff_edge",
        "weight_diff_condition_count",
        "weight_diff_condition_edge",
        "horse_weight_bucket",
        "horse_weight_condition_count",
        "horse_weight_condition_edge",
        "gate_bucket",
        "gate_condition_count",
        "gate_condition_edge",
        "jockey_condition_count",
        "jockey_condition_edge",
        "jockey_course_condition_count",
        "jockey_course_condition_edge",
        "jockey_surface_distance_pop_count",
        "jockey_surface_distance_pop_edge",
        "trainer_condition_count",
        "trainer_condition_edge",
        "trainer_course_condition_count",
        "trainer_course_condition_edge",
        "surface_group",
        "distance",
        "distance_bucket",
        "track_code",
        "weather_code",
        "going_code",
        "turf_going_code",
        "dirt_going_code",
        "lap_times_raw",
        "race_corner_passage_raw",
        "race_time",
        "runner_last3f_time",
        "margin_code",
        "result_detail_raw",
        "race_class",
        "field_bucket",
        "observed_at",
    ]
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(output_rows)

    buys = [row for row in output_rows if row["decision"] == "BUY"]
    print(f"rows={len(output_rows)} buys={len(buys)} output={args.output}")


if __name__ == "__main__":
    main()
