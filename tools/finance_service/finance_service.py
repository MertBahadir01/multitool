"""
finance_service.py — shared data layer for all finance tools.
Place at: tools/finance_service/finance_service.py
All other finance tools import from here.

API used:
  Exchange rates : https://api.exchangerate-api.com/v4/latest/TRY  (free, no key)
  Crypto prices  : https://api.coingecko.com/api/v3/simple/price   (free, no key)
  Stock prices   : https://query1.finance.yahoo.com/v8/finance/chart/<TICKER> (free)
"""

import datetime
import threading
import requests
from database.database import get_connection


# ── helpers ───────────────────────────────────────────────────────────────────
def _today() -> str:
    return datetime.date.today().isoformat()

def _now() -> str:
    return datetime.datetime.now().isoformat()


# ── Transactions (Expense / Income) ──────────────────────────────────────────
class TransactionService:
    def __init__(self, user_id: int):
        self.uid = user_id

    def add(self, amount: float, category: str, note: str = "",
            tx_type: str = "expense", tx_date: str = "") -> int:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO fin_transactions (user_id,amount,category,note,tx_type,tx_date) "
            "VALUES (?,?,?,?,?,?)",
            (self.uid, amount, category, note, tx_type, tx_date or _today())
        )
        conn.commit(); rid = cur.lastrowid; conn.close()
        return rid

    def get_all(self, tx_type: str = None, category: str = None,
                from_date: str = "", to_date: str = "") -> list:
        conn = get_connection()
        q = "SELECT * FROM fin_transactions WHERE user_id=?"
        p: list = [self.uid]
        if tx_type:   q += " AND tx_type=?";   p.append(tx_type)
        if category:  q += " AND category=?";  p.append(category)
        if from_date: q += " AND tx_date>=?";  p.append(from_date)
        if to_date:   q += " AND tx_date<=?";  p.append(to_date)
        q += " ORDER BY tx_date DESC"
        rows = conn.execute(q, p).fetchall(); conn.close()
        return [dict(r) for r in rows]

    def delete(self, tx_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM fin_transactions WHERE id=? AND user_id=?", (tx_id, self.uid))
        conn.commit(); conn.close()

    def totals_by_category(self, tx_type="expense", from_date="", to_date="") -> dict:
        conn = get_connection()
        q = "SELECT category, SUM(amount) FROM fin_transactions WHERE user_id=? AND tx_type=?"
        p: list = [self.uid, tx_type]
        if from_date: q += " AND tx_date>=?"; p.append(from_date)
        if to_date:   q += " AND tx_date<=?"; p.append(to_date)
        q += " GROUP BY category"
        rows = conn.execute(q, p).fetchall(); conn.close()
        return {r[0]: r[1] for r in rows}

    def monthly_totals(self, tx_type="expense") -> list:
        conn = get_connection()
        rows = conn.execute(
            "SELECT strftime('%Y-%m', tx_date) as month, SUM(amount) "
            "FROM fin_transactions WHERE user_id=? AND tx_type=? "
            "GROUP BY month ORDER BY month",
            (self.uid, tx_type)
        ).fetchall(); conn.close()
        return [{"month": r[0], "total": r[1]} for r in rows]


# ── Budgets ───────────────────────────────────────────────────────────────────
class BudgetService:
    def __init__(self, user_id: int):
        self.uid = user_id

    def set_budget(self, category: str, amount: float, period: str = "monthly"):
        conn = get_connection()
        conn.execute(
            "INSERT INTO fin_budgets (user_id,category,amount,period) VALUES (?,?,?,?) "
            "ON CONFLICT(user_id,category) DO UPDATE SET amount=excluded.amount,period=excluded.period",
            (self.uid, category, amount, period)
        )
        conn.commit(); conn.close()

    def get_budgets(self) -> list:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM fin_budgets WHERE user_id=? ORDER BY category",
            (self.uid,)
        ).fetchall(); conn.close()
        return [dict(r) for r in rows]

    def delete_budget(self, budget_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM fin_budgets WHERE id=? AND user_id=?", (budget_id, self.uid))
        conn.commit(); conn.close()


# ── Savings Goals ─────────────────────────────────────────────────────────────
class SavingsService:
    def __init__(self, user_id: int):
        self.uid = user_id

    def add_goal(self, name: str, target: float, saved: float = 0,
                 deadline: str = "", monthly_add: float = 0) -> int:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO fin_savings (user_id,name,target,saved,deadline,monthly_add) "
            "VALUES (?,?,?,?,?,?)",
            (self.uid, name, target, saved, deadline, monthly_add)
        )
        conn.commit(); rid = cur.lastrowid; conn.close()
        return rid

    def update_saved(self, goal_id: int, saved: float):
        conn = get_connection()
        conn.execute(
            "UPDATE fin_savings SET saved=? WHERE id=? AND user_id=?",
            (saved, goal_id, self.uid)
        )
        conn.commit(); conn.close()

    def get_goals(self) -> list:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM fin_savings WHERE user_id=? ORDER BY name",
            (self.uid,)
        ).fetchall(); conn.close()
        return [dict(r) for r in rows]

    def delete_goal(self, goal_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM fin_savings WHERE id=? AND user_id=?", (goal_id, self.uid))
        conn.commit(); conn.close()


# ── Assets / Portfolio ────────────────────────────────────────────────────────
class PortfolioService:
    def __init__(self, user_id: int):
        self.uid = user_id

    def add_asset(self, symbol: str, name: str, qty: float,
                  buy_price: float, asset_type: str = "stock") -> int:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO fin_assets (user_id,symbol,name,quantity,buy_price,asset_type) "
            "VALUES (?,?,?,?,?,?)",
            (self.uid, symbol.upper(), name, qty, buy_price, asset_type)
        )
        conn.commit(); rid = cur.lastrowid; conn.close()
        return rid

    def get_assets(self, asset_type: str = None) -> list:
        conn = get_connection()
        if asset_type:
            rows = conn.execute(
                "SELECT * FROM fin_assets WHERE user_id=? AND asset_type=? ORDER BY symbol",
                (self.uid, asset_type)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM fin_assets WHERE user_id=? ORDER BY symbol",
                (self.uid,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def delete_asset(self, asset_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM fin_assets WHERE id=? AND user_id=?", (asset_id, self.uid))
        conn.commit(); conn.close()


# ── Subscriptions ─────────────────────────────────────────────────────────────
class SubscriptionService:
    def __init__(self, user_id: int):
        self.uid = user_id

    def add(self, name: str, amount: float, currency: str = "TRY",
            billing_cycle: str = "monthly", next_due: str = "") -> int:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO fin_subscriptions (user_id,name,amount,currency,billing_cycle,next_due) "
            "VALUES (?,?,?,?,?,?)",
            (self.uid, name, amount, currency, billing_cycle, next_due or _today())
        )
        conn.commit(); rid = cur.lastrowid; conn.close()
        return rid

    def get_all(self) -> list:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM fin_subscriptions WHERE user_id=? ORDER BY next_due",
            (self.uid,)
        ).fetchall(); conn.close()
        return [dict(r) for r in rows]

    def delete(self, sub_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM fin_subscriptions WHERE id=? AND user_id=?", (sub_id, self.uid))
        conn.commit(); conn.close()

    def monthly_cost(self) -> float:
        subs = self.get_all()
        total = 0.0
        for s in subs:
            if s["billing_cycle"] == "monthly":   total += s["amount"]
            elif s["billing_cycle"] == "yearly":  total += s["amount"] / 12
            elif s["billing_cycle"] == "weekly":  total += s["amount"] * 4.33
        return round(total, 2)


# ── Debts / Loans ─────────────────────────────────────────────────────────────
class DebtService:
    def __init__(self, user_id: int):
        self.uid = user_id

    def add(self, name: str, principal: float, interest_rate: float,
            remaining: float, monthly_payment: float, start_date: str = "") -> int:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO fin_debts (user_id,name,principal,interest_rate,remaining,monthly_payment,start_date) "
            "VALUES (?,?,?,?,?,?,?)",
            (self.uid, name, principal, interest_rate, remaining, monthly_payment, start_date or _today())
        )
        conn.commit(); rid = cur.lastrowid; conn.close()
        return rid

    def get_all(self) -> list:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM fin_debts WHERE user_id=? ORDER BY name",
            (self.uid,)
        ).fetchall(); conn.close()
        return [dict(r) for r in rows]

    def update_remaining(self, debt_id: int, remaining: float):
        conn = get_connection()
        conn.execute(
            "UPDATE fin_debts SET remaining=? WHERE id=? AND user_id=?",
            (remaining, debt_id, self.uid)
        )
        conn.commit(); conn.close()

    def delete(self, debt_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM fin_debts WHERE id=? AND user_id=?", (debt_id, self.uid))
        conn.commit(); conn.close()


# ── Net Worth ─────────────────────────────────────────────────────────────────
class NetWorthService:
    def __init__(self, user_id: int):
        self.uid = user_id

    def add_item(self, name: str, value: float, item_type: str) -> int:
        """item_type: 'asset' or 'liability'"""
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO fin_net_worth (user_id,name,value,item_type,updated_at) VALUES (?,?,?,?,?)",
            (self.uid, name, value, item_type, _today())
        )
        conn.commit(); rid = cur.lastrowid; conn.close()
        return rid

    def get_all(self) -> list:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM fin_net_worth WHERE user_id=? ORDER BY item_type,name",
            (self.uid,)
        ).fetchall(); conn.close()
        return [dict(r) for r in rows]

    def update_value(self, item_id: int, value: float):
        conn = get_connection()
        conn.execute(
            "UPDATE fin_net_worth SET value=?,updated_at=? WHERE id=? AND user_id=?",
            (value, _today(), item_id, self.uid)
        )
        conn.commit(); conn.close()

    def delete(self, item_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM fin_net_worth WHERE id=? AND user_id=?", (item_id, self.uid))
        conn.commit(); conn.close()

    def snapshot(self) -> dict:
        items = self.get_all()
        assets = sum(i["value"] for i in items if i["item_type"] == "asset")
        liabs  = sum(i["value"] for i in items if i["item_type"] == "liability")
        return {"assets": assets, "liabilities": liabs, "net_worth": assets - liabs}


# ── Bill Reminders ────────────────────────────────────────────────────────────
class BillService:
    def __init__(self, user_id: int):
        self.uid = user_id

    def add(self, name: str, amount: float, due_date: str,
            recurring: bool = False, note: str = "") -> int:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO fin_bills (user_id,name,amount,due_date,recurring,note,paid) "
            "VALUES (?,?,?,?,?,?,0)",
            (self.uid, name, amount, due_date, 1 if recurring else 0, note)
        )
        conn.commit(); rid = cur.lastrowid; conn.close()
        return rid

    def get_all(self) -> list:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM fin_bills WHERE user_id=? ORDER BY due_date",
            (self.uid,)
        ).fetchall(); conn.close()
        return [dict(r) for r in rows]

    def set_paid(self, bill_id: int, paid: bool):
        conn = get_connection()
        conn.execute(
            "UPDATE fin_bills SET paid=? WHERE id=? AND user_id=?",
            (1 if paid else 0, bill_id, self.uid)
        )
        conn.commit(); conn.close()

    def delete(self, bill_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM fin_bills WHERE id=? AND user_id=?", (bill_id, self.uid))
        conn.commit(); conn.close()


# ── API helpers ───────────────────────────────────────────────────────────────
def fetch_exchange_rates(base: str = "TRY") -> dict:
    """Returns {currency: rate_vs_base}. Runs in a thread to avoid blocking UI."""
    try:
        r = requests.get(
            f"https://api.exchangerate-api.com/v4/latest/{base}", timeout=8)
        if r.ok:
            return r.json().get("rates", {})
    except Exception:
        pass
    # Fallback static rates vs TRY
    return {"USD": 0.031, "EUR": 0.029, "GBP": 0.025, "JPY": 4.6,
            "TRY": 1.0, "CHF": 0.028, "CAD": 0.042, "AUD": 0.047}


def fetch_crypto_prices(coins: list = None) -> dict:
    """Returns {coin_id: price_in_usd}"""
    ids = ",".join(coins or ["bitcoin","ethereum","solana","ripple","dogecoin"])
    try:
        r = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price"
            f"?ids={ids}&vs_currencies=usd,try", timeout=8)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return {}


