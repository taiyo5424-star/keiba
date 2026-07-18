import argparse
import csv
from pathlib import Path


def clean(value: str) -> str:
    return value.replace("\u3000", " ").strip()


def b(raw: str, start: int, end: int) -> str:
    return raw.encode("cp932", errors="ignore")[start:end].decode("cp932", errors="ignore")


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


def parse_tenths(value: str) -> float | None:
    value = value.strip()
    if not value or not value.isdigit():
        return None
    return int(value) / 10


def normalize_se(raw: str) -> dict[str, str] | None:
    data_kubun = b(raw, 2, 3)
    if data_kubun not in {"5", "6", "7"}:
        return None

    finish_rank = parse_int(b(raw, 334, 336))
    arrival_order = parse_int(b(raw, 331, 334))
    race_time = parse_tenths(b(raw, 337, 342))
    runner_last3f_time = parse_tenths(b(raw, 389, 393))
    win_odds = parse_odds(b(raw, 359, 363))
    popularity = parse_int(b(raw, 363, 365))
    horse_no = b(raw, 28, 30).strip().zfill(2)
    if finish_rank is None or win_odds is None or not horse_no.strip("0"):
        return None

    race_date = b(raw, 11, 19)
    course_code = b(raw, 19, 21)
    meeting = b(raw, 21, 23)
    day = b(raw, 23, 25)
    race_no = b(raw, 25, 27)
    return {
        "race_id": f"{race_date}{course_code}{meeting}{day}{race_no}",
        "race_date": race_date,
        "course_code": course_code,
        "meeting": meeting,
        "day": day,
        "race_no": race_no,
        "horse_no": horse_no,
        "horse_id": b(raw, 30, 40),
        "horse_name": clean(b(raw, 40, 76)),
        "jockey_code": b(raw, 296, 301),
        "jockey_name": clean(b(raw, 306, 314)),
        "trainer_code": b(raw, 85, 90),
        "trainer_name": clean(b(raw, 90, 98)),
        "horse_weight": b(raw, 324, 327).strip(),
        "weight_diff_sign": b(raw, 327, 328).strip(),
        "weight_diff": b(raw, 328, 331).strip(),
        "arrival_order": "" if arrival_order is None else str(arrival_order),
        "finish_rank": str(finish_rank),
        "label_win": "1" if finish_rank == 1 else "0",
        "race_time": "" if race_time is None else f"{race_time:.1f}",
        "margin_code": b(raw, 342, 348).strip(),
        "runner_last3f_time": "" if runner_last3f_time is None else f"{runner_last3f_time:.1f}",
        "result_detail_raw": b(raw, 331, 397).strip(),
        "win_odds": f"{win_odds:.1f}",
        "win_popularity": "" if popularity is None else str(popularity),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a minimal win-probability training dataset from JV-Link SE records.")
    parser.add_argument("--input", default="data/jra_van_exports/raw_race_2025_to_now_full.csv")
    parser.add_argument("--output", default="data/model/win_training_minimal.csv")
    args = parser.parse_args()

    rows: list[dict[str, str]] = []
    with Path(args.input).open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["record_type"] != "SE":
                continue
            normalized = normalize_se(row["raw"])
            if normalized:
                rows.append(normalized)

    fields = [
        "race_id",
        "race_date",
        "course_code",
        "meeting",
        "day",
        "race_no",
        "horse_no",
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
        "label_win",
        "race_time",
        "margin_code",
        "runner_last3f_time",
        "result_detail_raw",
        "win_odds",
        "win_popularity",
    ]
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    races = {row["race_id"] for row in rows}
    winners = sum(1 for row in rows if row["label_win"] == "1")
    print(f"rows={len(rows)} races={len(races)} winners={winners} output={args.output}")


if __name__ == "__main__":
    main()
