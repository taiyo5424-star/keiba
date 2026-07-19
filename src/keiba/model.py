"""条件付きロジット(多項ロジット)による勝率モデル — Benter (1994) の原型。

レース内の各馬の効用 u_i = x_i・w を softmax して勝率にする。
損失はレース単位の多項対数尤度。numpy のみで実装(外部ML依存なし)。
LightGBM 等に置き換える場合も、出力確率を calibration.py で較正確認し、
blend.py で市場確率と結合してから使うこと(モデル単体の確率は使わない)。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from keiba.features import FEATURE_COLUMNS


@dataclass
class ConditionalLogitModel:
    feature_columns: list
    weights: np.ndarray | None = None
    mean_: np.ndarray | None = None
    std_: np.ndarray | None = None

    def _design(self, df: pd.DataFrame) -> np.ndarray:
        X = df[self.feature_columns].to_numpy(dtype=float)
        if self.mean_ is None:
            self.mean_ = X.mean(axis=0)
            self.std_ = X.std(axis=0) + 1e-9
        return (X - self.mean_) / self.std_

    def fit(
        self,
        df: pd.DataFrame,
        n_iter: int = 300,
        lr: float = 0.2,
        l2: float = 1e-3,
        race_col: str = "race_id",
        label_col: str = "won",
    ) -> "ConditionalLogitModel":
        """レースごとの softmax 尤度を勾配上昇で最大化する。"""
        X = self._design(df)
        y = df[label_col].to_numpy(dtype=float)
        groups = df[race_col].to_numpy()
        # レース境界のインデックス(入力はレースごとに連続している前提で並べ替え)
        order = np.argsort(groups, kind="stable")
        X, y, groups = X[order], y[order], groups[order]
        _, start_idx = np.unique(groups, return_index=True)
        bounds = np.append(np.sort(start_idx), len(groups))

        w = np.zeros(X.shape[1])
        n_races = len(bounds) - 1
        for _ in range(n_iter):
            grad = -l2 * w
            for k in range(n_races):
                s, e = bounds[k], bounds[k + 1]
                if y[s:e].sum() != 1:
                    continue  # 勝者が特定できないレースは学習から除外
                z = X[s:e] @ w
                z -= z.max()
                p = np.exp(z)
                p /= p.sum()
                grad += X[s:e].T @ (y[s:e] - p)
            w += lr * grad / n_races
        self.weights = w
        return self

    def predict_race_probs(self, df: pd.DataFrame) -> np.ndarray:
        """1レース分のDataFrame(全出走馬)に対する勝率を返す。"""
        if self.weights is None:
            raise RuntimeError("model is not fitted")
        X = (df[self.feature_columns].to_numpy(dtype=float) - self.mean_) / self.std_
        z = X @ self.weights
        z -= z.max()
        p = np.exp(z)
        return p / p.sum()

    def predict(self, df: pd.DataFrame, race_col: str = "race_id") -> pd.Series:
        """複数レースのDataFrameにレース内正規化済みの勝率列を返す。"""
        out = np.empty(len(df))
        for _, idx in df.groupby(race_col, sort=False).indices.items():
            out[idx] = self.predict_race_probs(df.iloc[idx])
        return pd.Series(out, index=df.index, name="model_prob")


def mean_race_log_likelihood(
    probs: pd.Series, df: pd.DataFrame, race_col: str = "race_id", label_col: str = "won"
) -> float:
    """勝ち馬に割り当てた確率の平均対数尤度(モデル比較の共通指標)。

    市場確率・モデル確率・結合確率を同じ土俵で比較するのに使う。
    blend.py の log_likelihood と同じ定義。
    """
    ll = 0.0
    n = 0
    for _, g in df.groupby(race_col):
        winners = g.index[g[label_col] == 1]
        if len(winners) != 1:
            continue
        ll += float(np.log(max(probs.loc[winners[0]], 1e-300)))
        n += 1
    return ll / max(n, 1)
