import tkinter as tk
from tkinter import ttk
import serial
import threading
import time
import keyboard

# COM5の部分を使用するポートに合わせて変更
SERIAL_PORT = 'com7'
BAUDRATE = 115200

class SBUSControllerMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SBUS Controller & Monitor")
        self.root.geometry("1200x750")
        
        # シリアル通信設定
        self.serial_port = SERIAL_PORT
        self.baudrate = BAUDRATE
        self.ser = None
        self.running = True
        
        # コントローラーデータ
        self.control = [1000] * 16
        # スイッチ系チャンネル（CH5, CH7-CH16）を初期値500に設定（switch_states=1 に対応）
        self.control[4] = 500   # CH5
        for i in range(6, 16):  # CH7-CH16
            self.control[i] = 500
        self.data = [0] * 25
        self.switch_states = [1] * 11  # [0]=CH5, [1..6]=CH7-CH12, [7..10]=CH13-CH16
        self._toggle_key_pressed = set()
        
        # チャンネル名
        self.channel_names = [
            "CH1  エルロン（左）",    "CH2  ラダー",
            "CH3  スロットル",       "CH4  エレベーター",
            "CH5  投下装置 (Key:0)",  "CH6  エルロン（右）",
            "CH7  自動操縦 (Key:1)",  "CH8  ミッション選択 (Key:2)",
            "CH9  自動離着陸 (Key:3)", "CH10 安全装置 (Key:4)",
            "CH11 離陸前テスト (Key:5)", "CH12 離陸後テスト (Key:6)",
            "CH13 (Key:7)",            "CH14 (Key:8)",
            "CH15 (Key:9)",            "CH16 (Key:-)"
        ]
        
        # GUI要素の初期化
        self.create_widgets()
        
        # シリアル接続
        self.connect_serial()
        
        # スレッド開始
        self.serial_thread = threading.Thread(target=self.main_loop, daemon=True)
        self.serial_thread.start()
        
        self.keyboard_thread = threading.Thread(target=self.check_keyboard, daemon=True)
        self.keyboard_thread.start()
        
        self.serial_receive_thread = threading.Thread(target=self.serial_receive_loop, daemon=True)
        self.serial_receive_thread.start()
        
        # ウィンドウを閉じるときの処理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_widgets(self):
        # タイトル
        title_label = ttk.Label(self.root, text="SBUS Controller & Monitor", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(8, 2))
        
        # ステータス表示
        self.status_var = tk.StringVar(value="Status: Ready")
        status_label = ttk.Label(self.root, textvariable=self.status_var, font=("Arial", 10))
        status_label.pack(pady=(0, 4))
        
        # 左右分割ペイン
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        
        # 左ペイン: コントローラーステータス
        left_frame = ttk.LabelFrame(paned, text="Controller Status")
        paned.add(left_frame, weight=1)
        self.create_controller_tab(left_frame)
        
        # 右ペイン: モニター
        right_frame = ttk.LabelFrame(paned, text="Monitor")
        paned.add(right_frame, weight=1)
        self.create_monitor_tab(right_frame)
        
        # ボタン行
        control_frame = ttk.Frame(self.root)
        control_frame.pack(pady=6)
        
        disconnect_btn = ttk.Button(control_frame, text="Disconnect", command=self.disconnect_serial)
        disconnect_btn.pack(side=tk.LEFT, padx=5)
        
        guide_btn = ttk.Button(control_frame, text="Key Guide", command=self.show_guide_popup)
        guide_btn.pack(side=tk.LEFT, padx=5)
        
        exit_btn = ttk.Button(control_frame, text="Exit", command=self.on_closing)
        exit_btn.pack(side=tk.LEFT, padx=5)
    
    def create_controller_tab(self, parent):
        """コントローラーステータス表示タブ"""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # キャンバスとスクロールバー
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
        self.controller_labels = {}
        for i in range(16):
            ch_frame = ttk.Frame(scrollable_frame)
            ch_frame.pack(fill=tk.X, padx=5, pady=3)
            
            ch_name = ttk.Label(ch_frame, text=self.channel_names[i], width=25, font=("Arial", 10))
            ch_name.pack(side=tk.LEFT)
            
            # プログレスバー
            progress = ttk.Progressbar(ch_frame, length=250, mode='determinate')
            progress.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            
            # 値表示ラベル
            value_label = ttk.Label(ch_frame, text="1000", width=8, font=("Arial", 10))
            value_label.pack(side=tk.LEFT)
            
            self.controller_labels[i] = {
                'label': value_label,
                'progress': progress
            }
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    def create_monitor_tab(self, parent):
        """モニタータブ"""
        # サブタブを作成
        sub_notebook = ttk.Notebook(parent)
        sub_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # HEXデータタブ
        hex_frame = ttk.Frame(sub_notebook)
        sub_notebook.add(hex_frame, text="HEX Data")
        
        hex_label = ttk.Label(hex_frame, text="Received SBUS Data (HEX):", font=("Arial", 10))
        hex_label.pack(pady=5)
        
        self.hex_text = tk.Text(hex_frame, height=8, width=100, font=("Courier", 8), takefocus=False)
        self.hex_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.hex_text.bind("<Key>", lambda e: "break")
        
        hex_clear_btn = ttk.Button(hex_frame, text="Clear Log", command=self.clear_log)
        hex_clear_btn.pack(pady=5)
        
        # テキストデータタブ
        text_frame = ttk.Frame(sub_notebook)
        sub_notebook.add(text_frame, text="Text Output")
        
        text_label = ttk.Label(text_frame, text="Received Text Data:", font=("Arial", 10))
        text_label.pack(pady=5)
        
        self.monitor_text = tk.Text(text_frame, height=8, width=100, font=("Courier", 9), takefocus=False)
        self.monitor_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.monitor_text.bind("<Key>", lambda e: "break")
        
        text_clear_btn = ttk.Button(text_frame, text="Clear Log", command=self.clear_text_log)
        text_clear_btn.pack(pady=5)
    
    def create_guide_tab(self, parent):
        """操作ガイドタブ"""
        guide_text = """
操作ガイド
━━━━━━━━━━━━━━━━━━━━━━━━━━

【プロポスティック操作】
  エルロン（左） (CH1) : A / D キー
  ラダー     (CH2) : J / L キー
  スロットル (CH3) : W / S キー
  エレベーター (CH4) : I / K キー

【切り替え操作】
  投下装置   (CH5)  : 0 キー (3段階: 500/1000/1500)
  エルロン（右） (CH6)  : Q / E キー

【3段階切り替え】
  自動操縦     (CH7)  : 1 キー (500/1000/1500)
  ミッション選択   (CH8)  : 2 キー (500/1000/1500)
  自動離着陸   (CH9)  : 3 キー (500/1000/1500)
  安全装置     (CH10) : 4 キー (500/1000/1500)
  離陸前テスト (CH11) : 5 キー (500/1000/1500)
  離陸後テスト (CH12) : 6 キー (500/1000/1500)
  （未割り当）  (CH13) : 7 キー (500/1000/1500)
  （未割り当）  (CH14) : 8 キー (500/1000/1500)
  （未割り当）  (CH15) : 9 キー (500/1000/1500)
  （未割り当）  (CH16) : - キー (500/1000/1500)

【その他】
  リセット      : R キー (すべてニュートラル)

各プログレスバーはリアルタイムで値を表示します。
        """
        
        text_widget = tk.Text(parent, wrap=tk.WORD, font=("Courier", 10))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert(tk.END, guide_text)
        text_widget.config(state=tk.DISABLED)

    def show_guide_popup(self):
        """操作ガイドをポップアップウィンドウで表示"""
        popup = tk.Toplevel(self.root)
        popup.title("Key Guide")
        popup.geometry("420x480")
        popup.resizable(False, False)
        self.create_guide_tab(popup)
    
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
    
    def clear_text_log(self):
        self.monitor_text.delete(1.0, tk.END)
    
    def convert_data(self):
        """SBUSデータに変換 - 16チャンネル対応"""
        channels = self.control  # 16チャンネルすべてを使用
        
        self.data[0] = 0x0F  # ヘッダー
        
        # CH1-16を11ビットずつエンコード（合計22バイト）
        # 各チャンネルは11ビ（1024中央値で0-2047の範囲）
        self.data[1] = (channels[0] & 0xFF)
        self.data[2] = ((channels[0] >> 8) & 0x07) | ((channels[1] & 0x1F) << 3)
        self.data[3] = ((channels[1] >> 5) & 0x3F) | ((channels[2] & 0x03) << 6)
        self.data[4] = (channels[2] >> 2) & 0xFF
        self.data[5] = ((channels[2] >> 10) & 0x01) | ((channels[3] & 0x7F) << 1)
        self.data[6] = ((channels[3] >> 7) & 0x0F) | ((channels[4] & 0x0F) << 4)
        self.data[7] = ((channels[4] >> 4) & 0x7F) | ((channels[5] & 0x01) << 7)
        self.data[8] = (channels[5] >> 1) & 0xFF
        self.data[9] = ((channels[5] >> 9) & 0x03) | ((channels[6] & 0x3F) << 2)
        self.data[10] = ((channels[6] >> 6) & 0x1F) | ((channels[7] & 0x07) << 5)
        self.data[11] = (channels[7] >> 3) & 0xFF
        self.data[12] = (channels[8] & 0xFF)
        self.data[13] = ((channels[8] >> 8) & 0x07) | ((channels[9] & 0x1F) << 3)
        self.data[14] = ((channels[9] >> 5) & 0x3F) | ((channels[10] & 0x03) << 6)
        self.data[15] = (channels[10] >> 2) & 0xFF
        self.data[16] = ((channels[10] >> 10) & 0x01) | ((channels[11] & 0x7F) << 1)
        self.data[17] = ((channels[11] >> 7) & 0x0F) | ((channels[12] & 0x0F) << 4)
        self.data[18] = ((channels[12] >> 4) & 0x7F) | ((channels[13] & 0x01) << 7)
        self.data[19] = (channels[13] >> 1) & 0xFF
        self.data[20] = ((channels[13] >> 9) & 0x03) | ((channels[14] & 0x3F) << 2)
        self.data[21] = ((channels[14] >> 6) & 0x1F) | ((channels[15] & 0x07) << 5)
        self.data[22] = (channels[15] >> 3) & 0xFF
        
        self.data[23] = 0x00  # フラグバイト（bit7:failsafe, bit6:ch17, bit5:ch18...）
        self.data[24] = 0x00  # フッター
    
    def check_keyboard(self):
        """キーボード入力チェック"""
        # トグルキーマッピング: {key: (switch_statesインデックス, controlインデックス)}
        toggle_map = {
            '0': (0, 4),
            '1': (1, 6),  '2': (2, 7),  '3': (3, 8),  '4': (4, 9),
            '5': (5, 10), '6': (6, 11), '7': (7, 12), '8': (8, 13),
            '9': (9, 14), '-': (10, 15),
        }

        while self.running:
            try:
                # アナログチャンネル（ポーリング）
                step = 10
                if keyboard.is_pressed('j'):
                    if self.control[0] < 1680: self.control[0] += step
                elif keyboard.is_pressed('l'):
                    if self.control[0] > 360: self.control[0] -= step

                if keyboard.is_pressed('a'):
                    if self.control[1] < 1680: self.control[1] += step
                elif keyboard.is_pressed('d'):
                    if self.control[1] > 360: self.control[1] -= step

                if keyboard.is_pressed('w'):
                    if self.control[2] < 1680: self.control[2] += step
                elif keyboard.is_pressed('s'):
                    if self.control[2] > 360: self.control[2] -= step

                if keyboard.is_pressed('i'):
                    if self.control[3] < 1680: self.control[3] += step
                elif keyboard.is_pressed('k'):
                    if self.control[3] > 360: self.control[3] -= step

                # エルロン2（CH6）を360～1680範囲に正規化
                if keyboard.is_pressed('q'):
                    self.control[5] = 360   # 設定倥をQキー用に調整
                elif keyboard.is_pressed('e'):
                    self.control[5] = 1680  # 設定倥をEキー用に調整

                # トグルキー（状態追跡ベースデバウンス - time.sleep不要）
                for key, (sw_idx, ctrl_idx) in toggle_map.items():
                    if keyboard.is_pressed(key):
                        if key not in self._toggle_key_pressed:
                            self._toggle_key_pressed.add(key)
                            self.switch_states[sw_idx] = (self.switch_states[sw_idx] % 3) + 1
                            self.control[ctrl_idx] = [500, 1000, 1500][self.switch_states[sw_idx] - 1]
                    else:
                        self._toggle_key_pressed.discard(key)

                # リセット
                if keyboard.is_pressed('R'):
                    if 'R' not in self._toggle_key_pressed:
                        self._toggle_key_pressed.add('R')
                        self.control = [1000] * 16
                        self.control[4] = 500
                        for _i in range(6, 16):
                            self.control[_i] = 500
                        self.switch_states = [1] * 11
                else:
                    self._toggle_key_pressed.discard('R')

                time.sleep(0.005)  # 5msポーリング（応答性向上）
            except Exception as e:
                print(f"Keyboard error: {e}")
    
    def decode_sbus_data(self, data):
        """SBUSデータをデコード"""
        if len(data) < 25:
            return None
        
        channels = []
        channels.append(((data[1] | (data[2] << 8)) & 0x07FF))
        channels.append((((data[2] >> 3) | (data[3] << 5)) & 0x07FF))
        channels.append((((data[3] >> 6) | (data[4] << 2) | (data[5] << 10)) & 0x07FF))
        channels.append((((data[5] >> 1) | (data[6] << 7)) & 0x07FF))
        channels.append((((data[6] >> 4) | (data[7] << 4)) & 0x07FF))
        channels.append((((data[7] >> 7) | (data[8] << 1) | (data[9] << 9)) & 0x07FF))
        channels.append((((data[9] >> 2) | (data[10] << 6)) & 0x07FF))
        channels.append((((data[10] >> 5) | (data[11] << 3)) & 0x07FF))
        channels.append(((data[12] | (data[13] << 8)) & 0x07FF))
        channels.append((((data[13] >> 3) | (data[14] << 5)) & 0x07FF))
        channels.append((((data[14] >> 6) | (data[15] << 2) | (data[16] << 10)) & 0x07FF))
        channels.append((((data[16] >> 1) | (data[17] << 7)) & 0x07FF))
        
        return channels[:12]
    
    def update_gui(self):
        """GUI更新"""
        for i in range(16):
            value = self.control[i]
            self.controller_labels[i]['label'].config(text=str(value))
            # プログレスバーの値を0-100に正規化（500-1500の範囲）
            normalized_value = (value - 500) / 10
            self.controller_labels[i]['progress']['value'] = normalized_value
    
    def serial_receive_loop(self):
        """シリアル受信スレッド - テキストデータを読み込み"""
        text_buffer = ""
        while self.running:
            try:
                if self.ser and self.ser.is_open and self.ser.in_waiting:
                    # 1バイト読み込む
                    byte_data = self.ser.read(1)
                    if byte_data:
                        char = byte_data.decode('utf-8', errors='ignore')
                        
                        # \n（LF）で行が完成
                        if char == '\n':
                            if text_buffer.strip():
                                self.monitor_text.insert(tk.END, text_buffer + '\n')
                                self.monitor_text.see(tk.END)
                            text_buffer = ""
                        # \r（CR）は無視
                        elif char == '\r':
                            pass
                        # その他の文字をバッファに追加
                        else:
                            text_buffer += char
                else:
                    time.sleep(0.01)
            except Exception as e:
                print(f"Serial receive error: {e}")
                time.sleep(0.1)
    
    def main_loop(self):
        """メインループ"""
        while self.running:
            try:
                # データ変換
                self.convert_data()
                
                # シリアル送信
                if self.ser and self.ser.is_open:
                    self.ser.write(bytes(self.data))
                
                # GUI更新
                self.update_gui()
                self.root.update_idletasks()
                
                time.sleep(0.01)
            except Exception as e:
                print(f"Main loop error: {e}")
    
    def on_closing(self):
        self.running = False
        keyboard.unhook_all()
        self.disconnect_serial()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SBUSControllerMonitorApp(root)
    root.mainloop()
