# 投票システムの自動化・データ取得 — 規約と実態

調査日: 2026-07-18。JRA約定は一次資料PDF/HTMLを直接取得して確認。

## 1. JRA(即PAT / A-PAT / JRAダイレクト)

- **自動投票プログラム・bot・スクレイピングを名指しで禁止する条項は存在しない**
  (即PAT約定第27条ほか、3約定すべての原文確認)。
- 禁止されているのは: 他人委託による投票(代行)、商業目的利用、システムへの妨害・混乱、
  「その他競馬会が不適切と認めた行為」(包括条項)等。
  出典: [即PAT約定PDF](https://www.jra.go.jp/dento/soku/pdf/yakujo_soku.pdf)
- **連携ソフトは「禁止」ではなく「無保証」**: 「他のサイト、アプリケーション等を連携させて
  投票された場合、投票の成否および投票内容は一切保証いたしません」
  ([即PAT禁止・注意事項](https://www.jra.go.jp/dento/soku/instructions/kinshi.html)、
  [JRAお知らせ2019/12/20](https://www.jra.go.jp/dento/info/2019/122001.html))。
- **JRA-VAN公式サイト自身がIPAT連携の自動投票ソフト(例: KSC自動投票Plus)を
  DataLab.対応ソフトとして掲載**しており、連携投票ソフトは事実上容認されたエコシステム。
  出典: [KSC自動投票Plus(JRA-VAN公式)](https://jra-van.jp/dlb/sft/lib/kscjidou.html)
- 即PAT約定第28条: IPATで取得した情報(オッズ等)の複製・転載には事前承諾が必要(知財条項)。
- 既存ツール: [ipatgo](https://ipat-docs.readthedocs.io/ja/latest/summary.html)(全券種対応、
  JV-Link+IPAT会員必須、Windows専用)、[ipathelper](https://pypi.org/project/ipathelper/)(Python、
  地方も対応)、Selenium/Playwright自作例多数。
- **リスク**: 投票成否の無保証、包括条項による解約possibility、過度なアクセスは妨害行為に該当しうる。
  投票代行・商業利用は明確に違反。

## 2. 地方競馬(SPAT4 / オッズパーク / 楽天競馬)

- 3社とも**自動投票の名指し禁止は確認できず**。共通する禁止は: 有害プログラム送信、
  システム妨害、商業目的利用、本人以外の利用、事業者裁量の包括条項。
  出典: [オッズパーク投票会員規約PDF](https://www.oddspark.com/pdf/kiyaku_shicyu.pdf)、
  [楽天競馬 投票規約](https://keiba.rakuten.co.jp/guide/term01)、
  [SPAT4アプリ利用規約](https://spat4-apps.com/terms/index.html)
- 楽天はグループ共通規約で「ロボット等の自動化された手段」によるアクセスを事前許諾なく
  禁止しているとの解説あり(楽天競馬固有の投票規約には明記なし)。
- SPAT4本体の加入者約定原文は未確認。

## 3. 公式データの取得手段

| ソース | 内容 | 料金 | 制約 |
|---|---|---|---|
| **JRA-VAN DataLab.**(JV-Link) | 蓄積系(成績・血統・調教)+リアルタイム系(速報オッズ・馬体重・払戻) | 月額2,090円 | ActiveX COM、**Windows専用** |
| **地方競馬DATA**(UmaConn) | 全地方の出走表・成績・オッズ(2005年〜、オッズは2010年2月〜) | 月額約2,640〜2,970円(要公式確認) | Windows前提 |
| [地方競馬情報サイト データ室](https://www.keiba.go.jp/KeibaWeb/DataRoom/DataRoomTop) | 無料の公式データ | 無料 | 粒度粗い |

- **速報オッズの更新間隔**(JRA-VAN公式FAQ): 最短10秒(1レースのみ発売時)〜
  3場開催時は当該レース120秒、他レース610〜710秒。時系列オッズデータも提供。
  出典: [JRA-VANヘルプ](https://support.jra-van.jp/jravan/detail?site=SVKNEGBV&category=16&id=227)
- **netkeibaスクレイピング**: 公式FAQが「サービスに支障があると判断した場合、予告なく通信制限、
  解除依頼にも応じない」と明記。支障を生じさせるスクレイピングは規約の禁止事項に該当。
  出典: [netkeibaサポートFAQ](https://support.keiba.netkeiba.com/hc/ja/articles/39720493823129)

## 4. 大量購入の実例

- **UPRO事件(2009)**: 予想プログラムで3年間に約160億円の払戻所得を隠し国税が摘発
  (追徴約60億円)。JRAが発売拒否した報道は無し。
  出典: [J-CAST](https://www.j-cast.com/2009/10/09051436.html?p=all)
- **外れ馬券裁判(大阪)**: 自動購入ソフトでPAT経由3年間28.7億円の網羅的購入が司法の場で
  公認された(購入自体をJRAが止めた形跡なし)。
- 自動投票を理由にJRAがPAT口座を停止した公表事例は**未確認**。

## 5. 実務方針(推奨)

1. データ取得は**公式有料データ(JRA-VAN / 地方競馬DATA)を第一選択**にする
   (規約リスク・データ品質・オッズ更新頻度の全てで優位)。
2. スクレイピングを併用する場合はアクセス間隔を大きく取り、妨害と見なされない範囲に留める。
3. 投票自動化は既存エコシステム(JV-Link連携ソフト等)の形態に寄せ、
   投票成否の検証(投票照会との突合)を必ず実装する。無保証を前提に冪等設計にする。
4. 投票代行・第三者への予想販売と組み合わせない(商業目的利用の明確な違反になりうる)。