def fetch_stock_price(symbol: str) -> dict:
    """Returns {price, change, change_pct, currency} or empty dict on error."""
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            "?interval=1d&range=1d", timeout=8,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if r.ok:
            data = r.json()
            meta = data["chart"]["result"][0]["meta"]
            return {
                "price":      meta.get("regularMarketPrice", 0),
                "prev_close": meta.get("previousClose",       0),
                "currency":   meta.get("currency", "USD"),
            }
    except Exception:
        pass
    return {}


def fetch_stock_history(symbol: str, period: str = "1mo") -> list:
    """Returns list of {date, close} dicts."""
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            f"?interval=1d&range={period}",
            timeout=10, headers={"User-Agent": "Mozilla/5.0"}
        )
        if r.ok:
            data   = r.json()
            result = data["chart"]["result"][0]
            timestamps = result["timestamp"]
            closes     = result["indicators"]["quote"][0]["close"]
            out = []
            for ts, c in zip(timestamps, closes):
                if c is not None:
                    date = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                    out.append({"date": date, "close": round(c, 4)})
            return out
    except Exception:
        pass
    return []


def fetch_crypto_history(coin_id: str = "bitcoin", days: int = 30) -> list:
    """Returns list of {date, price}"""
    try:
        r = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
            f"?vs_currency=usd&days={days}", timeout=10)
        if r.ok:
            prices = r.json().get("prices", [])
            return [
                {"date": datetime.datetime.fromtimestamp(p[0]/1000).strftime("%Y-%m-%d"),
                 "price": round(p[1], 4)}
                for p in prices
            ]
    except Exception:
        pass
    return []


