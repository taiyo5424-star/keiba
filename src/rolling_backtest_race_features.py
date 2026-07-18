import argparse
import csv
from collections import defaultdict
from pathlib import Path

from predict_historical_win_ev import clamp, odds_bucket


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def group_by_race(rows: list[dict[str, str]]) -> list[tuple[str, list[dict[str, str]]]]:
    by_race: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_race[row["race_id"]].append(row)
    return sorted(by_race.items(), key=lambda item: item[0])


class Agg:
    def __init__(self) -> None:
        self.count = 0
        self.wins = 0
        self.expected = 0.0

    def update(self, row: dict[str, str]) -> None:
        self.count += 1
        self.wins += int(row["label_win"])
        self.expected += float(row["market_probability"])

    def edge(self, prior: float) -> float:
        if self.count == 0:
            return 1.0
        return (self.wins + prior) / (self.expected + prior)


def distance_bucket(distance: str) -> str:
    try:
        d = int(distance)
    except ValueError:
        return "unknown"
    if d < 1200:
        return "1000-1199"
    if d < 1400:
        return "1200-1399"
    if d < 1600:
        return "1400-1599"
    if d < 1800:
        return "1600-1799"
    if d < 2000:
        return "1800-1999"
    if d < 2400:
        return "2000-2399"
    return "2400+"


def field_bucket(size: int) -> str:
    if size <= 8:
        return "05-08"
    if size <= 11:
        return "09-11"
    if size <= 14:
        return "12-14"
    return "15+"


def race_class(row: dict[str, str]) -> str:
    grade = row.get("grade_code", "")
    if grade:
        return f"G{grade}"
    youngest = row.get("condition_youngest", "")
    race_type = row.get("race_type_code", "")
    return f"{race_type}_{youngest}"


def add_market_probabilities(race_rows: list[dict[str, str]]) -> tuple[bool, str]:
    odds_values = []
    for row in race_rows:
        try:
            odds = float(row["win_odds"])
        except ValueError:
            return False, "bad_odds"
        if odds < 1.1:
            return False, "odds_below_1_1"
        odds_values.append(odds)
    if len(odds_values) < 5:
        return False, "small_field"
    implied_total = sum(1 / odds for odds in odds_values)
    if implied_total < 1.02 or implied_total > 1.55:
        return False, "abnormal_implied_total"
    for row, odds in zip(race_rows, odds_values):
        row["market_probability"] = (1 / odds) / implied_total
    return True, "ok"


