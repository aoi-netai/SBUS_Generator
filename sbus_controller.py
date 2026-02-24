import serial
import time
import keyboard

# COM5の部分を使用するポートに合わせて変更
ser = serial.Serial('com7', baudrate=115200, parity=serial.PARITY_NONE, stopbits=1, timeout=1)

# 送信データの初期化
data = [0] * 25 
control = [0] * 16

# 送信データの入力
# プロポスティック（ラジコン飛行機モード）
control[0] = 1000  # CH1: ヨー
control[1] = 1000  # CH2: ロール
control[2] = 1000  # CH3: スロットル
control[3] = 1000  # CH4: ピッチ
control[4] = 500   # CH5: 投下装置（スイッチ初期値 500）
control[5] = 1000  # CH6: エルロン2

# 3段階切り替えチャンネル（スイッチ初期値 500 = switch_states=1 に対応）
control[6] = 500   # CH7: キー1
control[7] = 500   # CH8: キー2
control[8] = 500   # CH9: キー3
control[9] = 500   # CH10: キー4
control[10] = 500  # CH11: キー5
control[11] = 500  # CH12: キー6
control[12] = 500  # CH13: キー7
control[13] = 500  # CH14: キー8
control[14] = 500  # CH15: キー9
control[15] = 500  # CH16: キー-

# 各チャンネルの3段階切り替え状態を管理
# [0]=CH5, [1]=CH7, [2]=CH8, ..., [6]=CH12, [7]=CH13, ..., [10]=CH16
switch_states = [1] * 11  # キー状態（1=500, 2=1000, 3=1500）

# トグルキーの押下状態追跡（デバウンス用）
toggle_key_pressed = set()


# SBUSのデータ
# 11bitの符号なし整数をdataに格納

def convert_data():
    """SBUSデータに変換 - 16チャンネル対応"""
    channels = control  # 16チャンネルすべてを使用
    
    data[0] = 0x0F  # ヘッダー
    
    # CH1-16を11ビットずつエンコード（合計22バイト）
    data[1] = (channels[0] & 0xFF)
    data[2] = ((channels[0] >> 8) & 0x07) | ((channels[1] & 0x1F) << 3)
    data[3] = ((channels[1] >> 5) & 0x3F) | ((channels[2] & 0x03) << 6)
    data[4] = (channels[2] >> 2) & 0xFF
    data[5] = ((channels[2] >> 10) & 0x01) | ((channels[3] & 0x7F) << 1)
    data[6] = ((channels[3] >> 7) & 0x0F) | ((channels[4] & 0x0F) << 4)
    data[7] = ((channels[4] >> 4) & 0x7F) | ((channels[5] & 0x01) << 7)
    data[8] = (channels[5] >> 1) & 0xFF
    data[9] = ((channels[5] >> 9) & 0x03) | ((channels[6] & 0x3F) << 2)
    data[10] = ((channels[6] >> 6) & 0x1F) | ((channels[7] & 0x07) << 5)
    data[11] = (channels[7] >> 3) & 0xFF
    data[12] = (channels[8] & 0xFF)
    data[13] = ((channels[8] >> 8) & 0x07) | ((channels[9] & 0x1F) << 3)
    data[14] = ((channels[9] >> 5) & 0x3F) | ((channels[10] & 0x03) << 6)
    data[15] = (channels[10] >> 2) & 0xFF
    data[16] = ((channels[10] >> 10) & 0x01) | ((channels[11] & 0x7F) << 1)
    data[17] = ((channels[11] >> 7) & 0x0F) | ((channels[12] & 0x0F) << 4)
    data[18] = ((channels[12] >> 4) & 0x7F) | ((channels[13] & 0x01) << 7)
    data[19] = (channels[13] >> 1) & 0xFF
    data[20] = ((channels[13] >> 9) & 0x03) | ((channels[14] & 0x3F) << 2)
    data[21] = ((channels[14] >> 6) & 0x1F) | ((channels[15] & 0x07) << 5)
    data[22] = (channels[15] >> 3) & 0xFF
    
    data[23] = 0x00  # フラグバイト
    data[24] = 0x00  # フッター

