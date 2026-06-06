import asyncio
import aiohttp
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SPIKE_MULTIPLIER = float(os.environ.get("SPIKE_MULTIPLIER", "5"))
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "3600"))

ALERTED = set()

async def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        await session.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})

async def get_top_symbols():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            data = await r.json()
            usdt_pairs = [d for d in data if d["symbol"].endswith("USDT")]
            sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x["quoteVolume"]), reverse=True)
            return [d["symbol"] for d in sorted_pairs[:50]]

async def get_klines(symbol, interval="1h", limit=31):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            return await r.json()

async def check_volume_spike():
    global ALERTED
    new_alerted = set()
    try:
        symbols = await get_top_symbols()
    except Exception as e:
        print(f"Error getting symbols: {e}")
        return
    for symbol in symbols:
        try:
            klines = await get_klines(symbol)
            if len(klines) < 31:
                continue
            volumes = [float(k[5]) for k in klines[:-1]]
            current_volume = float(klines[-1][5])
            current_price = float(klines[-1][4])
            avg_volume = sum(volumes[-30:]) / 30
            if avg_volume == 0:
                continue
            ratio = current_volume / avg_volume
            if ratio >= SPIKE_MULTIPLIER:
                new_alerted.add(symbol)
                if symbol not in ALERTED:
                    open_price = float(klines[-1][1])
                    change = ((current_price - open_price) / open_price) * 100
                    direction = "📈" if change >= 0 else "📉"
                    now = datetime.now().strftime("%d/%m/%Y %H:%M")
                    msg = (
                        f"🚨 <b>Volume Spike Detected!</b>\n\n"
                        f"Coin: <b>{symbol}</b>\n"
                        f"Current Volume: {current_volume:,.0f}\n"
                        f"Average Volume (30h): {avg_volume:,.0f}\n"
                        f"Ratio: <b>{ratio:.1f}x</b> 🔥\n\n"
                        f"Price: ${current_price:,.4f}\n"
                        f"Change: {direction} {change:+.2f}%\n\n"
                        f"Time: {now}"
                    )
                    await send_telegram(msg)
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"Error checking {symbol}: {e}")
            continue
    ALERTED = new_alerted

async def main():
    print("Volume Spike Bot Started!")
    await send_telegram("🚨 Volume Spike Bot Started Successfully!")
    while True:
        print(f"Checking volume spikes... {datetime.now()}")
        await check_volume_spike()
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
