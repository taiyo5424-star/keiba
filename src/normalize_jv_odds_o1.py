import argparse
import csv
from pathlib import Path


def b(raw: str, start: int, end: int) -> str:
    return raw.encode("cp932", errors="ignore")[start:end].decode("cp932", errors="ignore")


def parse_odds(value: str) -> str:
    value = value.strip()
    if not value or "-" in value or "*" in value:
        return ""
    try:
        odds = int(value) / 10
    except ValueError:
        return ""
    if odds <= 0:
        return ""
    return f"{odds:.1f}"


def common_fields(raw: str) -> dict[str, str]:
    race_date = b(raw, 11, 19)
    course_code = b(raw, 19, 21)
    meeting = b(raw, 21, 23)
    day = b(raw, 23, 25)
    race_no = b(raw, 25, 27)
    observed_md_hm = b(raw, 27, 35)
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
        "observed_at": f"{race_date[:4]}-{observed_md_hm[:2]}-{observed_md_hm[2:4]}T{observed_md_hm[4:6]}:{observed_md_hm[6:8]}:00+09:00",
    }


def read_starts(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return {
            (row["race_id"], row["horse_no"]): row
            for row in csv.DictReader(f)
        }


def append_win_rows(raw: str, common: dict[str, str], starts: dict[tuple[str, str], dict[str, str]], rows: list[dict[str, str]]) -> None:
    base = 43
    width = 8
    for i in range(28):
        offset = base + i * width
        horse_no = b(raw, offset, offset + 2)
        odds = parse_odds(b(raw, offset + 2, offset + 6))
        popularity = b(raw, offset + 6, offset + 8).strip()
        if not horse_no.strip() or not odds:
            continue
        start = starts.get((common["race_id"], horse_no.strip().zfill(2)), {})
        rows.append(
            {
                **common,
                "bet_type": "win",
                "horse_no": horse_no.strip().zfill(2),
                "selection": start.get("horse_name", horse_no.strip().zfill(2)),
                "odds": odds,
                "odds_min": odds,
                "odds_max": odds,
                "popularity": popularity,
                "source": "jra-van-0B31",
            }
        )


def append_place_rows(raw: str, common: dict[str, str], starts: dict[tuple[str, str], dict[str, str]], rows: list[dict[str, str]]) -> None:
    base = 267
    width = 12
    for i in range(28):
        offset = base + i * width
        horse_no = b(raw, offset, offset + 2)
        odds_min = parse_odds(b(raw, offset + 2, offset + 6))
        odds_max = parse_odds(b(raw, offset + 6, offset + 10))
        popularity = b(raw, offset + 10, offset + 12).strip()
        if not horse_no.strip() or not odds_min or not odds_max:
            continue
        start = starts.get((common["race_id"], horse_no.strip().zfill(2)), {})
        rows.append(
            {
                **common,
                "bet_type": "place",
                "horse_no": horse_no.strip().zfill(2),
                "selection": start.get("horse_name", horse_no.strip().zfill(2)),
                "odds": odds_min,
                "odds_min": odds_min,
                "odds_max": odds_max,
                "popularity": popularity,
                "source": "jra-van-0B31",
            }
        )


def normalize(input_path: Path, starts_path: Path) -> list[dict[str, str]]:
    starts = read_starts(starts_path)
    rows: list[dict[str, str]] = []
    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["record_type"] != "O1":
                continue
            raw = row["raw"]
            common = common_fields(raw)
            append_win_rows(raw, common, starts, rows)
            append_place_rows(raw, common, starts, rows)
    rows.sort(key=lambda row: (row["race_id"], row["bet_type"], int(row["horse_no"])))
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_live_odds(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["race_id", "bet_type", "selection", "odds", "source", "observed_at"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize JV-Link O1 win/place odds records.")
    parser.add_argument("--input", default="data/jra_van_exports/raw_rt_0b31_2026061409030411.csv")
    parser.add_argument("--starts", default="data/jra_van_exports/starts_minimal.csv")
    parser.add_argument("--output", default="data/jra_van_exports/odds_win_place_minimal.csv")
    parser.add_argument("--live-output", default="data/live_odds.csv")
    args = parser.parse_args()

    rows = normalize(Path(args.input), Path(args.starts))
    write_csv(Path(args.output), rows)
    write_live_odds(Path(args.live_output), rows)
    print(f"odds_rows={len(rows)} output={args.output}")
    print(f"live_output={args.live_output}")


if __name__ == "__main__":
    main()
