import argparse
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd


FEATURES = [
    "final_rank_score",
    "recent_speed",
    "pace_fit",
    "distance_fit",
    "jockey_score",
    "trainer_score",
    "market_probability",
]


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(x, -35, 35)))


def standardize(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std[std == 0] = 1
    return (x - mean) / std, mean, std


def train_logistic(x: np.ndarray, y: np.ndarray, epochs: int, lr: float, l2: float) -> np.ndarray:
    weights = np.zeros(x.shape[1])
    for _ in range(epochs):
        pred = sigmoid(x @ weights)
        grad = (x.T @ (pred - y)) / len(y)
        grad[1:] += l2 * weights[1:]
        weights -= lr * grad
    return weights


def brier_score(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def log_loss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def calibration_bins(y: np.ndarray, p: np.ndarray, bins: int = 5) -> list[dict[str, float]]:
    rows = []
    cuts = np.linspace(0, 1, bins + 1)
    for lo, hi in zip(cuts[:-1], cuts[1:]):
        mask = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if not mask.any():
            continue
        rows.append(
            {
                "bin_low": float(lo),
                "bin_high": float(hi),
                "count": int(mask.sum()),
                "avg_probability": float(p[mask].mean()),
                "actual_rate": float(y[mask].mean()),
            }
        )
    return rows


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_predictions(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["race_id", "race_name", "bet_type", "selection", "probability", "confidence", "reason"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a dependency-light baseline probability model.")
    parser.add_argument("--train", default="data/model_training_example.csv")
    parser.add_argument("--score", default="data/model_scoring_example.csv")
    parser.add_argument("--predictions", default="outputs/model_predictions_example.csv")
    parser.add_argument("--model", default="outputs/baseline_model.json")
    parser.add_argument("--epochs", type=int, default=3000)
    parser.add_argument("--lr", type=float, default=0.05)
    parser.add_argument("--l2", type=float, default=0.01)
    args = parser.parse_args()

    train_df = pd.read_csv(args.train)
    x_raw = train_df[FEATURES].astype(float).to_numpy()
    y = train_df["label"].astype(float).to_numpy()
    x_scaled, mean, std = standardize(x_raw)
    x = np.c_[np.ones(len(x_scaled)), x_scaled]

    weights = train_logistic(x, y, args.epochs, args.lr, args.l2)
    train_p = sigmoid(x @ weights)

    score_df = pd.read_csv(args.score)
    score_x = (score_df[FEATURES].astype(float).to_numpy() - mean) / std
    score_p = sigmoid(np.c_[np.ones(len(score_x)), score_x] @ weights)

    prediction_rows = []
    for row, probability in zip(score_df.to_dict("records"), score_p):
        prediction_rows.append(
            {
                "race_id": row["race_id"],
                "race_name": row["race_name"],
                "bet_type": row.get("bet_type", "win"),
                "selection": row["selection"],
                "probability": f"{probability:.6f}",
                "confidence": "low",
                "reason": row.get("reason", "baseline_model"),
            }
        )

    write_predictions(Path(args.predictions), prediction_rows)
    save_json(
        Path(args.model),
        {
            "features": FEATURES,
            "weights": weights.tolist(),
            "mean": mean.tolist(),
            "std": std.tolist(),
            "train_brier": brier_score(y, train_p),
            "train_log_loss": log_loss(y, train_p),
            "calibration_bins": calibration_bins(y, train_p),
            "warning": "Example baseline only. Use time-split validation before real betting.",
        },
    )

    print(f"rows={len(prediction_rows)} train_brier={brier_score(y, train_p):.4f} train_log_loss={log_loss(y, train_p):.4f}")
    print(f"predictions={args.predictions}")
    print(f"model={args.model}")


if __name__ == "__main__":
    main()
