import argparse
import csv
from pathlib import Path


def clean(value: str) -> str:
    return value.replace("\u3000", " ").strip()


def b(raw: str, start: int, end: int) -> str:
    return raw.encode("cp932", errors="ignore")[start:end].decode("cp932", errors="ignore")


def common_fields(raw: str) -> dict[str, str]:
    race_date = b(raw, 11, 19)
    course_code = b(raw, 19, 21)
    meeting = b(raw, 21, 23)
    day = b(raw, 23, 25)
    race_no = b(raw, 25, 27)
    return {
        "record_type": b(raw, 0, 2),
        "data_kubun": b(raw, 2, 3),
        "created_date": b(raw, 3, 11),
        "race_date": race_date,
        "course_code": course_code,
        "meeting": meeting,
        "day": day,
        "race_no": race_no,
        "race_id": f"{race_date}{course_code}{meeting}{day}{race_no}",
    }


def normalize_race(raw: str) -> dict[str, str]:
    row = common_fields(raw)
    distance = b(raw, 697, 701).strip()
    track_code = b(raw, 705, 707).strip()
    surface = (
        "turf"
        if track_code.startswith("1")
        else "dirt"
        if track_code.startswith("2")
        else "jump"
        if track_code.startswith("3")
        else "other"
    )
    going_code = b(raw, 879, 881).strip()
    lap_times_raw = b(raw, 885, 945).strip()
    race_corner_passage_raw = b(raw, 965, 1130).strip()
    row.update(
        {
            "race_name": clean(b(raw, 32, 92)),
            "grade_code": b(raw, 614, 615).strip(),
            "race_type_code": b(raw, 616, 618).strip(),
            "race_symbol_code": b(raw, 618, 621).strip(),
            "weight_type_code": b(raw, 621, 622).strip(),
            "condition_2yo": b(raw, 622, 625).strip(),
            "condition_3yo": b(raw, 625, 628).strip(),
            "condition_4yo": b(raw, 628, 631).strip(),
            "condition_5up": b(raw, 631, 634).strip(),
            "condition_youngest": b(raw, 634, 637).strip(),
            "distance": distance,
            "track_code": track_code,
            "weather_code": b(raw, 877, 879).strip(),
            "going_code": going_code,
            "turf_going_code": going_code if surface == "turf" else "",
            "dirt_going_code": going_code if surface == "dirt" else "",
            "lap_times_raw": lap_times_raw,
            "race_corner_passage_raw": race_corner_passage_raw,
            "surface_group": surface,
            "post_time": b(raw, 873, 877).strip(),
            "registered_count": b(raw, 881, 883).strip(),
            "starter_count": b(raw, 883, 885).strip(),
            "raw_length": str(len(raw)),
        }
    )
    return row


def normalize_start(raw: str) -> dict[str, str]:
    row = common_fields(raw)
    race_time = b(raw, 337, 342).strip()
    runner_last3f_time = b(raw, 389, 393).strip()
    row.update(
        {
            "gate": b(raw, 27, 28),
            "horse_no": b(raw, 28, 30),
            "horse_id": b(raw, 30, 40),
            "horse_name": clean(b(raw, 40, 76)),
            "trainer_code": b(raw, 85, 90),
            "trainer_name": clean(b(raw, 90, 98)),
            "jockey_code": b(raw, 296, 301),
            "jockey_name": clean(b(raw, 306, 314)),
            "horse_weight": b(raw, 324, 327).strip(),
            "weight_diff_sign": b(raw, 327, 328).strip(),
            "weight_diff": b(raw, 328, 331).strip(),
            "arrival_order": b(raw, 331, 334).strip(),
            "finish_rank": b(raw, 334, 336).strip(),
            "race_time": f"{int(race_time) / 10:.1f}" if race_time.isdigit() else "",
            "margin_code": b(raw, 342, 348).strip(),
            "runner_last3f_time": f"{int(runner_last3f_time) / 10:.1f}" if runner_last3f_time.isdigit() else "",
            "result_detail_raw": b(raw, 331, 397).strip(),
            "raw_length": str(len(raw)),
        }
    )
    return row


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize minimal RA/SE records from raw JV-Link RACE export.")
    parser.add_argument("--input", default="data/jra_van_exports/raw_race_records.csv")
    parser.add_argument("--out-dir", default="data/jra_van_exports")
    args = parser.parse_args()

    races: list[dict[str, str]] = []
    starts: list[dict[str, str]] = []
    with Path(args.input).open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            raw = row["raw"]
            if row["record_type"] == "RA":
                races.append(normalize_race(raw))
            elif row["record_type"] == "SE":
                starts.append(normalize_start(raw))

    out_dir = Path(args.out_dir)
    race_fields = [
        "record_type",
        "race_id",
        "race_date",
        "course_code",
        "meeting",
        "day",
        "race_no",
        "race_name",
        "grade_code",
        "race_type_code",
        "race_symbol_code",
        "weight_type_code",
        "condition_2yo",
        "condition_3yo",
        "condition_4yo",
        "condition_5up",
        "condition_youngest",
        "distance",
        "track_code",
        "weather_code",
        "going_code",
        "turf_going_code",
        "dirt_going_code",
        "lap_times_raw",
        "race_corner_passage_raw",
        "surface_group",
        "post_time",
        "registered_count",
        "starter_count",
        "data_kubun",
        "created_date",
        "raw_length",
    ]
    start_fields = [
        "record_type",
        "race_id",
        "race_date",
        "course_code",
        "meeting",
        "day",
        "race_no",
        "horse_no",
        "gate",
        "horse_id",
        "horse_name",
        "jockey_code",
        "jockey_name",
        "trainer_code",
        "trainer_name",
        "horse_weight",
        "weight_diff_sign",
        "weight_diff",
        "arrival_order",
        "finish_rank",
        "race_time",
        "margin_code",
        "runner_last3f_time",
        "result_detail_raw",
        "data_kubun",
        "created_date",
        "raw_length",
    ]
    write_csv(out_dir / "races_minimal.csv", races, race_fields)
    write_csv(out_dir / "starts_minimal.csv", starts, start_fields)
    print(f"races={len(races)} output={out_dir / 'races_minimal.csv'}")
    print(f"starts={len(starts)} output={out_dir / 'starts_minimal.csv'}")


if __name__ == "__main__":
    main()
