#https://github.com/Hattorius/Tradingview-ticker?tab=readme-ov-file#installing
# ignore everything here
import sys, os
current_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)



# ignore everything here
import sys, os
current_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
import time
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from ticker import ticker

SYMBOL = "BMFBOVESPA:PETR4"
CANDLE_SECONDS = 15
MAX_CANDLES = 40

tick = ticker(SYMBOL)
tick.start()

candles = []
current_candle = None

plt.style.use("dark_background")
fig, ax = plt.subplots(figsize=(15, 7))
plt.ion()
plt.show(block=False)

def redraw():
    ax.clear()
    visible = candles[-MAX_CANDLES:]
    if not visible:
        return
    
    lows = []
    highs = []
    labels = []
    
    for i, c in enumerate(visible):
        is_current = (i == len(visible) - 1)
        color = "lime" if c["close"] >= c["open"] else "red"
        
        body_low = min(c["open"], c["close"])
        body_high = max(c["open"], c["close"])
        
        ax.add_patch(
            Rectangle(
                (i - 0.3, body_low),
                0.6,
                body_high - body_low if body_high != body_low else 0.002,
                color=color,
                alpha=0.9,
                edgecolor='white' if is_current else None,
                linewidth=2 if is_current else 0
            )
        )
        
        ax.plot([i, i], [c["low"], c["high"]], 
                color=color, linewidth=2 if is_current else 1.5)
        
        lows.append(c["low"])
        highs.append(c["high"])
        
        # Formatar horário (HH:MM:SS)
        labels.append(datetime.fromtimestamp(c["time"]).strftime('%H:%M:%S'))
    
    # Fixar xlim e ylim para evitar distorção
    ax.set_xlim(-0.5, MAX_CANDLES - 0.5)
    
    if lows and highs:
        price_range = max(highs) - min(lows)
        padding = price_range * 0.02 if price_range > 0 else 0.01
        ax.set_ylim(min(lows) - padding, max(highs) + padding)
    
    # Configurar labels do eixo X (mostrar 1 a cada 5 candles para não poluir)
    tick_positions = list(range(len(visible)))
    tick_labels = labels
    
    # Mostrar só alguns horários (espaçados)
    step = max(1, len(visible) // 8)
    visible_positions = tick_positions[::step]
    visible_labels = tick_labels[::step]
    
    ax.set_xticks(visible_positions)
    ax.set_xticklabels(visible_labels, rotation=45, ha='right', fontsize=8)
    
    if current_candle:
        direction = "🟢" if current_candle["close"] >= current_candle["open"] else "🔴"
        ax.set_title(
            f"{SYMBOL} | {direction} {current_candle['close']:.2f} | Total: {len(candles)} candles",
            fontsize=12, fontweight='bold'
        )
    
    ax.grid(alpha=0.2)
    fig.canvas.draw()
    fig.canvas.flush_events()

print(f"🚀 Iniciando... Candles de {CANDLE_SECONDS}s")

last_redraw = 0

while True:
    state = tick.states.get(SYMBOL)
    
    if not state or state.get("price", 0) == 0:
        time.sleep(0.05)
        continue
    
    price = state["price"]
    ts = state.get("time", time.time())
    candle_time = int(ts) - (int(ts) % CANDLE_SECONDS)
    
    if current_candle is None:
        current_candle = {
            "time": candle_time,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
        }
        candles.append(current_candle)
        print(f"🟢 Candle #{len(candles)} | {datetime.fromtimestamp(candle_time).strftime('%H:%M:%S')} | {price:.2f}")
        redraw()
        
    elif candle_time != current_candle["time"]:
        print(f"🔵 Fechou #{len(candles)} em {current_candle['close']:.2f}")
        
        current_candle = {
            "time": candle_time,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
        }
        candles.append(current_candle)
        print(f"🟢 Candle #{len(candles)} | {datetime.fromtimestamp(candle_time).strftime('%H:%M:%S')} | {price:.2f}")
        redraw()
        
    else:
        updated = False
        if price > current_candle["high"]:
            current_candle["high"] = price
            updated = True
        if price < current_candle["low"]:
            current_candle["low"] = price
            updated = True
        if price != current_candle["close"]:
            current_candle["close"] = price
            updated = True
        
        if updated:
            now = time.time()
            if now - last_redraw > 0.3:
                redraw()
                last_redraw = now
    
    time.sleep(0.05)
