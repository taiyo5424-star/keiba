# -*- coding: utf-8 -*-
"""JRA-VAN DataLab (JV-Link) 生データダンプ — Windows専用。

あなたのWindows PCで実行し、JV-Linkから蓄積データを取得して
リポジトリの data/jvraw/ にレコード種別ごとのテキストで保存する。
保存後に git commit & push すれば、クラウド側(Claude)がパーサを書いて
分析パイプラインに統合する、という分業のためのスクリプト。

前提(Windowsでの1回だけの準備):
  1. JRA-VAN DataLab. 会員契約(済み)
  2. JV-Link のインストール: https://jra-van.jp/dlb/ からSDK/JV-Link
  3. 初回のみ JV-Link 設定で利用キーを登録(スタートメニューのJV-Link設定)
  4. pip install pywin32

実行例(PowerShell / コマンドプロンプト):
  python scripts\\jvlink_dump.py --dataspec RACE --from 20260101000000
  python scripts\\jvlink_dump.py --dataspec RACE --from 20240101000000 --option 4
     (option 4 = セットアップデータ: 過去分全量。初回はこれ)

dataspec の例(JV-Data仕様書参照):
  RACE : レース詳細(RA)・馬毎レース情報(SE)・払戻(HR)等
  DIFF : 馬・騎手・調教師等のマスタ
  BLOD : 血統
  YSCH : 開催スケジュール
  SNAP : 調教(ウッド・坂路)     ※契約プランにより取得可否が異なる

注意:
- 取得データはJRA-VAN利用規約に基づく個人利用の範囲で扱うこと。
  リポジトリをprivateに保ち、生データを再配布しない。
- このスクリプトはWindows+JV-Link環境でのみ動作する(クラウド側では
  実行不可のため未テスト。エラーが出たらメッセージを添えて相談)。
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataspec", default="RACE")
    ap.add_argument("--from", dest="fromtime", required=True,
                    help="YYYYMMDDhhmmss(この時刻以降の更新分を取得)")
    ap.add_argument("--option", type=int, default=1,
                    help="1=通常(差分) 2=今週 3=セットアップ(ダイアログ) 4=セットアップ(全量)")
    ap.add_argument("--out", default="data/jvraw")
    ap.add_argument("--sid", default="KEIBA-EV",
                    help="JVInitに渡すソフトウェアID(任意の識別子)")
    args = ap.parse_args()

    try:
        import win32com.client  # type: ignore
    except ImportError:
        print("pywin32 が必要です: pip install pywin32", file=sys.stderr)
        return 2

    jv = win32com.client.Dispatch("JVDTLab.JVLink")

    ret = jv.JVInit(args.sid)
    if ret != 0:
        print(f"JVInit 失敗: code={ret}(JV-Link設定で利用キー登録を確認)",
              file=sys.stderr)
        return 1

    # JVOpen は環境により戻り値がタプル(ret, readcount, downloadcount, ts)の
    # 場合と整数のみの場合がある(makepy生成の有無)。両対応にする。
    res = jv.JVOpen(args.dataspec, args.fromtime, args.option)
    if isinstance(res, tuple):
        ret, read_count = res[0], (res[1] if len(res) > 1 else -1)
    else:
        ret, read_count = res, -1
    if ret != 0:
        print(f"JVOpen 失敗: code={ret}(dataspec/期間/契約プランを確認。"
              f"-1xx系はパラメータ、-2xx系はダウンロード関連)", file=sys.stderr)
        return 1
    print(f"JVOpen OK: dataspec={args.dataspec} 想定読込数={read_count}")

    out_dir = Path(args.out) / args.dataspec
    out_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, object] = {}
    counts: Counter = Counter()
    buf_size = 110000  # JV-Data最大レコード長より大きく

    try:
        while True:
            res = jv.JVRead("", buf_size, "")
            # 戻り値: (ret, buff, size, filename) 形式(makepy有無で揺れに対応)
            if isinstance(res, tuple):
                rc = res[0]
                buff = res[1] if len(res) > 1 else ""
            else:
                rc, buff = res, ""
            if rc == 0:
                break          # 全件終了
            if rc == -1:
                continue       # ファイル切替
            if rc < -1:
                print(f"JVRead エラー: code={rc}", file=sys.stderr)
                break
            record = str(buff)
            rectype = record[:2]
            if rectype not in files:
                files[rectype] = (out_dir / f"{rectype}.txt").open(
                    "a", encoding="utf-8", newline="\n"
                )
            files[rectype].write(record.rstrip("\r\n") + "\n")
            counts[rectype] += 1
            total = sum(counts.values())
            if total % 5000 == 0:
                print(f"  {total}件... {dict(counts)}", flush=True)
    finally:
        for f in files.values():
            f.close()
        jv.JVClose()

    print(f"完了: {dict(counts)} → {out_dir}/")
    print("次の手順: git add data/jvraw && git commit && git push で"
          "クラウド側に共有してください(パーサ実装はClaudeが行います)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
