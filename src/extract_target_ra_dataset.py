import argparse
import csv
from pathlib import Path


COURSE_NAMES = {
    "01": "札幌",
    "02": "函館",
    "03": "福島",
    "04": "新潟",
    "05": "東京",
    "06": "中山",
    "07": "中京",
    "08": "京都",
    "09": "阪神",
    "10": "小倉",
}


def b(raw: str, start: int, end: int) -> str:
    return raw.encode("cp932", errors="ignore")[start:end].decode("cp932", errors="ignore")


def clean(value: str) -> str:
    return value.replace("\u3000", " ").strip()


def surface_group(track_code: str) -> str:
    if track_code.startswith("1"):
        return "turf"
    if track_code.startswith("2"):
        return "dirt"
    if track_code.startswith("3"):
        return "jump"
    return "other"


def normalize_ra(raw: str) -> dict[str, str] | None:
    race_date = b(raw, 11, 19)
    course_code = b(raw, 19, 21)
    meeting = b(raw, 21, 23)
    day = b(raw, 23, 25)
    race_no = b(raw, 25, 27)
    distance = b(raw, 697, 701).strip()
    track_code = b(raw, 705, 707).strip()
    surface = surface_group(track_code)
    going_code = b(raw, 879, 881).strip()
    if not race_date or not course_code or not race_no:
        return None
    return {
        "race_id": f"{race_date}{course_code}{meeting}{day}{race_no}",
        "race_date": race_date,
        "course_code": course_code,
        "course_name": COURSE_NAMES.get(course_code, course_code),
        "meeting": meeting,
        "day": day,
        "race_no": race_no,
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
        "lap_times_raw": b(raw, 885, 945).strip(),
        "race_corner_passage_raw": b(raw, 965, 1130).strip(),
        "surface_group": surface,
        "post_time": b(raw, 873, 877).strip(),
        "registered_count": b(raw, 881, 883).strip(),
        "starter_count": b(raw, 883, 885).strip(),
    }


def iter_ra(path: Path):
    for line in path.read_bytes().splitlines():
        if not line:
            continue
        raw = line.decode("cp932", errors="ignore").rstrip("\r\n\0")
        if raw.startswith("RA"):
            row = normalize_ra(raw)
            if row:
                yield row


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract race details from TARGET frontier JV RA files.")
    parser.add_argument("--target-se-dir", default=r"C:\TFJV\SE_DATA")
    parser.add_argument("--start-year", type=int, default=2004)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--output", default="data/model/target_races_2004_2026.csv")
    args = parser.parse_args()

    rows = []
    root = Path(args.target_se_dir)
    for year in range(args.start_year, args.end_year + 1):
        year_dir = root / str(year)
        if not year_dir.exists():
            continue
        for path in sorted(year_dir.glob("SR*.DAT")):
            rows.extend(iter_ra(path))

    fields = [
        "race_id",
        "race_date",
        "course_code",
        "course_name",
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
    ]
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"rows={len(rows)} output={args.output}")


if __name__ == "__main__":
    main()
