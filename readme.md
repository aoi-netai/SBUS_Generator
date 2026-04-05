# SBUS_Generator

Pythonでシリアル通信経由のSBUS送信とモニタ表示を行うツールです。  
現在のメイン実装は `main.py`（送信＋モニタGUI）です。

## 実行環境

- Python 3.x
- pyserial 3.5
- keyboard 0.13.5
- tkinter（標準ライブラリ）

## セットアップ

```bash
pip install -r requirements.txt
```

## COMポートの設定方法

使用するCOMポートは、実行するスクリプト内の設定値を編集します。

- `main.py`  
  `SERIAL_PORT = 'com7'`
- `sbus_controller.py`  
  `serial.Serial('com7', ...)`
- `sbus_monitor.py`  
  `self.serial_port = 'com7'`

環境に合わせて `com7` を `COM3` / `COM5` などに変更してください（Windows想定）。

### 現在のシリアル設定（実装準拠）

- Baudrate: `115200`
- Parity: `NONE`
- Stopbits: `1`
- Timeout: `1`

## 操作方法（main.py）

```bash
python main.py
```

### キー操作

- `J / L` : CH1（エルロン左）
- `A / D` : CH2（ラダー）
- `W / S` : CH3（スロットル）
- `I / K` : CH4（エレベーター）
- `Q / E` : CH6（エルロン右）を低/高に切替
- `0` : CH5 を3段階切替（500/1000/1500）
- `1`〜`9`, `-` : CH7〜CH16 を3段階切替（500/1000/1500）
- `R` : 全チャンネルを初期値へリセット

### GUI操作

- `Disconnect` : シリアル切断
- `Key Guide` : キー操作ガイド表示
- `Exit` : 終了

## 補足

- `sbus_controller.py` はキーボード操作でSBUS送信するシンプル版です。
- `sbus_monitor.py` はSBUS受信表示用のモニタです。

> [!WARNING]
> 実際の受信機との違いとして、信号反転を行っていません。必要に応じて外部回路等で対応してください。
