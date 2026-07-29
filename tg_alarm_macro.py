#!/usr/bin/env python3

import pyautogui
import win32gui
import win32con
import time
import cv2
import numpy as np
import mss
import json
import os
import sys
import shutil

pyautogui.FAILSAFE = True

TARGET_NAME = "Имя пользователя"
CHECK_INTERVAL = 10
RING_SECONDS = 8
CHANGE_THRESHOLD = 15.0
CALIBRATE_FILE = "tg_alarm_macro_calibrate.json"

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def find_telegram():
    def cb(hwnd, results):
        title = win32gui.GetWindowText(hwnd)
        if title == "Telegram":
            results.append(hwnd)
    results = []
    win32gui.EnumWindows(cb, results)
    if results:
        return results[0]
    def cb2(hwnd, results):
        title = win32gui.GetWindowText(hwnd)
        if "Telegram" in title and title.strip():
            results.append(hwnd)
    results2 = []
    win32gui.EnumWindows(cb2, results2)
    return results2[0] if results2 else None

def focus_window(hwnd):
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.5)

def get_window_rect(hwnd):
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    return left, top, right - left, bottom - top

def screenshot_rect(left, top, width, height):
    with mss.mss() as sct:
        monitor = {"left": int(left), "top": int(top), "width": int(width), "height": int(height)}
        img = sct.grab(monitor)
        return np.array(img)

def take_msg_screenshot(hwnd):
    left, top, w, h = get_window_rect(hwnd)
    msg_top = top + int(h * 0.25)
    msg_h = int(h * 0.55)
    return screenshot_rect(left, msg_top, w, msg_h)

def detect_new_messages(img1, img2):
    h = min(img1.shape[0], img2.shape[0])
    gray1 = cv2.cvtColor(img1[:h, :, :3], cv2.COLOR_BGRA2GRAY)
    gray2 = cv2.cvtColor(img2[:h, :, :3], cv2.COLOR_BGRA2GRAY)
    diff = cv2.absdiff(gray1, gray2)
    mean_diff = np.mean(diff)
    return mean_diff, mean_diff > CHANGE_THRESHOLD

def calibrate_buttons():
    hwnd = find_telegram()
    if not hwnd:
        print("Telegram Desktop ne nayden. Zapusti Telegram.")
        return None
    focus_window(hwnd)
    config = {}
    left, top, w, h = get_window_rect(hwnd)
    log(f"Okno Telegram: ({left}, {top}) {w}x{h}")
    print()
    print("=== KALIBRATSIYA KNOPOK ===")
    print("Shag 1: Navedi myshku na KNOPKU ZVONKA (ikona telefona vverhu) i nazhmi Enter")
    input()
    config["call_x"], config["call_y"] = pyautogui.position()
    log(f"Knopka zvonka: ({config['call_x']}, {config['call_y']})")
    print()
    print("Shag 2: Zaplani na korotkij zvonok cherez Telegram (chtoby poyavilos okno zvonka)")
    print("         Navedi myshku na KNOPKU OTBOYA (krasnaya trubka) i nazhmi Enter")
    input()
    config["hangup_x"], config["hangup_y"] = pyautogui.position()
    log(f"Knopka otboya: ({config['hangup_x']}, {config['hangup_y']})")
    with open(CALIBRATE_FILE, "w") as f:
        json.dump(config, f, indent=2)
    log(f"Kalibratsiya sohranena v {CALIBRATE_FILE}")
    return config

def load_calibration():
    if os.path.exists(CALIBRATE_FILE):
        with open(CALIBRATE_FILE) as f:
            return json.load(f)
    return None

def navigate_to_chat(hwnd, name):
    focus_window(hwnd)
    time.sleep(1)
    log(f"Ishem chat '{name}'...")
    pyautogui.hotkey("ctrl", "k")
    time.sleep(0.5)
    pyautogui.write(name, interval=0.05)
    time.sleep(0.5)
    pyautogui.press("enter")
    time.sleep(1)
    pyautogui.press("escape")
    time.sleep(0.3)

def alarm():
    print()
    for _ in range(15):
        print("\a", end="", flush=True)
        time.sleep(0.15)
    print()

def main():
    print("=== TG Alarm Macro ===")
    print()
    if len(sys.argv) > 1 and sys.argv[1] == "--calibrate":
        calibrate_buttons()
        return
    hwnd = find_telegram()
    if not hwnd:
        print("Telegram Desktop ne nayden. Zapusti Telegram.")
        input("Nazhmi Enter dlya vyhoda...")
        return
    focus_window(hwnd)
    log(f"Okno: '{win32gui.GetWindowText(hwnd)}'")
    navigate_to_chat(hwnd, TARGET_NAME)
    config = load_calibration()
    if not config:
        print()
        print("Nuzhna kalibratsiya knopok.")
        print("Zapusti skript s flagom --calibrate:")
        print(f"  python tg_alarm_macro.py --calibrate")
        print()
        ans = input("Sdelat kalibratsiyu seychas? (y/n): ")
        if ans.lower() == "y":
            config = calibrate_buttons()
            if not config:
                return
        else:
            return
    print()
    print("Ubedis, chto otkryt nuzhny chat.")
    print("Skript nachnet cherez 3 sekundy...")
    time.sleep(3)
    log("Delayu bazovy snimok...")
    baseline = take_msg_screenshot(hwnd)
    log(f"Razmer: {baseline.shape[1]}x{baseline.shape[0]}")
    cycle = 0
    try:
        while True:
            cycle += 1
            if cycle > 1:
                log(f"Ozhidanie {CHECK_INTERVAL} sek...")
                for i in range(CHECK_INTERVAL):
                    time.sleep(1)
            current = take_msg_screenshot(hwnd)
            diff_val, has_changed = detect_new_messages(baseline, current)
            log(f"Proverka #{cycle} (izmenenie: {diff_val:.1f})")
            if has_changed:
                log(">>>> NOVOE SOOBSHCHENIE! <<<<")
                alarm()
                print("Alarm srabotal! Nazhmi Ctrl+C dlya vyhoda.")
                time.sleep(10)
                log("Prodolzhaem monitoring...")
                baseline = take_msg_screenshot(hwnd)
                continue
            log("Zvonok...")
            focus_window(hwnd)
            time.sleep(0.3)
            pyautogui.click(config["call_x"], config["call_y"])
            time.sleep(RING_SECONDS)
            pyautogui.click(config["hangup_x"], config["hangup_y"])
            time.sleep(0.5)
            focus_window(hwnd)
            time.sleep(0.5)
            baseline = take_msg_screenshot(hwnd)
    except KeyboardInterrupt:
        print()
        log("Ostanovlen polzovatelem.")

if __name__ == "__main__":
    main()