def CheckKeybord():
    global toggle_key_pressed

    # ヨー（CH1）
    if keyboard.is_pressed('j'):
        if(control[0] < 1680):
            control[0] += 10
            print("CH1 (Yaw):" + str(control[0]))
    elif keyboard.is_pressed('l'):
        if(control[0] > 360):
            control[0] -= 10
            print("CH1 (Yaw):" + str(control[0]))

    # ロール（CH2）
    if keyboard.is_pressed('a'):
        if(control[1] < 1680):
            control[1] += 10
            print("CH2 (Roll):" + str(control[1]))
    elif keyboard.is_pressed('d'):
        if(control[1] > 360):
            control[1] -= 10
            print("CH2 (Roll):" + str(control[1]))

    # スロットル（CH3）
    if keyboard.is_pressed('w'):
        if(control[2] < 1680):
            control[2] += 10
            print("CH3 (Throttle):" + str(control[2]))
    elif keyboard.is_pressed('s'):
        if(control[2] > 360):
            control[2] -= 10
            print("CH3 (Throttle):" + str(control[2]))

    # ピッチ（CH4）
    if keyboard.is_pressed('i'):
        if(control[3] < 1680):
            control[3] += 10
            print("CH4 (Pitch):" + str(control[3]))
    elif keyboard.is_pressed('k'):
        if(control[3] > 360):
            control[3] -= 10
            print("CH4 (Pitch):" + str(control[3]))

    # トグルキー処理（状態追跡ベースのデバウンス - time.sleep不要）
    # {キー: (switch_statesインデックス, controlインデックス, チャンネル名)}
    toggle_map = {
        '0': (0, 4,  'CH5 (Drop Device)'),
        '1': (1, 6,  'CH7 (Key1)'),
        '2': (2, 7,  'CH8 (Key2)'),
        '3': (3, 8,  'CH9 (Key3)'),
        '4': (4, 9,  'CH10 (Key4)'),
        '5': (5, 10, 'CH11 (Key5)'),
        '6': (6, 11, 'CH12 (Key6)'),
        '7': (7, 12, 'CH13 (Key7)'),
        '8': (8, 13, 'CH14 (Key8)'),
        '9': (9, 14, 'CH15 (Key9)'),
        '-': (10, 15, 'CH16 (Key-)'),
    }
    for key, (sw_idx, ctrl_idx, ch_name) in toggle_map.items():
        if keyboard.is_pressed(key):
            if key not in toggle_key_pressed:
                toggle_key_pressed.add(key)
                switch_states[sw_idx] = (switch_states[sw_idx] % 3) + 1
                val = [500, 1000, 1500][switch_states[sw_idx] - 1]
                control[ctrl_idx] = val
                print(f"{ch_name}: {val}")
        else:
            toggle_key_pressed.discard(key)

    # エルロン2（CH6） - qとeで直接値設定を360～1680範囲に正規化
    if keyboard.is_pressed('q'):
        control[5] = 360
        print("CH6 (Aileron 2): 360")
    elif keyboard.is_pressed('e'):
        control[5] = 1680
        print("CH6 (Aileron 2): 1680")

    # リセット（Rキー）
    if keyboard.is_pressed('R'):
        if 'R' not in toggle_key_pressed:
            toggle_key_pressed.add('R')
            for i in range(4):   # CH1-CH4: 1000
                control[i] = 1000
            control[4] = 500     # CH5
            control[5] = 1000    # CH6
            for i in range(6, 16):  # CH7-CH16: 500
                control[i] = 500
            for i in range(11):
                switch_states[i] = 1
            print("Reset - All channels to 1000")
    else:
        toggle_key_pressed.discard('R')

while(1):

    CheckKeybord() # キーボードの入力を確認

    convert_data() # データの変換

    ser.write(data) # 送信
    time.sleep(0.002) # 送信間隔（SBUS: 2ms）
