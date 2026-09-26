"""
hermes_client.py
Wraps the Ollama Python client with stock-trading-focused prompts.
Model: hermes3 (Nous Hermes 3, 8B via Ollama)
"""

import ollama
from rich.console import Console

console = Console()

MODEL = "hermes3"

SYSTEM_PROMPT = """You are Hermes, an expert stock market trading coach and journal analyst.
You have deep knowledge of technical analysis, risk management, trading psychology, and the Indian stock markets (NSE/BSE).
You speak like a calm, direct mentor — insightful but concise. You never give financial advice, only observations and coaching.
When analysing trade journals, you look for behavioural patterns, emotional biases, and setup quality.
Always respond in clean markdown format suitable for Obsidian notes.
Prices are in Indian Rupees (₹). Stocks trade on NSE/BSE."""


def _chat(user_message: str, context: str = "") -> str:
    """Send a message to Hermes and return the response text."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    if context:
        messages.append({"role": "user", "content": f"Here is the context data:\n\n{context}"})
        messages.append({"role": "assistant", "content": "Understood. I've reviewed the context. Please give me your analysis request."})
    messages.append({"role": "user", "content": user_message})

    try:
        response = ollama.chat(model=MODEL, messages=messages)
        return response["message"]["content"].strip()
    except ollama.ResponseError as e:
        if "not found" in str(e).lower():
            console.print(f"\n[bold red]❌ Model '{MODEL}' not found.[/bold red]")
            console.print(f"[yellow]Run: [bold]ollama pull {MODEL}[/bold] then try again.[/yellow]\n")
        else:
            console.print(f"[bold red]❌ Ollama error:[/bold red] {e}")
        raise
    except Exception as e:
        console.print(f"[bold red]❌ Could not connect to Ollama.[/bold red]")
        console.print("[yellow]Make sure Ollama is running: [bold]ollama serve[/bold][/yellow]")
        raise


def analyze_trade_patterns(trades_summary: str) -> str:
    return _chat(
        "Analyse my trade journal entries below. Identify:\n"
        "1. My most profitable setups and what they have in common\n"
        "2. My most losing setups and why they fail\n"
        "3. Emotional patterns (FOMO, revenge trading, overconfidence)\n"
        "4. Risk management issues (stop loss adherence, position sizing)\n"
        "5. Three specific, actionable improvements I should make\n\n"
        "Format your response as a clean Obsidian markdown note with headers and bullet points.",
        context=trades_summary,
    )


def analyze_daily_journal(daily_text: str, date: str) -> str:
    return _chat(
        f"Review my market journal for {date}. Provide:\n"
        "1. A 2-3 sentence summary of what happened\n"
        "2. Key market observations I should remember\n"
        "3. Any emotional flags you noticed in my notes\n"
        "4. Two things to watch for tomorrow\n\n"
        "Be concise. Format as a short Obsidian markdown section.",
        context=daily_text,
    )


def generate_weekly_review(week_data: str, week_label: str) -> str:
    return _chat(
        f"Generate a comprehensive weekly trading review for {week_label}. Include:\n"
        "1. **Week Summary** — P&L, number of trades, win rate\n"
        "2. **Best Trade** — what went right\n"
        "3. **Worst Trade** — what went wrong and the lesson\n"
        "4. **Pattern of the Week** — what setup dominated\n"
        "5. **Psychological Assessment** — how was my mindset this week?\n"
        "6. **Next Week's Focus** — one specific thing to improve\n\n"
        "Format as a complete, well-structured Obsidian markdown document.",
        context=week_data,
    )


def analyze_watchlist_stock(stock_name: str, past_trades: str) -> str:
    return _chat(
        f"Based on my past trades in {stock_name}, give me a brief coaching note:\n"
        "1. How have I historically performed with this stock?\n"
        "2. What mistakes have I made with it?\n"
        "3. One sentence of advice for trading it again.\n\n"
        "Keep it under 150 words.",
        context=past_trades,
    )


def update_memory_insights(memory: dict, trades_summary: str) -> str:
    """Ask Hermes to update the memory with new patterns learned."""
    existing = str(memory.get("patterns", []))
    return _chat(
        "Based on the latest trade data, extract 3-5 key trading patterns or behavioural insights "
        "that should be added to my persistent memory. Return ONLY a JSON array of short strings, "
        "each under 20 words. Example: [\"Wins more on morning breakouts\", \"Holds losers past SL on Fridays\"]\n"
        f"Existing patterns: {existing}",
        context=trades_summary,
    )
