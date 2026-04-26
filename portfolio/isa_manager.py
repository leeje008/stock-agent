"""ISA account, monthly contribution, target allocation history CRUD."""
import json
from datetime import datetime

from db.database import get_connection
from db.models import IsaAccount, MonthlyContribution, TargetAllocationHistory


class IsaManager:
    # --- Account ---
    def upsert_account(self, account: IsaAccount) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO isa_accounts
                 (account_name, monthly_contribution, risk_level, start_date,
                  annual_limit, tax_status, note)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(account_name) DO UPDATE SET
                 monthly_contribution=excluded.monthly_contribution,
                 risk_level=excluded.risk_level,
                 start_date=excluded.start_date,
                 annual_limit=excluded.annual_limit,
                 tax_status=excluded.tax_status,
                 note=excluded.note""",
            (account.account_name, account.monthly_contribution, account.risk_level,
             account.start_date, account.annual_limit, account.tax_status, account.note),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM isa_accounts WHERE account_name=?", (account.account_name,)
        ).fetchone()
        conn.close()
        return row["id"]

    def get_account(self, account_id: int | None = None,
                    account_name: str | None = None) -> IsaAccount | None:
        conn = get_connection()
        if account_id is not None:
            row = conn.execute(
                "SELECT * FROM isa_accounts WHERE id=?", (account_id,)
            ).fetchone()
        elif account_name is not None:
            row = conn.execute(
                "SELECT * FROM isa_accounts WHERE account_name=?", (account_name,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM isa_accounts ORDER BY id LIMIT 1"
            ).fetchone()
        conn.close()
        if not row:
            return None
        return IsaAccount(
            id=row["id"], account_name=row["account_name"],
            monthly_contribution=row["monthly_contribution"],
            risk_level=row["risk_level"], start_date=row["start_date"],
            annual_limit=row["annual_limit"], tax_status=row["tax_status"],
            note=row["note"], created_at=row["created_at"],
        )

    def list_accounts(self) -> list[IsaAccount]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM isa_accounts ORDER BY id").fetchall()
        conn.close()
        return [
            IsaAccount(
                id=r["id"], account_name=r["account_name"],
                monthly_contribution=r["monthly_contribution"],
                risk_level=r["risk_level"], start_date=r["start_date"],
                annual_limit=r["annual_limit"], tax_status=r["tax_status"],
                note=r["note"], created_at=r["created_at"],
            )
            for r in rows
        ]

    # --- Monthly Contribution ---
    def record_contribution(self, contribution: MonthlyContribution) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO monthly_contributions (account_id, year_month, amount, note)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(account_id, year_month) DO UPDATE SET
                 amount=excluded.amount,
                 note=excluded.note""",
            (contribution.account_id, contribution.year_month,
             contribution.amount, contribution.note),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM monthly_contributions WHERE account_id=? AND year_month=?",
            (contribution.account_id, contribution.year_month),
        ).fetchone()
        conn.close()
        return row["id"]

    def get_contributions(self, account_id: int) -> list[MonthlyContribution]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM monthly_contributions WHERE account_id=? ORDER BY year_month",
            (account_id,),
        ).fetchall()
        conn.close()
        return [
            MonthlyContribution(
                id=r["id"], account_id=r["account_id"], year_month=r["year_month"],
                amount=r["amount"], note=r["note"], created_at=r["created_at"],
            )
            for r in rows
        ]

    def get_year_total(self, account_id: int, year: int) -> float:
        conn = get_connection()
        row = conn.execute(
            """SELECT COALESCE(SUM(amount), 0) AS total
               FROM monthly_contributions
               WHERE account_id=? AND year_month LIKE ?""",
            (account_id, f"{year}-%"),
        ).fetchone()
        conn.close()
        return float(row["total"])

    # --- Target Allocation History ---
    def record_target_allocation(self, target: TargetAllocationHistory) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO target_allocation_history
                 (account_id, set_date, weights_json, monthly_amount, strategy, reason)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (target.account_id, target.set_date, target.weights_json,
             target.monthly_amount, target.strategy, target.reason),
        )
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        return row_id

    def get_latest_target(self, account_id: int) -> TargetAllocationHistory | None:
        conn = get_connection()
        row = conn.execute(
            """SELECT * FROM target_allocation_history
               WHERE account_id=? ORDER BY set_date DESC, id DESC LIMIT 1""",
            (account_id,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return TargetAllocationHistory(
            id=row["id"], account_id=row["account_id"], set_date=row["set_date"],
            weights_json=row["weights_json"], monthly_amount=row["monthly_amount"],
            strategy=row["strategy"], reason=row["reason"], created_at=row["created_at"],
        )

    def get_target_history(self, account_id: int) -> list[TargetAllocationHistory]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM target_allocation_history WHERE account_id=? ORDER BY set_date, id",
            (account_id,),
        ).fetchall()
        conn.close()
        return [
            TargetAllocationHistory(
                id=r["id"], account_id=r["account_id"], set_date=r["set_date"],
                weights_json=r["weights_json"], monthly_amount=r["monthly_amount"],
                strategy=r["strategy"], reason=r["reason"], created_at=r["created_at"],
            )
            for r in rows
        ]


def get_or_create_default_account() -> IsaAccount:
    """앱 진입 시 사용할 기본 ISA 계좌를 보장."""
    mgr = IsaManager()
    account = mgr.get_account()
    if account is not None:
        return account
    default = IsaAccount(
        account_name="기본 ISA",
        monthly_contribution=1_000_000,
        risk_level="중립",
        start_date=datetime.today().strftime("%Y-%m-%d"),
    )
    account_id = mgr.upsert_account(default)
    return mgr.get_account(account_id=account_id)
