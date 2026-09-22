"""
実際の市場データ取得 (yfinance)。NISA成長投資枠でよく使われる
東証上場銘柄・ETFを中心にウォッチリストを持つ。
"""
import yfinance as yf

WATCHLIST = {
    "7203.T": "トヨタ自動車",
    "6758.T": "ソニーグループ",
    "9984.T": "ソフトバンクグループ",
    "8306.T": "三菱UFJフィナンシャル・グループ",
    "6501.T": "日立製作所",
    "9432.T": "NTT",
    "4063.T": "信越化学工業",
    "6098.T": "リクルートホールディングス",
    "1306.T": "TOPIX連動型ETF",
    "1321.T": "日経225連動型ETF",
}


def get_quotes(tickers=None):
    tickers = tickers or list(WATCHLIST.keys())
    result = {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            hist = tk.history(period="5d")
            if hist.empty:
                continue
            last = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2] if len(hist) > 1 else last
            change_pct = (last - prev) / prev * 100 if prev else 0
            result[t] = {
                "name": WATCHLIST.get(t, t),
                "price": round(float(last), 1),
                "change_pct": round(float(change_pct), 2),
            }
        except Exception as e:
            result[t] = {"error": str(e)}
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(get_quotes(), ensure_ascii=False, indent=2))
