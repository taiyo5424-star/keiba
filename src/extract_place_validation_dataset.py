import argparse
import csv
from collections import defaultdict
from pathlib import Path


def b(raw: str, start: int, end: int) -> str:
    return raw.encode("cp932", errors="ignore")[start:end].decode("cp932", errors="ignore")


def clean(value: str) -> str:
    return value.replace("　", " ").strip()


def parse_int(value: str) -> int | None:
    value = value.strip()
    if not value or not value.isdigit():
        return None
    return int(value)


def parse_odds(value: str) -> float | None:
    value = value.strip()
    if not value or not value.isdigit():
        return None
    odds = int(value) / 10
    if odds <= 0:
        return None
    return odds


def race_id_of(raw: str) -> str:
    return f"{b(raw, 11, 19)}{b(raw, 19, 21)}{b(raw, 21, 23)}{b(raw, 23, 25)}{b(raw, 25, 27)}"


def parse_se(raw: str) -> dict[str, str] | None:
    if b(raw, 2, 3) not in {"5", "6", "7"}:
        return None
    finish_rank = parse_int(b(raw, 334, 336))
    win_odds = parse_odds(b(raw, 359, 363))
    horse_no = b(raw, 28, 30).strip().zfill(2)
    if finish_rank is None or not horse_no.strip("0"):
        return None
    popularity = parse_int(b(raw, 363, 365))
    return {
        "race_id": race_id_of(raw),
        "race_date": b(raw, 11, 19),
        "course_code": b(raw, 19, 21),
        "race_no": b(raw, 25, 27),
        "horse_no": horse_no,
        "horse_id": b(raw, 30, 40),
        "horse_name": clean(b(raw, 40, 76)),
        "finish_rank": str(finish_rank),
        "win_odds": "" if win_odds is None else f"{win_odds:.1f}",
        "win_popularity": "" if popularity is None else str(popularity),
    }


def parse_o1_place(raw: str) -> tuple[str, str, dict[str, dict[str, str]]]:
    """Return (race_id, data_kubun, {horse_no: place odds fields})."""
    race_id = race_id_of(raw)
    data_kubun = b(raw, 2, 3)
    place: dict[str, dict[str, str]] = {}
    base = 267
    width = 12
    for i in range(28):
        offset = base + i * width
        horse_no = b(raw, offset, offset + 2).strip()
        odds_min = parse_odds(b(raw, offset + 2, offset + 6))
        odds_max = parse_odds(b(raw, offset + 6, offset + 10))
        popularity = b(raw, offset + 10, offset + 12).strip()
        if not horse_no or odds_min is None or odds_max is None:
            continue
        place[horse_no.zfill(2)] = {
            "place_odds_min": f"{odds_min:.1f}",
            "place_odds_max": f"{odds_max:.1f}",
            "place_popularity": popularity,
        }
    return race_id, data_kubun, place


def parse_hr(raw: str) -> tuple[str, dict[str, str]]:
    """Return (race_id, info) where info holds starters, place payouts, flags."""
    race_id = race_id_of(raw)
    starters = b(raw, 29, 31).strip()
    place_fusei = b(raw, 32, 33)  # 不成立フラグ, index 1 = 複勝
    place_tokubarai = b(raw, 41, 42)  # 特払フラグ, index 1 = 複勝
    refunded = {
        str(i + 1).zfill(2)
        for i, flag in enumerate(b(raw, 58, 86))
        if flag == "1"
    }
    payouts: dict[str, int] = {}
    base = 141
    width = 13
    for i in range(5):
        offset = base + i * width
        horse_no = b(raw, offset, offset + 2).strip()
        amount = parse_int(b(raw, offset + 2, offset + 11))
        if not horse_no or not horse_no.isdigit() or not amount:
            continue
        payouts[horse_no.zfill(2)] = amount
    return race_id, {
        "starters": starters,
        "place_fusei": place_fusei,
        "place_tokubarai": place_tokubarai,
        "refunded": refunded,
        "payouts": payouts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Join SE results, final O1 place odds, and HR place payouts into a place-EV validation dataset."
    )
    parser.add_argument("--input", default="data/jra_van_exports/raw_race_2025_to_now_full.csv")
    parser.add_argument("--output", default="data/model/place_validation.csv")
    args = parser.parse_args()

    se_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    o1_by_race: dict[str, tuple[str, dict[str, dict[str, str]]]] = {}
    hr_by_race: dict[str, dict] = {}

    with Path(args.input).open("r", encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f):
            record_type = row["record_type"]
            raw = row["raw"]
            if record_type == "SE":
                se = parse_se(raw)
                if se:
                    se_rows[se["race_id"]].append(se)
            elif record_type == "O1":
                race_id, data_kubun, place = parse_o1_place(raw)
                current = o1_by_race.get(race_id)
                if place and (current is None or data_kubun >= current[0]):
                    o1_by_race[race_id] = (data_kubun, place)
            elif record_type == "HR":
                race_id, info = parse_hr(raw)
                hr_by_race[race_id] = info

    output_rows: list[dict[str, str]] = []
    races_complete = 0
    for race_id in sorted(se_rows):
        hr = hr_by_race.get(race_id)
        o1 = o1_by_race.get(race_id)
        if not hr or not o1:
            continue
        if hr["place_fusei"] == "1" or hr["place_tokubarai"] == "1":
            continue
        races_complete += 1
        data_kubun, place_odds = o1
        for se in sorted(se_rows[race_id], key=lambda r: r["horse_no"]):
            horse_no = se["horse_no"]
            if horse_no in hr["refunded"]:
                continue
            odds = place_odds.get(horse_no, {})
            payout = hr["payouts"].get(horse_no, 0)
            output_rows.append(
                {
                    **se,
                    "num_starters": hr["starters"],
                    "place_odds_min": odds.get("place_odds_min", ""),
                    "place_odds_max": odds.get("place_odds_max", ""),
                    "place_popularity": odds.get("place_popularity", ""),
                    "place_label": "1" if payout > 0 else "0",
                    "place_payout_yen": str(payout) if payout > 0 else "0",
                    "o1_data_kubun": data_kubun,
                }
            )

    fields = [
        "race_id",
        "race_date",
        "course_code",
        "race_no",
        "num_starters",
        "horse_no",
        "horse_id",
        "horse_name",
        "finish_rank",
        "win_odds",
        "win_popularity",
        "place_odds_min",
        "place_odds_max",
        "place_popularity",
        "place_label",
        "place_payout_yen",
        "o1_data_kubun",
    ]
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(output_rows)

    dates = sorted({row["race_date"] for row in output_rows})
    placed = sum(1 for row in output_rows if row["place_label"] == "1")
    print(f"runners={len(output_rows)} races={races_complete} placed={placed}")
    if dates:
        print(f"date_range={dates[0]}..{dates[-1]} days={len(dates)}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
