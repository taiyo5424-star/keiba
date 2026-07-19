"""エンドツーエンドのパイプラインデモ(合成データ)。

流れ: 合成レース履歴 → SQLite格納 → PIT特徴量 → 条件付きロジット学習
     → 市場確率とロジット結合(Benter較正) → EV閾値+1/4ケリーでバックテスト

「モデル単体 < 市場 < 結合」という対数尤度の序列と、結合確率による
EVフィルタが控除率をどこまで跳ね返すかを確認する。
実データ(JRA-VAN等)に差し替えるときも、この流れをそのまま使う。

実行: python examples/pipeline_demo.py
"""

import numpy as np
import pandas as pd

from keiba.backtest import backtest_win_bets
from keiba.blend import blend_probabilities, fit_blend_weights, log_likelihood
from keiba.features import FEATURE_COLUMNS, build_pit_features, time_series_split
from keiba.model import ConditionalLogitModel, mean_race_log_likelihood
from keiba.store import connect, insert_races, insert_runners

rng = np.random.default_rng(7)

# ---------- 1. 合成世界: 馬・騎手の能力からレース結果と市場オッズを生成 ----------
N_HORSES, N_RACES, FIELD = 80, 600, 8
ability = {f"H{i}": rng.normal(0, 1) for i in range(N_HORSES)}
j_skill = {f"J{i}": rng.normal(0, 0.3) for i in range(14)}

races, runners, market_rows = [], [], []
date = pd.Timestamp("2023-01-01")
for r in range(N_RACES):
    rid = f"R{r:04d}"
    date += pd.Timedelta(days=1)
    races.append({"race_id": rid, "date": date.strftime("%Y-%m-%d"), "organizer": "jra"})
    ids = rng.choice(N_HORSES, size=FIELD, replace=False)
    entries, utils = [], []
    for no, h in enumerate(ids, start=1):
        hid, jid = f"H{h}", f"J{rng.integers(14)}"
        utils.append(ability[hid] + j_skill[jid])
        entries.append({"race_id": rid, "horse_no": no, "horse_id": hid,
                        "jockey_id": jid, "trainer_id": f"T{h % 12}",
                        "age": int(rng.integers(3, 8)), "weight": 55.0,
                        "body_weight": 480.0})
    u = np.asarray(utils)
    true_p = np.exp(u) / np.exp(u).sum()
    # 市場は真の確率のノイズ版(≒賢い群衆)。払戻率0.8でオッズ化
    market_p = true_p * rng.gamma(60, 1 / 60, size=FIELD)
    market_p /= market_p.sum()
    odds = 0.8 / market_p
    winner = rng.choice(FIELD, p=true_p)
    finish = np.empty(FIELD, dtype=int)
    rest = [i for i in range(FIELD) if i != winner]
    finish[winner] = 1
    for pos, idx in enumerate(rng.permutation(rest), start=2):
        finish[idx] = pos
    for i, e in enumerate(entries):
        e["finish_pos"] = int(finish[i])
        e["win_odds_final"] = float(odds[i])
    runners.extend(entries)

conn = connect(":memory:")
insert_races(conn, pd.DataFrame(races))
insert_runners(conn, pd.DataFrame(runners))
print(f"合成データ: {N_RACES}レース {N_RACES * FIELD}出走を格納")

# ---------- 2. PIT特徴量 → 時系列分割 → モデル学習 ----------
runners_df = pd.DataFrame(runners)
feats = build_pit_features(pd.DataFrame(races), runners_df)
feats = feats.merge(
    runners_df[["race_id", "horse_no", "win_odds_final"]], on=["race_id", "horse_no"]
)
train, test = time_series_split(feats, train_frac=0.6)
model = ConditionalLogitModel(feature_columns=FEATURE_COLUMNS)
model.fit(train, n_iter=250)
print(f"学習: {train['race_id'].nunique()}レース / 検証: {test['race_id'].nunique()}レース")

# ---------- 3. Benter較正: モデル確率×市場確率のロジット結合 ----------
test = test.copy()
test["model_prob"] = model.predict(test)
inv = 1.0 / test["win_odds_final"]
test["market_prob"] = inv / inv.groupby(test["race_id"]).transform("sum")

# 結合係数は検証期間の前半で推定し、後半で評価(さらに時系列を守る)
race_ids = test.sort_values("date")["race_id"].unique()
fit_ids = set(race_ids[: len(race_ids) // 2])
eval_ids = [rid for rid in race_ids if rid not in fit_ids]

def to_tuples(df, ids):
    out = []
    for rid in ids:
        g = df[df["race_id"] == rid]
        w = np.flatnonzero(g["won"].to_numpy() == 1)
        if len(w) != 1:
            continue
        out.append((g["model_prob"].to_numpy(), g["market_prob"].to_numpy(), int(w[0])))
    return out

alpha, beta = fit_blend_weights(to_tuples(test, fit_ids), n_iter=300)
print(f"\nロジット結合係数: α(モデル)={alpha:.3f}, β(市場)={beta:.3f}")

eval_tuples = to_tuples(test, eval_ids)
print("平均対数尤度(評価期間、高いほど良い):")
print(f"  市場単体     : {log_likelihood(eval_tuples, 0.0, 1.0):+.4f}")
print(f"  モデル単体   : {log_likelihood(eval_tuples, 1.0, 0.0):+.4f}")
print(f"  結合(α,β)  : {log_likelihood(eval_tuples, alpha, beta):+.4f}")

# ---------- 4. 結合確率でEVフィルタ+1/4ケリーのバックテスト ----------
eval_df = test[test["race_id"].isin(eval_ids)].copy()
blended = []
for rid, g in eval_df.groupby("race_id", sort=False):
    blended.append(pd.Series(
        blend_probabilities(g["model_prob"], g["market_prob"], alpha, beta), index=g.index))
eval_df["prob"] = pd.concat(blended)
eval_df["odds"] = eval_df["win_odds_final"]

for min_ev, label in [(1.00, "EV>=1.00"), (1.05, "EV>=1.05")]:
    res = backtest_win_bets(eval_df, min_ev=min_ev, staking="kelly", kelly_fraction=0.25)
    print(f"\n[{label} / 1-4ケリー] 購入{res.n_bets}点 "
          f"回収率{res.roi:.3f} 最終資金{res.final_bankroll:.3f} "
          f"最大DD{res.max_drawdown:.1%}")

print("\n注: 合成市場は「市場がすでに賢い」設定のため、履歴特徴だけのモデルでは")
print("    市場を超える情報がほとんど無い。判断基準は対数尤度が第一:")
print("    評価期間で「結合 > 市場単体」を安定して満たさない限り、")
print("    バックテストの回収率が1を超えていてもサンプルノイズとみなして")
print("    賭けない(数百レース規模の回収率は偶然で±20%以上動く)。")
print("    これが docs/strategy.md の撤退基準①の実演である。")
