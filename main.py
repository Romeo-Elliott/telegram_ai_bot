import asyncio
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import anthropic
import ccxt

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
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

def run_agent(user_id: int, user_message: str) -> str:
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    conversation_history[user_id].append({"role": "user", "content": user_message})
    
    tools = [
        {
            "name": "get_crypto_price",
            "description": "Get current crypto price",
            "input_schema": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"]
            }
        },
        {
            "name": "analyze_signal",
            "description": "Analyze trading signal",
            "input_schema": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"]
            }
        }
    ]
    
    messages = conversation_history[user_id].copy()
    
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system="You are a crypto trading assistant. Reply in Myanmar language if user writes in Myanmar.",
            tools=tools,
            messages=messages
        )
        
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    if block.name == "get_crypto_price":
                        result = get_crypto_price(block.input["symbol"])
                    elif block.name == "analyze_signal":
                        result = analyze_signal(block.input["symbol"])
                    else:
                        result = "Tool not found"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            conversation_history[user_id].append({"role": "assistant", "content": final_text})
            if len(conversation_history[user_id]) > 20:
                conversation_history[user_id] = conversation_history[user_id][-20:]
            return final_text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 မင်္ဂလာပါ! Crypto AI Bot ပါ။\n\n"
        "/price BTC - Price ကြည့်\n"
        "/signal ETH - Trading signal\n"
        "/clear - History ဖျက်\n\n"
        "သို့မဟုတ် တိုက်ရိုက် မေးလိုက်ပါ! 😊"
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
    response = run_agent(update.effective_user.id, update.message.text)
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
