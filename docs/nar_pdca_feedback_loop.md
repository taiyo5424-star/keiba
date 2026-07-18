# 地方競馬 期待値分析 PDCA

目的は、各レース後に得られる結果・展開・馬場状態・映像/テキスト所見を、同日以降のレース予測へ即時反映すること。

## 基本方針

1. レース前は、公式出馬表または投票画面でラインナップを照合する。
2. レース後は、結果、通過順、上がり、馬場、勝ち時計、払戻、映像所見を記録する。
3. 同一競馬場・同一開催日の後続レースには、直近レースから推定したバイアスを補正として入れる。
4. 補正は過信しない。サンプルが少ない間は `low confidence` とし、推奨金額を抑える。
5. 予想通知では、使った当日バイアスを短く明記する。

## レース後に記録する項目

`data/nar_feedback/race_reviews.csv`

- `race_id`
- `race_date`
- `venue`
- `race_no`
- `post_time`
- `surface`
- `distance`
- `going`
- `winner_no`
- `winner_name`
- `winner_odds`
- `win_payout`
- `pace_note`: slow / average / fast / unknown
- `position_bias`: front / stalker / midpack / closer / none / unknown
- `rail_bias`: inside / outside / none / unknown
- `track_speed`: fast / normal / slow / unknown
- `video_note`: 映像からの短い観察
- `text_note`: 公式短評、専門紙、実況、結果コメント等からの短い要約
- `reviewed_at`

`data/nar_feedback/bias_context.csv`

- `race_date`
- `venue`
- `updated_after_race_no`
- `sample_size`
- `front_score`
- `closer_score`
- `inside_score`
- `outside_score`
- `speed_score`
- `bias_summary`
- `confidence`
- `updated_at`

## 後続レースへの反映ルール

同日同場で、直近2から4レースを中心に見る。

- 前残り: 逃げ・先行が連続して残る、差しが届かない、内前が有利。
  - 先行力のある馬を上方補正。
  - 出遅れ癖、追込一辺倒は下方補正。
- 差し有利: ハイペースや外差しが連続して決まる。
  - 差し脚のある馬、外枠で揉まれにくい馬を上方補正。
  - 短距離の内先行人気馬を過剰人気として警戒。
- 内有利: 内枠やラチ沿いが伸びる。
  - 内枠、ロスなく運べる馬を上方補正。
  - 外枠で先行できない馬は下方補正。
- 外有利: 内が重い、外差しが伸びる。
  - 外目から運ぶ差し馬を上方補正。
  - 内で包まれやすい人気馬を下方補正。
- 高速馬場: 時計が速い。
  - 持ち時計、スピード指数、短縮組を上方補正。
- タフ馬場: 時計がかかる。
  - パワー型、距離延長耐性、上がりがかかっても崩れない馬を上方補正。

## 補正の上限

当日バイアスだけで推定勝率を大きく変えない。

- confidence low: 勝率補正は最大 +/- 2pt
- confidence medium: 最大 +/- 4pt
- confidence high: 最大 +/- 6pt

初期値は必ず `low`。3レース以上で同方向の傾向が出たら `medium`、5レース以上で明確なら `high`。

## 動画・テキストの扱い

動画は、以下だけを特徴量化する。

- スタート: 出遅れ、二の脚、押して行けたか
- 道中: 砂を被った反応、折り合い、ポジション争い
- 直線: 内外の伸び、脚色、詰まり、不利
- ゴール後: 余力、止まり方

テキストは、以下を短く要約する。

- 公式結果、払戻、通過順
- 専門紙/記者コメント
- 実況やレース後コメント
- ユーザー提供の新聞・スクショ

著作権のある本文は長く保存せず、特徴量・要約だけを保存する。

## 通知フォーマット

今後のBUY通知には、先頭に結論を出す。

`BUY: 川崎5R 16:45 / 単勝6 フェアーメロディ / 100円`

続けて、必要なら以下を入れる。

- `ラインナップ照合済み`
- `当日バイアス: 川崎は内前やや有利、confidence low`
- `EV: 推定勝率16%、単勝7.1倍、EV +14%`
- `根拠: 同条件2着、先行力、馬場補正`

BUYなしの場合:

`BUYなし: 園田12R / 見送り / 人気馬のオッズ不足`

## 運用順序

1. 締切10分前: 出馬表・オッズ・変更情報を照合。
2. 予想: 直近の `bias_context.csv` を確認して確率を補正。
3. 通知: BUY/PASSを明示。
4. レース後: 結果と映像/テキスト所見を `race_reviews.csv` に追加。
5. 更新: `src/update_nar_bias_context.py` で `bias_context.csv` を更新。
6. 次レース: 更新済みバイアスを参照して再評価。