def enrich_rows(race_rows: list[dict[str, str]], race_meta: dict[str, str], pedigree: dict[str, dict[str, str]] | None = None) -> None:
    size = len(race_rows)
    for row in race_rows:
        row.update(race_meta)
        if pedigree is not None:
            ped = pedigree.get(row["horse_id"], {})
            row["sire_id"] = ped.get("sire_id", "")
            row["sire_name"] = ped.get("sire_name", "")
            row["dam_sire_id"] = ped.get("dam_sire_id", "")
            row["dam_sire_name"] = ped.get("dam_sire_name", "")
        row["field_bucket"] = field_bucket(size)
        row["distance_bucket"] = distance_bucket(row.get("distance", ""))
        row["race_class"] = race_class(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rolling backtest with race features and data-quality gates.")
    parser.add_argument("--input", default="data/model/target_win_training_2004_2025.csv")
    parser.add_argument("--races", default="data/model/target_races_2004_2026.csv")
    parser.add_argument("--pedigree", default="")
    parser.add_argument("--start-date", default="20050101")
    parser.add_argument("--min-ev", type=float, default=0.20)
    parser.add_argument("--min-condition-count", type=int, default=500)
    parser.add_argument("--min-condition-edge", type=float, default=1.02)
    parser.add_argument("--stake", type=int, default=100)
    parser.add_argument("--output", default="outputs/backtests/rolling_race_features_win_bets.csv")
    parser.add_argument("--summary", default="outputs/backtests/rolling_race_features_win_summary.csv")
    parser.add_argument("--top-candidates", default="outputs/backtests/rolling_race_features_top_candidates.csv")
    parser.add_argument("--top-n", type=int, default=500)
    args = parser.parse_args()

    race_meta = {row["race_id"]: row for row in read_csv(Path(args.races))}
    pedigree = {row["horse_id"]: row for row in read_csv(Path(args.pedigree))} if args.pedigree else None
    races = group_by_race(read_csv(Path(args.input)))

    pop_bucket_aggs: dict[tuple[str, str], Agg] = defaultdict(Agg)
    cond_pop_aggs: dict[tuple[str, str, str, str], Agg] = defaultdict(Agg)
    course_cond_pop_aggs: dict[tuple[str, str, str, str, str], Agg] = defaultdict(Agg)
    class_pop_aggs: dict[tuple[str, str, str], Agg] = defaultdict(Agg)
    field_pop_aggs: dict[tuple[str, str, str], Agg] = defaultdict(Agg)
    sire_cond_pop_aggs: dict[tuple[str, str, str, str], Agg] = defaultdict(Agg)
    damsire_cond_pop_aggs: dict[tuple[str, str, str, str], Agg] = defaultdict(Agg)
    jockey_aggs: dict[str, Agg] = defaultdict(Agg)
    trainer_aggs: dict[str, Agg] = defaultdict(Agg)

    bets = []
    candidates = []
    skipped: dict[str, int] = defaultdict(int)
    summaries: dict[str, dict[str, float]] = defaultdict(
        lambda: {"races": 0, "valid_races": 0, "bets": 0, "stake": 0, "return": 0, "wins": 0}
    )

    for race_id, race_rows in races:
        meta = race_meta.get(race_id)
        if not meta:
            skipped["missing_ra"] += 1
            continue
        enrich_rows(race_rows, meta, pedigree)
        ok, reason = add_market_probabilities(race_rows)
        race_date = race_rows[0]["race_date"]
        year = race_date[:4]
        if race_date >= args.start_date:
            summaries[year]["races"] += 1
        if not ok:
            skipped[reason] += 1
            continue
        if race_date >= args.start_date:
            summaries[year]["valid_races"] += 1
            for row in race_rows:
                odds = float(row["win_odds"])
                bucket = odds_bucket(odds)
                pop_bucket = (row["win_popularity"], bucket)
                cond_pop = (row["surface_group"], row["distance_bucket"], row["win_popularity"], bucket)
                course_cond_pop = (
                    row["course_code"],
                    row["surface_group"],
                    row["distance_bucket"],
                    row["win_popularity"],
                    bucket,
                )
                class_pop = (row["race_class"], row["win_popularity"], bucket)
                field_pop = (row["field_bucket"], row["win_popularity"], bucket)
                sire_cond_pop = (row.get("sire_id", ""), row["surface_group"], row["distance_bucket"], bucket)
                damsire_cond_pop = (row.get("dam_sire_id", ""), row["surface_group"], row["distance_bucket"], bucket)

                combo_edge = pop_bucket_aggs[pop_bucket].edge(50.0)
                cond_agg = cond_pop_aggs[cond_pop]
                cond_edge = cond_agg.edge(80.0)
                course_edge = course_cond_pop_aggs[course_cond_pop].edge(120.0)
                class_edge = class_pop_aggs[class_pop].edge(80.0)
                field_edge = field_pop_aggs[field_pop].edge(80.0)
                sire_edge = sire_cond_pop_aggs[sire_cond_pop].edge(120.0)
                damsire_edge = damsire_cond_pop_aggs[damsire_cond_pop].edge(120.0)
                jockey_edge = jockey_aggs[row["jockey_code"]].edge(120.0)
                trainer_edge = trainer_aggs[row["trainer_code"]].edge(120.0)

                blended_edge = clamp(
                    0.16 * combo_edge
                    + 0.24 * cond_edge
                    + 0.12 * course_edge
                    + 0.12 * class_edge
                    + 0.08 * field_edge
                    + 0.10 * sire_edge
                    + 0.08 * damsire_edge
                    + 0.05 * jockey_edge
                    + 0.05 * trainer_edge,
                    0.75,
                    1.30,
                )
                probability = float(row["market_probability"]) * blended_edge
                ev = probability * odds - 1

                is_buy = (
                    ev >= args.min_ev
                    and cond_agg.count >= args.min_condition_count
                    and cond_edge >= args.min_condition_edge
                    and 2.0 <= odds <= 50.0
                )
                if is_buy:
                    payout = args.stake * odds if row["label_win"] == "1" else 0.0
                    profit = payout - args.stake
                    summaries[year]["bets"] += 1
                    summaries[year]["stake"] += args.stake
                    summaries[year]["return"] += payout
                    summaries[year]["wins"] += int(row["label_win"])
                    bets.append(
                        {
                            "race_id": race_id,
                            "race_date": race_date,
                            "horse_no": row["horse_no"],
                            "selection": row["horse_name"],
                            "win_odds": f"{odds:.1f}",
                            "popularity": row["win_popularity"],
                            "probability": f"{probability:.4f}",
                            "ev_per_yen": f"{ev:.4f}",
                            "actual_win": row["label_win"],
                            "stake": str(args.stake),
                            "return": f"{payout:.0f}",
                            "profit": f"{profit:.0f}",
                            "blended_edge": f"{blended_edge:.4f}",
                            "condition_count": str(cond_agg.count),
                            "condition_edge": f"{cond_edge:.4f}",
                            "course_condition_count": str(course_cond_pop_aggs[course_cond_pop].count),
                            "course_condition_edge": f"{course_edge:.4f}",
                            "sire_name": row.get("sire_name", ""),
                            "sire_condition_count": str(sire_cond_pop_aggs[sire_cond_pop].count),
                            "sire_condition_edge": f"{sire_edge:.4f}",
                            "dam_sire_name": row.get("dam_sire_name", ""),
                            "dam_sire_condition_count": str(damsire_cond_pop_aggs[damsire_cond_pop].count),
                            "dam_sire_condition_edge": f"{damsire_edge:.4f}",
                            "surface_group": row["surface_group"],
                            "distance_bucket": row["distance_bucket"],
                            "race_class": row["race_class"],
                            "field_bucket": row["field_bucket"],
                        }
                    )
                if cond_agg.count >= 100 and 2.0 <= odds <= 50.0:
                    candidates.append(
                        {
                            "race_id": race_id,
                            "race_date": race_date,
                            "horse_no": row["horse_no"],
                            "selection": row["horse_name"],
                            "win_odds": f"{odds:.1f}",
                            "popularity": row["win_popularity"],
                            "probability": f"{probability:.4f}",
                            "ev_per_yen": f"{ev:.4f}",
                            "actual_win": row["label_win"],
                            "blended_edge": f"{blended_edge:.4f}",
                            "condition_count": str(cond_agg.count),
                            "condition_edge": f"{cond_edge:.4f}",
                            "course_condition_count": str(course_cond_pop_aggs[course_cond_pop].count),
                            "course_condition_edge": f"{course_edge:.4f}",
                            "sire_name": row.get("sire_name", ""),
                            "sire_condition_count": str(sire_cond_pop_aggs[sire_cond_pop].count),
                            "sire_condition_edge": f"{sire_edge:.4f}",
                            "dam_sire_name": row.get("dam_sire_name", ""),
                            "dam_sire_condition_count": str(damsire_cond_pop_aggs[damsire_cond_pop].count),
                            "dam_sire_condition_edge": f"{damsire_edge:.4f}",
                            "surface_group": row["surface_group"],
                            "distance_bucket": row["distance_bucket"],
                            "race_class": row["race_class"],
                            "field_bucket": row["field_bucket"],
                        }
                    )

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

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    bet_fields = [
        "race_id",
        "race_date",
        "horse_no",
        "selection",
        "win_odds",
        "popularity",
        "probability",
        "ev_per_yen",
        "actual_win",
        "stake",
        "return",
        "profit",
        "blended_edge",
        "condition_count",
        "condition_edge",
        "course_condition_count",
        "course_condition_edge",
        "sire_name",
        "sire_condition_count",
        "sire_condition_edge",
        "dam_sire_name",
        "dam_sire_condition_count",
        "dam_sire_condition_edge",
        "surface_group",
        "distance_bucket",
        "race_class",
        "field_bucket",
    ]
    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=bet_fields)
        writer.writeheader()
        writer.writerows(bets)

    summary_rows = []
    total = {"races": 0, "valid_races": 0, "bets": 0, "stake": 0, "return": 0, "wins": 0}
    for year in sorted(summaries):
        s = summaries[year]
        for key in total:
            total[key] += s[key]
        roi = s["return"] / s["stake"] - 1 if s["stake"] else 0.0
        hit = s["wins"] / s["bets"] if s["bets"] else 0.0
        summary_rows.append({**{"year": year}, **{k: f"{v:.0f}" for k, v in s.items()}, "hit_rate": f"{hit:.4f}", "roi": f"{roi:.4f}"})
    total_roi = total["return"] / total["stake"] - 1 if total["stake"] else 0.0
    total_hit = total["wins"] / total["bets"] if total["bets"] else 0.0
    summary_rows.append({**{"year": "TOTAL"}, **{k: f"{v:.0f}" for k, v in total.items()}, "hit_rate": f"{total_hit:.4f}", "roi": f"{total_roi:.4f}"})

    with Path(args.summary).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "races", "valid_races", "bets", "stake", "return", "wins", "hit_rate", "roi"])
        writer.writeheader()
        writer.writerows(summary_rows)

    candidates.sort(key=lambda row: float(row["ev_per_yen"]), reverse=True)
    candidate_fields = [
        "race_id",
        "race_date",
        "horse_no",
        "selection",
        "win_odds",
        "popularity",
        "probability",
        "ev_per_yen",
        "actual_win",
        "blended_edge",
        "condition_count",
        "condition_edge",
        "course_condition_count",
        "course_condition_edge",
        "sire_name",
        "sire_condition_count",
        "sire_condition_edge",
        "dam_sire_name",
        "dam_sire_condition_count",
        "dam_sire_condition_edge",
        "surface_group",
        "distance_bucket",
        "race_class",
        "field_bucket",
    ]
    with Path(args.top_candidates).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=candidate_fields)
        writer.writeheader()
        writer.writerows(candidates[: args.top_n])

    print(f"bets={len(bets)} output={args.output}")
    print(f"summary={args.summary}")
    print(f"top_candidates={args.top_candidates}")
    print(f"skipped={dict(sorted(skipped.items()))}")
    print(summary_rows[-1])


if __name__ == "__main__":
    main()