# ── Calculation helpers (pure, no DB) ────────────────────────────────────────
def loan_monthly_payment(principal: float, annual_rate: float, months: int) -> float:
    if annual_rate == 0:
        return principal / months
    r = annual_rate / 100 / 12
    return principal * r * (1 + r)**months / ((1 + r)**months - 1)


def loan_schedule(principal: float, annual_rate: float, months: int) -> list:
    pmt = loan_monthly_payment(principal, annual_rate, months)
    r   = annual_rate / 100 / 12
    balance = principal
    rows = []
    for m in range(1, months + 1):
        interest = balance * r
        principal_part = pmt - interest
        balance -= principal_part
        rows.append({
            "month": m, "payment": round(pmt, 2),
            "interest": round(interest, 2),
            "principal": round(principal_part, 2),
            "balance": round(max(balance, 0), 2)
        })
    return rows


def future_value(present: float, annual_rate: float, years: int,
                 monthly_contrib: float = 0) -> float:
    r = annual_rate / 100 / 12
    n = years * 12
    if r == 0:
        return present + monthly_contrib * n
    fv_lump = present * (1 + r)**n
    fv_annuity = monthly_contrib * ((1 + r)**n - 1) / r
    return round(fv_lump + fv_annuity, 2)


def tr_income_tax(income: float) -> dict:
    """Turkish 2024 income tax brackets (annual TRY)."""
    brackets = [
        (110_000,   0.15),
        (230_000,   0.20),
        (870_000,   0.27),
        (3_000_000, 0.35),
        (float("inf"), 0.40),
    ]
    tax = 0.0
    prev = 0.0
    detail = []
    for limit, rate in brackets:
        if income <= prev:
            break
        taxable = min(income, limit) - prev
        t = taxable * rate
        tax += t
        detail.append({"bracket": f"{prev:,.0f}–{limit:,.0f}", "rate": rate, "tax": round(t, 2)})
        prev = limit
    return {"gross": income, "tax": round(tax, 2), "net": round(income - tax, 2), "detail": detail}
