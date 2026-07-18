# 地方競馬データ契約

地方競馬の取り込み層は、取得元ごとの差を `data/nar_exports/` のCSVに正規化します。モデル、バックテスト、期待値計算は取得元を直接読みません。

## `data/nar_exports/races.csv`

- `race_id`: 安定したレースキー。例: `20260615_ooi_01`
- `race_date`: ISO日付
- `venue`: 競馬場
- `race_no`: レース番号
- `surface`: `dirt` など
- `distance`: メートル
- `going`: 馬場状態
- `field_size`: 出走頭数
- `post_time`: 発走予定時刻
- `available_at`: この行が予測に使えるようになった時刻

## `data/nar_exports/starts.csv`

1頭1行です。予測時刻で入手できる情報だけを入れます。

- `race_id`
- `horse_no`
- `horse_id`
- `horse_name`
- `jockey_name`
- `trainer_name`
- `post_position`
- `carried_weight`
- `horse_weight`
- `weight_diff`
- `sex_age`
- `available_at`

## `data/nar_exports/odds_snapshots.csv`

オッズ観測1件につき1行です。バックテストでは、実運用で購入判断に使う時刻以前のオッズだけを使います。

- `race_id`
- `bet_type`: まずは `win` と `place`
- `selection`: 馬名または買い目
- `horse_no`
- `odds`
- `popularity`
- `source`
- `observed_at`
- `is_final`: 確定オッズなら `true`、購入判断前なら `false`

## `data/nar_exports/results.csv`

確定後にだけ入れる行です。学習ラベルと精算に使います。

- `race_id`
- `horse_no`
- `finish_position`
- `payout_win`
- `payout_place`

## 時刻ルール

- 特徴量には `available_at <= prediction_time` の情報だけを使います。
- オッズは `observed_at <= purchase_time` のものだけを使います。
- `is_final=true` のオッズは、CLV計算と精算用であり、購入判断には使いません。

