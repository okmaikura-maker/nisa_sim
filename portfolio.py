"""
NISAペーパートレード・ポートフォリオ管理。
実際のお金は一切動かさない。すべて仮想資金での記録。
"""
import json
import os
from datetime import datetime

STATE_PATH = os.path.join(os.path.dirname(__file__), "state", "portfolio.json")
INITIAL_CASH = 1_800_000  # NISA成長投資枠の年間上限を目安にした仮想初期資金(円)


def _default_state():
    return {
        "cash": INITIAL_CASH,
        "holdings": {},  # ticker -> {"shares": int, "avg_cost": float}
        "history": [],   # 取引履歴
        "created_at": datetime.now().isoformat(),
    }


def load():
    if not os.path.exists(STATE_PATH):
        state = _default_state()
        save(state)
        return state
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def buy(state, ticker, shares, price, reason=""):
    cost = shares * price
    if cost > state["cash"]:
        return {"error": f"資金不足: 必要 {cost:.0f}円 / 保有 {state['cash']:.0f}円"}
    state["cash"] -= cost
    h = state["holdings"].setdefault(ticker, {"shares": 0, "avg_cost": 0.0})
    total_cost = h["avg_cost"] * h["shares"] + cost
    h["shares"] += shares
    h["avg_cost"] = total_cost / h["shares"] if h["shares"] else 0.0
    state["history"].append({
        "time": datetime.now().isoformat(), "action": "buy", "ticker": ticker,
        "shares": shares, "price": price, "reason": reason,
    })
    save(state)
    return {"ok": True, "cash_after": state["cash"]}


def sell(state, ticker, shares, price, reason=""):
    h = state["holdings"].get(ticker)
    if not h or h["shares"] < shares:
        return {"error": f"保有不足: {ticker} は {h['shares'] if h else 0}株しかない"}
    h["shares"] -= shares
    proceeds = shares * price
    state["cash"] += proceeds
    if h["shares"] == 0:
        del state["holdings"][ticker]
    state["history"].append({
        "time": datetime.now().isoformat(), "action": "sell", "ticker": ticker,
        "shares": shares, "price": price, "reason": reason,
    })
    save(state)
    return {"ok": True, "cash_after": state["cash"]}


def valuation(state, prices: dict):
    """prices: {ticker: current_price} を受け取り、評価額の内訳を返す"""
    holdings_value = 0.0
    breakdown = []
    for ticker, h in state["holdings"].items():
        price = prices.get(ticker)
        if price is None:
            continue
        value = h["shares"] * price
        pnl = (price - h["avg_cost"]) * h["shares"]
        holdings_value += value
        breakdown.append({
            "ticker": ticker, "shares": h["shares"], "avg_cost": h["avg_cost"],
            "current_price": price, "value": value, "pnl": pnl,
        })
    total = state["cash"] + holdings_value
    return {
        "cash": state["cash"], "holdings_value": holdings_value, "total": total,
        "pnl_total": total - INITIAL_CASH, "breakdown": breakdown,
    }
