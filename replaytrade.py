import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import matplotlib.animation as animation
import matplotlib.dates as mdates

class SwingTradeSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("Simulador de Swing Trade")
        self.root.geometry("1400x900")
        
        # Variáveis de controle
        self.df = None
        self.current_index = 50
        self.is_playing = False
        self.speed = 500  # milliseconds
        self.animation_id = None
        
	# ===== Indicadores (flags) =====
        self.show_sma = False
        self.show_ema = False
        self.show_bb = False
        self.show_rsi = False
        self.show_macd = False
        self.show_volume = False

        # Zoom (quantidade de candles visíveis)
        self.window_size = 50
        self.min_window = 10
        self.max_window = 200

        # Períodos
        self.sma_period = 20
        self.ema_period = 9
        self.bb_period = 20
        self.bb_std = 2
        self.rsi_period = 14

        # Controle de trades
        self.initial_capital = 10000.0
        self.capital = self.initial_capital
        self.position = None  # {'shares': int, 'entry_price': float, 'entry_date': str}
        self.trades_history = []
        self.equity_curve = []
        
        self.df_plot = None
        self.tooltip = None
        self.start_idx = 0
  
        self.setup_ui()

    def toggle_indicator(self, name):
        setattr(self, f"show_{name}", not getattr(self, f"show_{name}"))
        self.plot_candles()

    def calculate_indicators(self):
        df = self.df

        df["SMA"] = df["Close"].rolling(self.sma_period).mean()
        df["EMA"] = df["Close"].ewm(span=self.ema_period, adjust=False).mean()

        # Bollinger
        ma = df["Close"].rolling(self.bb_period).mean()
        std = df["Close"].rolling(self.bb_period).std()
        df["BB_UP"] = ma + self.bb_std * std
        df["BB_DN"] = ma - self.bb_std * std

        # RSI
        delta = df["Close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(self.rsi_period).mean()
        avg_loss = loss.rolling(self.rsi_period).mean()
        rs = avg_gain / avg_loss
        df["RSI"] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = df["Close"].ewm(span=12, adjust=False).mean()
        ema26 = df["Close"].ewm(span=26, adjust=False).mean()
        df["MACD"] = ema12 - ema26
        df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()

    def zoom_in(self, event=None):
        if self.window_size > self.min_window:
            self.window_size -= 5
            self.plot_candles()
            print(f"zoom: {self.window_size}")

    def zoom_out(self, event=None):
        if self.window_size < self.max_window:
            self.window_size += 5
            self.plot_candles()
            print(f"zoom: {self.window_size}")

    def on_mouse_move_old(self, event):
        # Segurança total
        if self.df_plot is None or self.tooltip is None:
            return

        # === CTRL OBRIGATÓRIO ===
        if event.key is None or "control" not in event.key:
            self.tooltip.set_visible(False)
            self.canvas.draw_idle()
            return

        if event.inaxes != self.ax_price:
            self.tooltip.set_visible(False)
            self.canvas.draw_idle()
            return

        if event.xdata is None:
            self.tooltip.set_visible(False)
            self.canvas.draw_idle()
            return

        x = int(round(event.xdata))

        if x < 0 or x >= len(self.df_plot):
            self.tooltip.set_visible(False)
            self.canvas.draw_idle()
            return

        row = self.df_plot.iloc[x]

        text = (
            f"Data: {row['Date'].strftime('%d/%m/%Y')}\n"
            f"Open:  {row['Open']:.2f}\n"
            f"High:  {row['High']:.2f}\n"
            f"Low:   {row['Low']:.2f}\n"
            f"Close: {row['Close']:.2f}\n"
            f"Vol:   {int(row['Volume'])}"
        )

        self.tooltip.xy = (x, row['High'])
        self.tooltip.set_text(text)
        self.tooltip.set_visible(True)

        self.canvas.draw_idle()

    def on_mouse_move(self, event):

        # Segurança total
        if self.df_plot is None or self.tooltip is None:
            return

        # Só mostra se Ctrl estiver pressionado
        if event.key != "control":
            if self.tooltip.get_visible():
                self.tooltip.set_visible(False)
                self.canvas.draw_idle()
            return
        	
        # Mouse fora do eixo
        if event.inaxes != self.ax:
            if self.tooltip.get_visible():
                self.tooltip.set_visible(False)
                self.canvas.draw_idle()
            #return
        
        # Coordenada X (índice do candle)
        if event.xdata is None:
            return
        
        x = int(round(event.xdata))

        # Fora do range dos candles
        if x < 0 or x >= len(self.df_plot):
            if self.tooltip.get_visible():
                self.tooltip.set_visible(False)
                self.canvas.draw_idle()
            return
        
        # Dados do candle
        row = self.df_plot.iloc[x]

        texto = (
            f"Data: {row['Date'].strftime('%d/%m/%Y')}\n"
            f"Abertura: {row['Open']:.2f}\n"
            f"Máxima: {row['High']:.2f}\n"
            f"Mínima: {row['Low']:.2f}\n"
            f"Fechamento: {row['Close']:.2f}\n"
            f"Volume: {int(row['Volume']):,}".replace(",", ".")
        )

        # Posiciona tooltip no candle
        self.tooltip.xy = (x, row["High"])
        self.tooltip.set_text(texto)

        # === Ajuste automático de borda ===
        total = len(self.df_plot)
        limite_direita = int(total * 0.75)

        if x >= limite_direita:
            self.tooltip.xytext = (-220, 15)
            self.tooltip.set_ha("right")
        else:
            self.tooltip.xytext = (15, 15)
            self.tooltip.set_ha("left")

        # Exibe tooltip
        self.tooltip.set_visible(True)
        self.canvas.draw_idle()

        
    def setup_ui(self):
        # Frame superior para controles
        control_frame = tk.Frame(self.root, bg='#2b2b2b', pady=10)
        control_frame.pack(side=tk.TOP, fill=tk.X)
        
        # Entrada de dados
        tk.Label(control_frame, text="Ação:", bg='#2b2b2b', fg='white', font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        self.ticker_entry = tk.Entry(control_frame, width=10, font=('Arial', 10))
        self.ticker_entry.insert(0, "PETR4.SA")
        self.ticker_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Label(control_frame, text="Data Início:", bg='#2b2b2b', fg='white', font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        self.date_entry = tk.Entry(control_frame, width=12, font=('Arial', 10))
        self.date_entry.insert(0, "2023-01-01")
        self.date_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Button(control_frame, text="Carregar", command=self.load_data, 
                 bg='#4a4a4a', fg='white', font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        
        # Separador
        tk.Frame(control_frame, width=2, bg='gray').pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # Controles de reprodução
        self.btn_backward = tk.Button(control_frame, text="◄◄", command=self.backward,
                                     bg='#4a4a4a', fg='white', font=('Arial', 12), width=4)
        self.btn_backward.pack(side=tk.LEFT, padx=2)
        
        self.btn_play = tk.Button(control_frame, text="▶", command=self.toggle_play,
                                 bg='#4a4a4a', fg='white', font=('Arial', 12), width=4)
        self.btn_play.pack(side=tk.LEFT, padx=2)
        
        self.btn_forward = tk.Button(control_frame, text="►►", command=self.forward,
                                    bg='#4a4a4a', fg='white', font=('Arial', 12), width=4)
        self.btn_forward.pack(side=tk.LEFT, padx=2)
        
        # Separador
        tk.Frame(control_frame, width=2, bg='gray').pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # Controles de trading
        self.btn_buy = tk.Button(control_frame, text="COMPRAR", command=self.buy,
                                bg='#00aa00', fg='white', font=('Arial', 11, 'bold'), width=10)
        self.btn_buy.pack(side=tk.LEFT, padx=5)
        
        self.btn_sell = tk.Button(control_frame, text="VENDER", command=self.sell,
                                 bg='#cc0000', fg='white', font=('Arial', 11, 'bold'), width=10)
        self.btn_sell.pack(side=tk.LEFT, padx=5)
        self.btn_sell.config(state=tk.DISABLED)
        
        # Separador
        tk.Frame(control_frame, width=2, bg='gray').pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # Velocidade
        tk.Label(control_frame, text="Velocidade:", bg='#2b2b2b', fg='white', font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        self.speed_scale = tk.Scale(control_frame, from_=10, to=2000, orient=tk.HORIZONTAL,
                                   command=self.update_speed, bg='#4a4a4a', fg='white',
                                   length=150, troughcolor='#666666')
        self.speed_scale.set(500)
        self.speed_scale.pack(side=tk.LEFT, padx=5)
        
        # Frame principal
        main_frame = tk.Frame(self.root)
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Frame esquerdo (gráfico)
        left_frame = tk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Criar figura matplotlib
        self.fig = Figure(figsize=(10, 8), facecolor='#1e1e1e')
        self.ax = self.fig.add_subplot(111, facecolor='#2b2b2b')
        
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        self.canvas = FigureCanvasTkAgg(self.fig, master=left_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # conexão do mouse (AQUI)
        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_move)

        
        # Frame direito (estatísticas)
        right_frame = tk.Frame(main_frame, bg='#2b2b2b', width=300)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
        right_frame.pack_propagate(False)
        
        # Estatísticas
        tk.Label(right_frame, text="ESTATÍSTICAS", bg='#2b2b2b', fg='white',
                font=('Arial', 14, 'bold')).pack(pady=10)
        
        self.stats_frame = tk.Frame(right_frame, bg='#2b2b2b')
        self.stats_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        
        self.create_stats_labels()
        
        # Tabela de trades
        trades_label = tk.Label(right_frame, text="HISTÓRICO DE TRADES", bg='#2b2b2b', fg='white',
                               font=('Arial', 12, 'bold'))
        trades_label.pack(pady=(20, 5))
        
        # Criar Treeview para trades
        columns = ('Data', 'Tipo', 'Preço', 'Result %')
        self.trades_tree = ttk.Treeview(right_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.trades_tree.heading(col, text=col)
            self.trades_tree.column(col, width=70, anchor='center')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.trades_tree.yview)
        self.trades_tree.configure(yscroll=scrollbar.set)
        
        self.trades_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Status bar
        self.status_bar = tk.Label(self.root, text="Carregue uma ação para começar", 
                                  bg='#3a3a3a', fg='white', anchor=tk.W, font=('Arial', 9))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # ===== Atalhos =====
        self.root.bind("1", lambda e: self.toggle_indicator("sma"))
        self.root.bind("2", lambda e: self.toggle_indicator("ema"))
        self.root.bind("3", lambda e: self.toggle_indicator("bb"))
        self.root.bind("4", lambda e: self.toggle_indicator("rsi"))
        self.root.bind("5", lambda e: self.toggle_indicator("macd"))
        self.root.bind("6", lambda e: self.toggle_indicator("volume"))
        self.root.bind("+", self.zoom_in)
        self.root.bind("-", self.zoom_out)

        '''
ATALHOS do ROOT.BIND
1 = SMA
2 = EMA
3 = Bollinger
4 = RSI
5 = MACD
6 = Volume
+/-=mais ou menos candles
        '''
        
    def create_stats_labels(self):
        stats = [
            ("Capital Inicial:", f"R$ {self.initial_capital:,.2f}"),
            ("Capital Atual:", f"R$ {self.capital:,.2f}"),
            ("Retorno:", "0.00%"),
            ("Posição:", "Nenhuma"),
            ("Qtd Ações:", "0"),
            ("Preço Médio:", "R$ 0.00"),
            ("Total Trades:", "0"),
            ("Trades Ganhos:", "0"),
            ("Trades Perdidos:", "0"),
            ("Taxa de Acerto:", "0%"),
            ("Maior Ganho:", "0.00%"),
            ("Maior Perda:", "0.00%"),
        ]
        
        self.stat_labels = {}
        for label, value in stats:
            frame = tk.Frame(self.stats_frame, bg='#2b2b2b')
            frame.pack(fill=tk.X, pady=3)
            
            tk.Label(frame, text=label, bg='#2b2b2b', fg='#aaaaaa',
                    font=('Arial', 9), anchor=tk.W).pack(side=tk.LEFT)
            
            val_label = tk.Label(frame, text=value, bg='#2b2b2b', fg='white',
                                font=('Arial', 9, 'bold'), anchor=tk.E)
            val_label.pack(side=tk.RIGHT)
            
            self.stat_labels[label] = val_label
    
    def load_data(self):
        ticker = self.ticker_entry.get().strip()
        start_date = self.date_entry.get().strip()
        
        try:
            self.status_bar.config(text=f"Carregando dados de {ticker}...")
            self.root.update()
            
            # Baixar dados
            end_date = datetime.now().strftime('%Y-%m-%d')
            df_temp = yf.download(ticker, start=start_date, end=end_date, progress=False)
            
            if df_temp.empty:
                messagebox.showerror("Erro", "Nenhum dado encontrado para esta ação/período")
                return
            
            # Resetar o índice e garantir que Date seja uma coluna
            df_temp = df_temp.reset_index()
            
            # Achatar colunas MultiIndex se necessário
            if isinstance(df_temp.columns, pd.MultiIndex):
                df_temp.columns = df_temp.columns.get_level_values(0)
            
            # Certificar-se de que as colunas existem
            required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in df_temp.columns for col in required_cols):
                messagebox.showerror("Erro", "Dados incompletos da ação")
                return
            
            self.df = df_temp
            self.calculate_indicators()
            self.current_index = min(50, len(self.df))
            
            # Resetar trading
            self.capital = self.initial_capital
            self.position = None
            self.trades_history = []
            self.equity_curve = []
            self.btn_sell.config(state=tk.DISABLED)
            self.btn_buy.config(state=tk.NORMAL)
            
            # Limpar treeview
            for item in self.trades_tree.get_children():
                self.trades_tree.delete(item)
            
            self.update_stats()
            self.plot_candles()
            self.status_bar.config(text=f"Dados carregados: {len(self.df)} candles")
            
        except Exception as e:
            import traceback
            messagebox.showerror("Erro", f"Erro ao carregar dados: {str(e)}\n\n{traceback.format_exc()}")
            self.status_bar.config(text="Erro ao carregar dados")
    
    def plot_candles(self):
        if self.df is None or len(self.df) == 0:
            return

        # ===== Limpar figura =====
        self.fig.clear()

        # ===== Quantos subplots =====
        rows = 1
        if self.show_volume:
            rows += 1
        if self.show_rsi:
            rows += 1
        if self.show_macd:
            rows += 1

        # ===== Criar eixos =====
        self.ax_price = self.fig.add_subplot(rows, 1, 1)
        current_row = 2

        if self.show_volume:
            self.ax_volume = self.fig.add_subplot(rows, 1, current_row, sharex=self.ax_price)
            current_row += 1

        if self.show_rsi:
            self.ax_rsi = self.fig.add_subplot(rows, 1, current_row, sharex=self.ax_price)
            current_row += 1

        if self.show_macd:
            self.ax_macd = self.fig.add_subplot(rows, 1, current_row, sharex=self.ax_price)

        # ===== Cor de fundo =====
        bg = '#2b2b2b'

        self.fig.patch.set_facecolor(bg)
        self.ax_price.set_facecolor(bg)

        if self.show_volume:
            self.ax_volume.set_facecolor(bg)

        if self.show_rsi:
            self.ax_rsi.set_facecolor(bg)

        if self.show_macd:
            self.ax_macd.set_facecolor(bg)

        # ===== Ajuste das cores dos eixos =====
        for ax in self.fig.axes:
            ax.tick_params(colors='white')
            ax.yaxis.label.set_color('white')
            ax.xaxis.label.set_color('white')
            ax.title.set_color('white')
            ax.grid(True, alpha=0.2, color='gray')


        # ===== Janela de candles =====
        # trocando pela linha de baixo, para controlar por + ou - 
        start_idx = max(0, self.current_index - 50)

        #ficou feio assim, usando o anterior start_idx = max(0, self.current_index - self.window_size)
        end_idx = self.current_index
        df_slice = self.df.iloc[start_idx:end_idx].copy()

        if len(df_slice) == 0:
            return

        x = range(len(df_slice))

        # ===== Plotar candles =====
        for i, (_, row) in enumerate(df_slice.iterrows()):
            open_price = row['Open']
            close_price = row['Close']
            high_price = row['High']
            low_price = row['Low']

            color = '#00ff00' if close_price >= open_price else '#ff0000'
            height = abs(close_price - open_price)
            bottom = min(open_price, close_price)

            self.ax_price.add_patch(
                Rectangle((i - 0.3, bottom), 0.6, height,
                          facecolor=color, edgecolor=color, alpha=0.8)
            )

            self.ax_price.plot([i, i], [low_price, high_price],
                               color=color, linewidth=1)

        # ===== Indicadores no preço =====
        if self.show_sma:
            self.ax_price.plot(x, df_slice["SMA"], color="yellow", linewidth=1, label="SMA")

        if self.show_ema:
            self.ax_price.plot(x, df_slice["EMA"], color="cyan", linewidth=1, label="EMA")

        if self.show_bb:
            self.ax_price.plot(x, df_slice["BB_UP"], color="gray", linestyle="--", linewidth=1)
            self.ax_price.plot(x, df_slice["BB_DN"], color="gray", linestyle="--", linewidth=1)

        # ===== Marcar compra =====
        if self.position:
            entry_date = self.position['entry_date']
            if (df_slice['Date'] == entry_date).any():
                entry_idx = df_slice[df_slice['Date'] == entry_date].index[0] - start_idx
                entry_price = self.position['entry_price']
                self.ax_price.plot(entry_idx, entry_price, 'g^', markersize=14)
                self.ax_price.axhline(entry_price, color='green', linestyle='--', alpha=0.5)

        # ===== Volume =====
        if self.show_volume:
            self.ax_volume.bar(x, df_slice["Volume"], alpha=0.3)
            self.ax_volume.set_ylabel("Volume")

        # ===== RSI =====
        if self.show_rsi:
            self.ax_rsi.plot(x, df_slice["RSI"], color="orange")
            self.ax_rsi.axhline(70, color="red", linestyle="--")
            self.ax_rsi.axhline(30, color="green", linestyle="--")
            self.ax_rsi.set_ylim(0, 100)
            self.ax_rsi.set_ylabel("RSI")

        # ===== MACD =====
        if self.show_macd:
            self.ax_macd.plot(x, df_slice["MACD"], label="MACD")
            self.ax_macd.plot(x, df_slice["MACD_SIGNAL"], label="Signal")
            self.ax_macd.legend()

        # ===== Estética =====
        self.ax_price.set_xlim(-1, len(df_slice))
        self.ax_price.grid(True, alpha=0.2)

        current_date = df_slice.iloc[-1]['Date']
        current_close = df_slice.iloc[-1]['Close']

        self.ax_price.set_title(
            f'{self.ticker_entry.get()} - {current_date.strftime("%d/%m/%Y")} '
            f'- Fechamento: R$ {current_close:.2f}'
        )

        self.fig.tight_layout()
        self.canvas.draw()
        
        # ===== Tooltip (recriado a cada redraw) =====
        self.tooltip = self.ax_price.annotate(
            "",
            xy=(0, 0),
            xytext=(15, 15),
            textcoords="offset points",
            bbox=dict(boxstyle="round", fc="#1e1e1e", ec="white"),
            arrowprops=dict(arrowstyle="->"),
            color="white"
        )
        self.tooltip.set_visible(False)


        # para o tooltip
        self.df_plot = df_slice.reset_index(drop=True)
        self.start_idx = start_idx

    def toggle_play(self):
        if self.df is None:
            messagebox.showwarning("Aviso", "Carregue uma ação primeiro")
            return
        
        self.is_playing = not self.is_playing
        
        if self.is_playing:
            self.btn_play.config(text="⏸")
            self.animate()
        else:
            self.btn_play.config(text="▶")
            if self.animation_id:
                self.root.after_cancel(self.animation_id)
    
    def animate(self):
        if self.is_playing and self.current_index < len(self.df):
            self.forward()
            self.animation_id = self.root.after(self.speed, self.animate)
        else:
            self.is_playing = False
            self.btn_play.config(text="▶")
    
    def forward(self):
        if self.df is None:
            return
        
        if self.current_index < len(self.df):
            self.current_index += 1
            self.plot_candles()
            self.update_equity_curve()
    
    def backward(self):
        if self.df is None:
            return
        
        if self.current_index > 50:
            self.current_index -= 1
            self.plot_candles()
    
    def update_speed(self, value):
        self.speed = int(value)
    
    def buy(self):
        if self.df is None or self.current_index >= len(self.df):
            return
        
        if self.position:
            messagebox.showwarning("Aviso", "Você já tem uma posição aberta")
            return
        
        current_row = self.df.iloc[self.current_index - 1]
        entry_price = current_row['Close']
        shares = int(self.capital / entry_price)
        
        if shares == 0:
            messagebox.showwarning("Aviso", "Capital insuficiente para comprar")
            return
        
        self.position = {
            'shares': shares,
            'entry_price': entry_price,
            'entry_date': current_row['Date']
        }
        
        self.btn_buy.config(state=tk.DISABLED)
        self.btn_sell.config(state=tk.NORMAL)
        
        self.update_stats()
        self.plot_candles()
        self.status_bar.config(text=f"Compra: {shares} ações a R$ {entry_price:.2f}")
    
    def sell(self):
        if not self.position or self.df is None or self.current_index >= len(self.df):
            return
        
        current_row = self.df.iloc[self.current_index - 1]
        exit_price = current_row['Close']
        
        # Calcular resultado
        entry_value = self.position['shares'] * self.position['entry_price']
        exit_value = self.position['shares'] * exit_price
        profit = exit_value - entry_value
        profit_pct = (profit / entry_value) * 100
        
        self.capital += profit
        
        # Registrar trade
        trade = {
            'entry_date': self.position['entry_date'],
            'exit_date': current_row['Date'],
            'entry_price': self.position['entry_price'],
            'exit_price': exit_price,
            'shares': self.position['shares'],
            'profit': profit,
            'profit_pct': profit_pct
        }
        
        self.trades_history.append(trade)
        
        # Adicionar ao treeview
        tag = 'win' if profit > 0 else 'loss'
        self.trades_tree.insert('', 0, values=(
            current_row['Date'].strftime('%d/%m/%y'),
            'Venda',
            f'{exit_price:.2f}',
            f'{profit_pct:+.2f}%'
        ), tags=(tag,))
        
        self.trades_tree.tag_configure('win', foreground='#00ff00')
        self.trades_tree.tag_configure('loss', foreground='#ff0000')
        
        self.position = None
        self.btn_sell.config(state=tk.DISABLED)
        self.btn_buy.config(state=tk.NORMAL)
        
        self.update_stats()
        self.plot_candles()
        self.status_bar.config(text=f"Venda: R$ {exit_price:.2f} | "
                              f"Lucro: R$ {profit:.2f} ({profit_pct:+.2f}%)")
    
    def update_equity_curve(self):
        if self.position and self.current_index > 0:
            current_price = self.df.iloc[self.current_index - 1]['Close']
            current_value = self.capital + (self.position['shares'] * current_price)
            self.equity_curve.append(current_value)
    
    def update_stats(self):
        # Capital atual (incluindo posição aberta)
        current_capital = self.capital
        if self.position and self.current_index > 0:
            current_price = self.df.iloc[self.current_index - 1]['Close']
            current_capital += self.position['shares'] * current_price
        
        returns = ((current_capital - self.initial_capital) / self.initial_capital) * 100
        
        self.stat_labels["Capital Atual:"].config(
            text=f"R$ {current_capital:,.2f}",
            fg='#00ff00' if current_capital >= self.initial_capital else '#ff0000'
        )
        
        self.stat_labels["Retorno:"].config(
            text=f"{returns:+.2f}%",
            fg='#00ff00' if returns >= 0 else '#ff0000'
        )
        
        # Posição
        if self.position:
            self.stat_labels["Posição:"].config(text="COMPRADO", fg='#00ff00')
            self.stat_labels["Qtd Ações:"].config(text=str(self.position['shares']))
            self.stat_labels["Preço Médio:"].config(text=f"R$ {self.position['entry_price']:.2f}")
        else:
            self.stat_labels["Posição:"].config(text="Nenhuma", fg='white')
            self.stat_labels["Qtd Ações:"].config(text="0")
            self.stat_labels["Preço Médio:"].config(text="R$ 0.00")
        
        # Estatísticas de trades
        if self.trades_history:
            total_trades = len(self.trades_history)
            winning_trades = len([t for t in self.trades_history if t['profit'] > 0])
            losing_trades = total_trades - winning_trades
            win_rate = (winning_trades / total_trades) * 100
            
            profits = [t['profit_pct'] for t in self.trades_history]
            max_gain = max(profits) if profits else 0
            max_loss = min(profits) if profits else 0
            
            self.stat_labels["Total Trades:"].config(text=str(total_trades))
            self.stat_labels["Trades Ganhos:"].config(text=str(winning_trades))
            self.stat_labels["Trades Perdidos:"].config(text=str(losing_trades))
            self.stat_labels["Taxa de Acerto:"].config(text=f"{win_rate:.1f}%")
            self.stat_labels["Maior Ganho:"].config(text=f"{max_gain:+.2f}%", fg='#00ff00')
            self.stat_labels["Maior Perda:"].config(text=f"{max_loss:+.2f}%", fg='#ff0000')

if __name__ == "__main__":
    root = tk.Tk()
    app = SwingTradeSimulator(root)
    root.mainloop()
