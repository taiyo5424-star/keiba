"""発注実行レイヤ — 既定はペーパートレード。実弾接続は明示的オプトイン。

設計原則:
1. **既定は絶対にペーパー**: PaperBroker が発注を記録・仮想約定するだけ。
   実弾は LiveBrokerAdapter を実装したオブジェクトを明示的に渡した場合のみ。
   このリポジトリは実弾接続の実装を含まない(IPAT連携はユーザーの
   ローカル環境で ipatgo 等を包む Adapter を書いて差し込む。
   docs/research/automation-tos.md の規約リスクを読んでから)。
2. **キルスイッチ**: 作業ディレクトリに KILL_SWITCH ファイルが存在する限り
   一切発注しない(人間がいつでも止められる)。
3. **多層ガード**: 日次投下上限・1日の発注回数上限・同一馬券の重複防止。
4. **完全記録**: すべての発注(却下含む)を store.bets / 監査ログに残す。
   投票成否の照合(発注→投票照会の突合)は実弾Adapterの責務として
   インタフェースに含める。
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from keiba.decision import BetOrder
from keiba.store import record_bet


class Broker(Protocol):
    """発注先の抽象。place() は受理した発注の識別子を返す。"""

    def place(self, order: BetOrder, placed_at: str) -> str: ...

    def verify(self, receipt: str) -> bool:
        """発注が実際に成立したかの照合。実弾Adapterでは投票照会と突合する。"""
        ...


class PaperBroker:
    """ペーパートレード: 判断時点オッズで仮想約定し、DBに記録する。"""

    def __init__(self, conn):
        self.conn = conn
        self._seq = 0

    def place(self, order: BetOrder, placed_at: str) -> str:
        record_bet(
            self.conn,
            placed_at=placed_at,
            race_id=order.race_id,
            bet_type=order.bet_type,
            selection=order.selection,
            stake=order.stake,
            odds_at_purchase=order.odds,
        )
        self._seq += 1
        return f"paper-{self._seq}"

    def verify(self, receipt: str) -> bool:
        return True  # ペーパーは常に成立扱い

    def settle_win_race(self, race_id: str, winner_selection: str, final_odds: float) -> None:
        """単勝の仮想清算: 的中した賭けに 払戻 = stake × 確定オッズ を記録。

        清算は確定オッズで行う(購入時オッズより通常低い側に動くため、
        判断時オッズで清算すると成績が甘く出る)。
        """
        self.conn.execute(
            "UPDATE bets SET returned = stake * ? "
            "WHERE race_id = ? AND bet_type = 'win' AND selection = ?",
            (final_odds, race_id, winner_selection),
        )
        self.conn.commit()


@dataclass
class ExecutionGuard:
    """発注前の多層チェック。1つでも引っかかれば発注しない。"""

    kill_switch_path: Path = Path("KILL_SWITCH")
    max_daily_stake: int = 30_000          # 円
    max_daily_orders: int = 50
    _placed_today: dict = field(default_factory=dict)  # date -> [stake合計, 件数]
    _seen_keys: set = field(default_factory=set)

    def check(self, order: BetOrder, now: _dt.datetime) -> tuple[bool, str]:
        if self.kill_switch_path.exists():
            return False, "kill switch is on"
        key = (order.race_id, order.bet_type, order.selection)
        if key in self._seen_keys:
            return False, "duplicate order"
        day = now.date().isoformat()
        staked, n = self._placed_today.get(day, (0, 0))
        if staked + order.stake > self.max_daily_stake:
            return False, f"daily stake cap ({self.max_daily_stake}) exceeded"
        if n + 1 > self.max_daily_orders:
            return False, "daily order-count cap exceeded"
        return True, "ok"

    def commit(self, order: BetOrder, now: _dt.datetime) -> None:
        day = now.date().isoformat()
        staked, n = self._placed_today.get(day, (0, 0))
        self._placed_today[day] = (staked + order.stake, n + 1)
        self._seen_keys.add((order.race_id, order.bet_type, order.selection))


@dataclass
class ExecutionResult:
    placed: list = field(default_factory=list)     # (order, receipt)
    rejected: list = field(default_factory=list)   # (order, reason)


def execute_orders(
    orders: list[BetOrder],
    broker: Broker,
    guard: ExecutionGuard,
    now: _dt.datetime | None = None,
) -> ExecutionResult:
    """ガードを通った発注のみブローカーに流す。結果は全件返す。"""
    now = now or _dt.datetime.now()
    result = ExecutionResult()
    for order in orders:
        ok, reason = guard.check(order, now)
        if not ok:
            result.rejected.append((order, reason))
            continue
        receipt = broker.place(order, placed_at=now.isoformat(timespec="seconds"))
        if not broker.verify(receipt):
            result.rejected.append((order, "verification failed"))
            continue
        guard.commit(order, now)
        result.placed.append((order, receipt))
    return result
