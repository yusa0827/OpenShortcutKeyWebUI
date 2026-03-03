# f13_f16_gui.py
import tkinter as tk
import keyboard

def send_key(key_name: str):
    # クリックしたら指定キーを送信
    keyboard.send(key_name)
    status_var.set(f"Sent {key_name.upper()}")

root = tk.Tk()
root.title("F13-F16 Sender")
root.resizable(False, False)

frame = tk.Frame(root, padx=12, pady=12)
frame.pack()

status_var = tk.StringVar(value="Ready")

buttons = [
    ("F13", "f13"),
    ("F14", "f14"),
    ("F15", "f15"),
    ("F16", "f16"),
]

for label, key_name in buttons:
    btn = tk.Button(
        frame,
        text=label,
        width=10,
        height=2,
        command=lambda k=key_name: send_key(k),
    )
    btn.pack(side="left", padx=6)

status = tk.Label(root, textvariable=status_var, padx=12, pady=6, anchor="w")
status.pack(fill="x")

root.mainloop()