import tkinter as tk
from tkinter import ttk
import serial
import threading
import time

class SBUSMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SBUS Data Monitor")
        self.root.geometry("800x600")
        
        # シリアル通信設定
        self.serial_port = 'com7'
        self.baudrate = 115200
        self.ser = None
        self.running = True

        # チャンネル名
        self.channel_names = [
            "CH1  エルロン（左）",  "CH2  ラダー",
            "CH3  スロットル",      "CH4  エレベーター",
            "CH5  投下装置",        "CH6  エルロン（右）",
            "CH7  自動操縦",        "CH8  ミッション選択",
            "CH9  自動離着陸",      "CH10 安全装置",
            "CH11 離陸前テスト",    "CH12 離陸後テスト",
        ]
        
        # GUI要素の初期化
        self.create_widgets()
        
        # シリアル接続スレッド
        self.serial_thread = threading.Thread(target=self.monitor_serial, daemon=True)
        self.serial_thread.start()
        
        # ウィンドウを閉じるときの処理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_widgets(self):
        # タイトル
        title_label = ttk.Label(self.root, text="SBUS Data Monitor", font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # ステータス表示
        self.status_var = tk.StringVar(value="Status: Disconnected")
        status_label = ttk.Label(self.root, textvariable=self.status_var, font=("Arial", 10))
        status_label.pack(pady=5)
        
        # チャンネルデータフレーム
        frame = ttk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # キャンバスとスクロールバーの作成
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # チャンネル表示ラベル
        self.channel_labels = {}
        for i in range(12):
            ch_frame = ttk.Frame(scrollable_frame)
            ch_frame.pack(fill=tk.X, padx=5, pady=3)
            
            label_text = self.channel_names[i] if i < len(self.channel_names) else f"CH{i+1}:"
            ch_name = ttk.Label(ch_frame, text=label_text, width=22, font=("Arial", 10))
            ch_name.pack(side=tk.LEFT)
            
            # プログレスバー
            progress = ttk.Progressbar(ch_frame, length=200, mode='determinate')
            progress.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            
            # 値表示ラベル
            value_label = ttk.Label(ch_frame, text="1000", width=8, font=("Arial", 10))
            value_label.pack(side=tk.LEFT)
            
            self.channel_labels[i] = {
                'label': value_label,
                'progress': progress
            }
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # HEXデータ表示
        hex_label = ttk.Label(self.root, text="Received Data (HEX):", font=("Arial", 10))
        hex_label.pack(pady=5)
        
        self.hex_text = tk.Text(self.root, height=3, width=80, font=("Courier", 8))
        self.hex_text.pack(padx=10, pady=5)
        
        # コントロールフレーム
        control_frame = ttk.Frame(self.root)
        control_frame.pack(pady=10)
        
        connect_btn = ttk.Button(control_frame, text="Connect", command=self.connect_serial)
        connect_btn.pack(side=tk.LEFT, padx=5)
        
        disconnect_btn = ttk.Button(control_frame, text="Disconnect", command=self.disconnect_serial)
        disconnect_btn.pack(side=tk.LEFT, padx=5)
        
        clear_btn = ttk.Button(control_frame, text="Clear Log", command=self.clear_log)
        clear_btn.pack(side=tk.LEFT, padx=5)
    
    def connect_serial(self):
        try:
            self.ser = serial.Serial(self.serial_port, self.baudrate, 
                                    parity=serial.PARITY_NONE, stopbits=1, timeout=1)
            self.status_var.set(f"Status: Connected to {self.serial_port}")
        except Exception as e:
            self.status_var.set(f"Status: Error - {str(e)}")
    
    def disconnect_serial(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.status_var.set("Status: Disconnected")
    
    def clear_log(self):
        self.hex_text.delete(1.0, tk.END)
    
    def decode_sbus_data(self, data):
        """SBUSデータをデコードしてチャンネル値を取得"""
        if len(data) < 25:
            return None
        
        channels = []
        
        # CH1
        channels.append(((data[1] | (data[2] << 8)) & 0x07FF))
        # CH2
        channels.append((((data[2] >> 3) | (data[3] << 5)) & 0x07FF))
        # CH3
        channels.append((((data[3] >> 6) | (data[4] << 2) | (data[5] << 10)) & 0x07FF))
        # CH4
        channels.append((((data[5] >> 1) | (data[6] << 7)) & 0x07FF))
        # CH5
        channels.append((((data[6] >> 4) | (data[7] << 4)) & 0x07FF))
        # CH6
        channels.append((((data[7] >> 7) | (data[8] << 1) | (data[9] << 9)) & 0x07FF))
        # CH7
        channels.append((((data[9] >> 2) | (data[10] << 6)) & 0x07FF))
        # CH8
        channels.append((((data[10] >> 5) | (data[11] << 3)) & 0x07FF))
        # CH9-12
        channels.append(((data[12] | (data[13] << 8)) & 0x07FF))
        channels.append((((data[13] >> 3) | (data[14] << 5)) & 0x07FF))
        channels.append((((data[14] >> 6) | (data[15] << 2) | (data[16] << 10)) & 0x07FF))
        channels.append((((data[16] >> 1) | (data[17] << 7)) & 0x07FF))
        
        return channels[:12]
    
    def monitor_serial(self):
        """シリアルポートからデータを読み込み、GUIを更新"""
        while self.running:
            if self.ser and self.ser.is_open:
                try:
                    data = self.ser.read(25)
                    if data and len(data) == 25:
                        # HEXデータを表示
                        hex_str = ' '.join(f'{b:02X}' for b in data)
                        self.hex_text.insert(tk.END, hex_str + '\n')
                        self.hex_text.see(tk.END)
                        
                        # チャンネル値をデコード
                        channels = self.decode_sbus_data(data)
                        if channels:
                            for i, value in enumerate(channels):
                                # PWM値に変換（通常は512-1536の範囲、中央は1024）
                                pwm_value = value + 512
                                pwm_value = max(500, min(1500, pwm_value))
                                
                                self.channel_labels[i]['label'].config(text=str(pwm_value))
                                # プログレスバーの値を0-100に正規化（500-1500の範囲）
                                normalized_value = (pwm_value - 500) / 10
                                self.channel_labels[i]['progress']['value'] = normalized_value
                        
                        self.root.update_idletasks()
                except Exception as e:
                    print(f"Error reading from serial: {e}")
            else:
                time.sleep(0.1)
    
    def on_closing(self):
        self.running = False
        self.disconnect_serial()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SBUSMonitorApp(root)
    root.mainloop()
