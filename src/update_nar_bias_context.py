import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path


REVIEWS = Path("data/nar_feedback/race_reviews.csv")
BIAS = Path("data/nar_feedback/bias_context.csv")


def score_note(value: str, positive: set[str], negative: set[str] | None = None) -> int:
    value = (value or "").strip().lower()
    if value in positive:
        return 1
    if negative and value in negative:
        return -1
    return 0


def confidence(sample_size: int, strongest_abs_score: int) -> str:
    if sample_size >= 5 and strongest_abs_score >= 3:
        return "high"
    if sample_size >= 3 and strongest_abs_score >= 2:
        return "medium"
    return "low"


def summarize(front: int, closer: int, inside: int, outside: int, speed: int, conf: str) -> str:
    parts: list[str] = []
    if front > closer and front >= 2:
        parts.append("front/stalker positive")
    elif closer > front and closer >= 2:
        parts.append("closer positive")
    if inside > outside and inside >= 2:
        parts.append("inside positive")
    elif outside > inside and outside >= 2:
        parts.append("outside positive")
    if speed >= 2:
        parts.append("fast track")
    elif speed <= -2:
        parts.append("slow/tough track")
    if not parts:
        parts.append("no clear same-day bias")
    return f"{'; '.join(parts)}; confidence={conf}"


def read_reviews() -> list[dict[str, str]]:
    if not REVIEWS.exists():
        return []
    with REVIEWS.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in read_reviews():
        if row.get("race_date") and row.get("venue"):
            grouped[(row["race_date"], row["venue"])].append(row)

    rows: list[dict[str, str]] = []
    now = datetime.now().isoformat(timespec="seconds")

    for (race_date, venue), reviews in sorted(grouped.items()):
        reviews = sorted(reviews, key=lambda r: int(r.get("race_no") or 0))
        front = closer = inside = outside = speed = 0
        max_race_no = 0
        for r in reviews:
            max_race_no = max(max_race_no, int(r.get("race_no") or 0))
            front += score_note(r.get("position_bias", ""), {"front", "stalker"})
            closer += score_note(r.get("position_bias", ""), {"closer"})
            inside += score_note(r.get("rail_bias", ""), {"inside"})
            outside += score_note(r.get("rail_bias", ""), {"outside"})
            speed += score_note(r.get("track_speed", ""), {"fast"}, {"slow"})

        strongest = max(abs(front), abs(closer), abs(inside), abs(outside), abs(speed))
        conf = confidence(len(reviews), strongest)
        rows.append(
            {
                "race_date": race_date,
                "venue": venue,
                "updated_after_race_no": str(max_race_no),
                "sample_size": str(len(reviews)),
                "front_score": str(front),
                "closer_score": str(closer),
                "inside_score": str(inside),
                "outside_score": str(outside),
                "speed_score": str(speed),
                "bias_summary": summarize(front, closer, inside, outside, speed, conf),
                "confidence": conf,
                "updated_at": now,
            }
        )

    BIAS.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "race_date",
        "venue",
        "updated_after_race_no",
        "sample_size",
        "front_score",
        "closer_score",
        "inside_score",
        "outside_score",
        "speed_score",
        "bias_summary",
        "confidence",
        "updated_at",
    ]
    with BIAS.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {BIAS} ({len(rows)} venue-days)")


if __name__ == "__main__":
    main()
