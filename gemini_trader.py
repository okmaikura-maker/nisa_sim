"""
GeminiによるNISAペーパートレード運用エージェント。
実際の証券口座・実資金には一切接続しない。すべて仮想ポートフォリオ内で完結する。

1回呼ぶごとに「1回の運用判断サイクル」を実行する。定期的に(例: 毎日/毎週)
呼び出すことで「永続的に運用し続ける仮想機関」として振る舞わせる想定。

環境変数 GEMINI_API_KEY が必要。

使い方:
    python gemini_trader.py
"""
import json
import os
import sys
from datetime import datetime

import portfolio
import market_data

from google import genai
from google.genai import types

LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "decisions.jsonl")

SYSTEM_PROMPT = """
あなたは「NISA成長投資枠」を運用する仮想の資産運用機関です。
これは完全なペーパートレード(紙上取引)であり、実際のお金は一切動きません。
すべての判断はシミュレーションとして記録されるだけです。あなたの判断が
実在する証券口座に反映されることは絶対にありません。

あなたの仕事:
- 与えられる現在の市況(watchlistの株価・騰落率)と、現在のポートフォリオ状態を見て、
  買い増し・売却・様子見のいずれかを判断してください。
- 判断には必ず理由(reason)を添えてください。
- 短期的な値動きだけでなく、NISA(長期・積立・分散が基本)の趣旨に沿った判断を意識してください。
- 1回の判断で使いすぎず、現金もある程度残すこと(全力買いは避ける)。
- 損切りルールも意識してください(含み損が大きくなりすぎている銘柄は検討する)。

使えるツール:
- get_portfolio(): 現在の保有状況と評価額を取得
- buy(ticker, shares, reason): 指定銘柄を買う(ペーパー)
- sell(ticker, shares, reason): 指定銘柄を売る(ペーパー)
- finish(summary): 今回の判断サイクルの総括を書いて終了する

必ず最後は finish() を呼んで終えてください。
"""


def build_tools():
    return [types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="get_portfolio", description="現在のポートフォリオ状態(現金・保有銘柄・評価額)を取得する",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="buy", description="指定銘柄をペーパーで買う",
            parameters=types.Schema(type="OBJECT", properties={
                "ticker": types.Schema(type="STRING"),
                "shares": types.Schema(type="INTEGER"),
                "reason": types.Schema(type="STRING"),
            }, required=["ticker", "shares", "reason"]),
        ),
        types.FunctionDeclaration(
            name="sell", description="指定銘柄をペーパーで売る",
            parameters=types.Schema(type="OBJECT", properties={
                "ticker": types.Schema(type="STRING"),
                "shares": types.Schema(type="INTEGER"),
                "reason": types.Schema(type="STRING"),
            }, required=["ticker", "shares", "reason"]),
        ),
        types.FunctionDeclaration(
            name="finish", description="今回の判断サイクルを終える",
            parameters=types.Schema(type="OBJECT", properties={
                "summary": types.Schema(type="STRING"),
            }, required=["summary"]),
        ),
    ])]


def log_event(event: dict):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def run_cycle(max_turns: int = 10, model_name: str = "gemini-3.5-flash-lite"):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("環境変数 GEMINI_API_KEY を設定してください", file=sys.stderr)
        sys.exit(1)

    state = portfolio.load()
    quotes = market_data.get_quotes()
    prices = {t: q["price"] for t, q in quotes.items() if "price" in q}
    val = portfolio.valuation(state, prices)

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, tools=build_tools())

    intro = (
        f"現在時刻: {datetime.now().isoformat()}\n"
        f"市況(watchlist):\n{json.dumps(quotes, ensure_ascii=False, indent=2)}\n\n"
        f"現在のポートフォリオ評価:\n{json.dumps(val, ensure_ascii=False, indent=2)}\n\n"
        "今回の運用判断サイクルを開始してください。"
    )
    contents = [types.Content(role="user", parts=[types.Part(text=intro)])]

    for turn in range(max_turns):
        response = client.models.generate_content(model=model_name, contents=contents, config=config)
        if not response.candidates:
            break
        cand = response.candidates[0].content
        contents.append(cand)
        did_call = False
        finished = False

        for part in cand.parts:
            if part.text:
                print(f"[turn {turn}] Gemini: {part.text.strip()}")
                log_event({"turn": turn, "type": "text", "content": part.text})

            if part.function_call:
                fc = part.function_call
                did_call = True
                args = dict(fc.args) if fc.args else {}
                print(f"[turn {turn}] tool_call: {fc.name}({args})")
                log_event({"turn": turn, "type": "tool_call", "name": fc.name, "args": args})

                if fc.name == "get_portfolio":
                    result = portfolio.valuation(state, prices)
                elif fc.name == "buy":
                    price = prices.get(args.get("ticker"))
                    if price is None:
                        result = {"error": "価格不明の銘柄"}
                    else:
                        result = portfolio.buy(state, args["ticker"], int(args["shares"]), price, args.get("reason", ""))
                elif fc.name == "sell":
                    price = prices.get(args.get("ticker"))
                    if price is None:
                        result = {"error": "価格不明の銘柄"}
                    else:
                        result = portfolio.sell(state, args["ticker"], int(args["shares"]), price, args.get("reason", ""))
                elif fc.name == "finish":
                    result = {"ok": True}
                    finished = True
                    log_event({"turn": turn, "type": "cycle_summary", "summary": args.get("summary", "")})
                    print(f"[turn {turn}] CYCLE SUMMARY: {args.get('summary', '')}")
                else:
                    result = {"error": "unknown tool"}

                print(f"[turn {turn}] result: {json.dumps(result, ensure_ascii=False)[:300]}")
                log_event({"turn": turn, "type": "tool_result", "name": fc.name, "result": result})

                contents.append(types.Content(
                    role="user",
                    parts=[types.Part(function_response=types.FunctionResponse(
                        name=fc.name, response={"result": result}
                    ))]
                ))

        if finished or not did_call:
            break

    final_val = portfolio.valuation(portfolio.load(), prices)
    print("\n=== サイクル終了時点の評価額 ===")
    print(json.dumps(final_val, ensure_ascii=False, indent=2))
    log_event({"type": "cycle_end", "valuation": final_val, "time": datetime.now().isoformat()})


if __name__ == "__main__":
    run_cycle()
