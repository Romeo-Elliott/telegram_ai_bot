import asyncio
import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import ccxt

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

conversation_history = {}

def get_crypto_price(symbol: str) -> str:
    try:
        exchange = ccxt.binance()
        ticker = exchange.fetch_ticker(f"{symbol.upper()}/USDT")
        price = ticker['last']
        change = ticker['percentage']
        return f"{symbol.upper()}/USDT: ${price:,.2f} ({change:+.2f}%)"
    except Exception as e:
        return f"Error: {e}"

def analyze_signal(symbol: str) -> str:
    try:
        exchange = ccxt.binance()
        ohlcv = exchange.fetch_ohlcv(f"{symbol.upper()}/USDT", '1h', limit=20)
        closes = [c[4] for c in ohlcv]
        current = closes[-1]
        sma10 = sum(closes[-10:]) / 10
        sma20 = sum(closes) / 20
        if current > sma10 > sma20:
            signal = "📈 BULLISH"
        elif current < sma10 < sma20:
            signal = "📉 BEARISH"
        else:
            signal = "⚖️ NEUTRAL"
        return f"{symbol.upper()} Signal:\nPrice: ${current:,.2f}\nSMA10: ${sma10:,.2f}\nSMA20: ${sma20:,.2f}\n{signal}"
    except Exception as e:
        return f"Error: {e}"

def call_openrouter(messages: list) -> str:
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "meta-llama/llama-3.3-70b-instruct:free",
                "messages": messages,
                "max_tokens": 1000
            },
            timeout=30
        )
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error: {e}"

async def run_agent(user_id: int, user_message: str) -> str:
    try:
        msg_lower = user_message.lower()

        crypto_symbols = ["btc", "eth", "sol", "bnb", "xrp", "doge", "ada", "avax", "link", "dot", "ton", "bitcoin", "ethereum"]
        detected_symbol = None
        for sym in crypto_symbols:
            if sym in msg_lower:
                detected_symbol = sym.replace("bitcoin", "btc").replace("ethereum", "eth")
                break

        extra_context = ""
        if detected_symbol:
            if any(w in msg_lower for w in ["signal", "analysis", "analyze", "trend", "သုံးသပ်"]):
                extra_context = f"\n[Real-time data: {analyze_signal(detected_symbol)}]"
            else:
                extra_context = f"\n[Real-time data: {get_crypto_price(detected_symbol)}]"

        if user_id not in conversation_history:
            conversation_history[user_id] = []

        system_msg = {
            "role": "system",
            "content": "You are a crypto trading assistant. Reply in Myanmar language if user writes in Myanmar. For general questions not related to crypto, still answer helpfully in Myanmar language."
        }

        conversation_history[user_id].append({
            "role": "user",
            "content": user_message + extra_context
        })

        messages = [system_msg] + conversation_history[user_id][-20:]

        response_text = await asyncio.to_thread(call_openrouter, messages)

        conversation_history[user_id].append({
            "role": "assistant",
            "content": response_text
        })

        if len(conversation_history[user_id]) > 20:
            conversation_history[user_id] = conversation_history[user_id][-20:]

        return response_text

    except Exception as e:
        return f"Error: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 မင်္ဂလာပါ! Crypto AI Bot ပါ။\n\n"
        "/price BTC - Price ကြည့်\n"
        "/signal ETH - Trading signal\n"
        "/clear - History ဖျက်\n\n"
        "ဘာမဆို တိုက်ရိုက် မေးလိုက်ပါ! 😊"
    )

async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /price BTC")
        return
    await update.message.reply_text(get_crypto_price(context.args[0]))

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /signal ETH")
        return
    await update.message.reply_text(analyze_signal(context.args[0]))

async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversation_history[update.effective_user.id] = []
    await update.message.reply_text("✅ History cleared!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    response = await run_agent(update.effective_user.id, update.message.text)
    await update.message.reply_text(response)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price_cmd))
    app.add_handler(CommandHandler("signal", signal_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
