
import sys
import os
import json
import time
import random
import logging
import threading
import subprocess
import importlib.util
import ctypes
from pathlib import Path
from ctypes import wintypes
import tkinter as tk
from tkinter import filedialog, messagebox

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "typeflow.log"
SETTINGS_FILE = BASE_DIR / "settings.json"
HISTORY_FILE = BASE_DIR / "history.json"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

PACKAGES = {
    "customtkinter": "customtkinter",
    "pyautogui": "pyautogui",
    "keyboard": "keyboard"
}


def install_packages():
    missing = [
        package for module, package in PACKAGES.items()
        if importlib.util.find_spec(module) is None
    ]

    if not missing:
        return

    root = tk.Tk()
    root.withdraw()

    messagebox.showinfo(
        "TypeFlow",
        "Trwa instalowanie wymaganych bibliotek."
    )

    root.destroy()

    try:
        subprocess.check_call([
            sys.executable, "-m", "pip",
            "install", *missing
        ])
        os.execv(sys.executable, [sys.executable] + sys.argv)

    except Exception:
        logging.exception("Instalacja bibliotek nie powiodła się")
        messagebox.showerror(
            "Błąd",
            f"Nie udało się zainstalować bibliotek.\n{LOG_FILE}"
        )
        sys.exit(1)


install_packages()

import customtkinter as ctk
import pyautogui
import keyboard


ULONG_PTR = ctypes.c_size_t
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR)
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR)
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD)
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT)
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION)
    ]


user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.SendInput.argtypes = [
    wintypes.UINT,
    ctypes.POINTER(INPUT),
    ctypes.c_int
]
user32.SendInput.restype = wintypes.UINT


def send_unicode_char(char):
    encoded = char.encode("utf-16-le")
    units = [
        encoded[i] | (encoded[i + 1] << 8)
        for i in range(0, len(encoded), 2)
    ]

    for unit in units:
        inputs = (INPUT * 2)()

        inputs[0].type = 1
        inputs[0].ki = KEYBDINPUT(
            0, unit, KEYEVENTF_UNICODE, 0, 0
        )

        inputs[1].type = 1
        inputs[1].ki = KEYBDINPUT(
            0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0
        )

        if user32.SendInput(
            2, inputs, ctypes.sizeof(INPUT)
        ) != 2:
            raise ctypes.WinError(ctypes.get_last_error())


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
    except Exception:
        logging.exception("Nie udało się zapisać ustawień")


class TypeFlow(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("TypeFlow 4.0")
        self.geometry("1100x760")
        self.minsize(650, 520)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.settings = load_json(SETTINGS_FILE, {})
        self.history = load_json(HISTORY_FILE, [])

        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()

        self.running = False
        self.typed_chars = 0
        self.total_chars = 0
        self.worker = None

        self.speed = tk.IntVar(
            value=self.settings.get("speed", 240)
        )
        self.typo_rate = tk.IntVar(
            value=self.settings.get("typo_rate", 3)
        )
        self.scale = tk.DoubleVar(
            value=self.settings.get("scale", 1.0)
        )

        self.typos_enabled = tk.BooleanVar(value=True)
        self.enter_enabled = tk.BooleanVar(value=True)
        self.random_pauses = tk.BooleanVar(value=True)

        self.delay = 5

        self.build_ui()
        self.apply_scale()
        self.update_stats()

        keyboard.add_hotkey("F8", self.stop_typing)
        keyboard.add_hotkey("F9", self.toggle_pause)

        self.protocol("WM_DELETE_WINDOW", self.close_app)

    def build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=16)
        header.grid(
            row=0, column=0,
            padx=15, pady=12,
            sticky="ew"
        )

        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="TYPEFLOW",
            font=ctk.CTkFont(size=28, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=18, pady=12)

        ctk.CTkButton(
            header,
            text="Wczytaj TXT",
            command=self.load_txt,
            width=110
        ).grid(row=0, column=1, padx=5)

        ctk.CTkButton(
            header,
            text="Zapisz TXT",
            command=self.save_txt,
            width=110
        ).grid(row=0, column=2, padx=5)

        ctk.CTkButton(
            header,
            text="Kopiuj",
            command=self.copy_text,
            width=90
        ).grid(row=0, column=3, padx=12)

        main = ctk.CTkFrame(self, corner_radius=16)
        main.grid(
            row=1, column=0,
            padx=15, pady=5,
            sticky="nsew"
        )

        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)
        main.grid_rowconfigure(0, weight=1)

        editor = ctk.CTkFrame(main, fg_color="transparent")
        editor.grid(
            row=0, column=0,
            padx=12, pady=12,
            sticky="nsew"
        )

        editor.grid_columnconfigure(0, weight=1)
        editor.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            editor,
            text="Edytor tekstu",
            font=ctk.CTkFont(size=17, weight="bold")
        ).grid(row=0, column=0, sticky="w", pady=8)

        self.textbox = ctk.CTkTextbox(
            editor,
            wrap="word",
            font=ctk.CTkFont(size=14),
            corner_radius=12
        )
        self.textbox.grid(
            row=1, column=0,
            sticky="nsew"
        )

        self.textbox.bind("<KeyRelease>", self.update_stats)

        settings = ctk.CTkScrollableFrame(
            main,
            corner_radius=12
        )
        settings.grid(
            row=0, column=1,
            padx=10, pady=12,
            sticky="nsew"
        )

        settings.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            settings,
            text="USTAWIENIA",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", padx=12, pady=12)

        self.speed_label = ctk.CTkLabel(settings, text="")
        self.speed_label.pack(anchor="w", padx=12)

        ctk.CTkSlider(
            settings,
            from_=30,
            to=900,
            variable=self.speed,
            command=self.update_speed
        ).pack(fill="x", padx=12, pady=8)

        preset_frame = ctk.CTkFrame(
            settings,
            fg_color="transparent"
        )
        preset_frame.pack(fill="x", padx=5)

        for name, value in [
            ("Wolno", 90),
            ("Normalnie", 240),
            ("Szybko", 450),
            ("Turbo", 750)
        ]:
            ctk.CTkButton(
                preset_frame,
                text=name,
                command=lambda v=value: self.set_speed(v),
                height=30
            ).pack(fill="x", padx=5, pady=3)

        ctk.CTkLabel(
            settings,
            text="Skala interfejsu"
        ).pack(anchor="w", padx=12, pady=(18, 0))

        ctk.CTkSlider(
            settings,
            from_=0.75,
            to=1.35,
            variable=self.scale,
            command=self.change_scale
        ).pack(fill="x", padx=12, pady=8)

        self.scale_label = ctk.CTkLabel(settings, text="")
        self.scale_label.pack(anchor="w", padx=12)

        ctk.CTkLabel(
            settings,
            text="Szansa na literówkę"
        ).pack(anchor="w", padx=12, pady=(18, 0))

        ctk.CTkSlider(
            settings,
            from_=0,
            to=10,
            number_of_steps=10,
            variable=self.typo_rate,
            command=lambda v: self.save_settings()
        ).pack(fill="x", padx=12, pady=8)

        ctk.CTkSwitch(
            settings,
            text="Symuluj literówki",
            variable=self.typos_enabled
        ).pack(anchor="w", padx=12, pady=7)

        ctk.CTkSwitch(
            settings,
            text="Obsługuj Enter",
            variable=self.enter_enabled
        ).pack(anchor="w", padx=12, pady=7)

        ctk.CTkSwitch(
            settings,
            text="Losowe przerwy",
            variable=self.random_pauses
        ).pack(anchor="w", padx=12, pady=7)

        ctk.CTkLabel(
            settings,
            text="Opóźnienie startu"
        ).pack(anchor="w", padx=12, pady=(18, 5))

        self.delay_menu = ctk.CTkOptionMenu(
            settings,
            values=["3", "5", "10", "15"],
            command=lambda v: setattr(self, "delay", int(v))
        )
        self.delay_menu.set("5")
        self.delay_menu.pack(fill="x", padx=12, pady=5)

        ctk.CTkLabel(
            settings,
            text="Historia tekstów"
        ).pack(anchor="w", padx=12, pady=(18, 5))

        self.history_menu = ctk.CTkOptionMenu(
            settings,
            values=["Brak historii"] + [
                f"Tekst {i + 1}" for i in range(len(self.history))
            ],
            command=self.load_history
        )
        self.history_menu.pack(fill="x", padx=12, pady=5)

        footer = ctk.CTkFrame(self, corner_radius=16)
        footer.grid(
            row=2, column=0,
            padx=15, pady=12,
            sticky="ew"
        )

        footer.grid_columnconfigure(0, weight=1)

        self.status = ctk.CTkLabel(
            footer,
            text="Gotowy",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.status.grid(
            row=0, column=0,
            sticky="w", padx=15, pady=8
        )

        self.progress = ctk.CTkProgressBar(footer)
        self.progress.grid(
            row=1, column=0,
            sticky="ew", padx=15, pady=5
        )
        self.progress.set(0)

        self.stats = ctk.CTkLabel(
            footer,
            text="0 znaków | 0 słów | 0 min"
        )
        self.stats.grid(
            row=2, column=0,
            sticky="w", padx=15, pady=8
        )

        buttons = ctk.CTkFrame(
            footer,
            fg_color="transparent"
        )
        buttons.grid(row=0, column=1, rowspan=3, padx=10)

        self.start_button = ctk.CTkButton(
            buttons,
            text="START",
            command=self.start_typing,
            width=90
        )
        self.start_button.pack(side="left", padx=3)

        self.pause_button = ctk.CTkButton(
            buttons,
            text="PAUZA",
            command=self.toggle_pause,
            state="disabled",
            width=85
        )
        self.pause_button.pack(side="left", padx=3)

        self.stop_button = ctk.CTkButton(
            buttons,
            text="STOP",
            command=self.stop_typing,
            state="disabled",
            fg_color="#B83232",
            width=85
        )
        self.stop_button.pack(side="left", padx=3)

    def apply_scale(self):
        value = self.scale.get()
        ctk.set_widget_scaling(value)
        ctk.set_window_scaling(value)
        self.scale_label.configure(text=f"{value:.2f}x")

    def change_scale(self, value):
        self.apply_scale()
        self.save_settings()

    def update_speed(self, value):
        self.speed_label.configure(
            text=f"{int(float(value))} znaków/min"
        )
        self.save_settings()

    def set_speed(self, value):
        self.speed.set(value)
        self.update_speed(value)

    def update_stats(self, event=None):
        text = self.textbox.get("1.0", "end-1c")
        chars = len(text)
        words = len(text.split())
        minutes = chars / max(1, self.speed.get())

        self.stats.configure(
            text=(
                f"{chars} znaków | {words} słów | "
                f"około {minutes:.1f} min"
            )
        )

    def save_settings(self):
        save_json(SETTINGS_FILE, {
            "speed": self.speed.get(),
            "typo_rate": self.typo_rate.get(),
            "scale": self.scale.get()
        })

    def save_history(self):
        text = self.textbox.get("1.0", "end-1c")

        if not text.strip():
            return

        self.history.insert(0, text)
        self.history = self.history[:10]

        save_json(HISTORY_FILE, self.history)

        self.history_menu.configure(
            values=["Brak historii"] + [
                f"Tekst {i + 1}" for i in range(len(self.history))
            ]
        )

    def load_history(self, value):
        if value == "Brak historii":
            return

        try:
            index = int(value.split(" ")[1]) - 1
            self.textbox.delete("1.0", "end")
            self.textbox.insert("1.0", self.history[index])
            self.update_stats()
        except Exception:
            logging.exception("Błąd historii")

    def load_txt(self):
        path = filedialog.askopenfilename(
            filetypes=[("Pliki tekstowe", "*.txt")]
        )

        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8-sig") as file:
                text = file.read()

            self.textbox.delete("1.0", "end")
            self.textbox.insert("1.0", text)
            self.update_stats()

        except Exception:
            messagebox.showerror("Błąd", "Nie udało się wczytać pliku.")

    def save_txt(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Pliki tekstowe", "*.txt")]
        )

        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as file:
                file.write(self.textbox.get("1.0", "end-1c"))

        except Exception:
            messagebox.showerror("Błąd", "Nie udało się zapisać pliku.")

    def copy_text(self):
        self.clipboard_clear()
        self.clipboard_append(
            self.textbox.get("1.0", "end-1c")
        )
        self.status.configure(text="Skopiowano tekst")

    def start_typing(self):
        if self.running:
            return

        text = self.textbox.get("1.0", "end-1c")

        if not text:
            messagebox.showwarning("Brak tekstu", "Wklej tekst.")
            return

        self.save_history()

        self.total_chars = len(text)
        self.typed_chars = 0
        self.stop_event.clear()
        self.pause_event.set()
        self.running = True

        self.start_button.configure(state="disabled")
        self.pause_button.configure(state="normal")
        self.stop_button.configure(state="normal")

        self.progress.set(0)

        self.worker = threading.Thread(
            target=self.typing_worker,
            args=(text,),
            daemon=True
        )
        self.worker.start()

    def typing_worker(self, text):
        try:
            for remaining in range(self.delay, 0, -1):
                if self.stop_event.wait(1):
                    return

                self.after(
                    0,
                    lambda r=remaining: self.status.configure(
                        text=f"Start za {r} sekund..."
                    )
                )

            for char in text:
                if self.stop_event.is_set():
                    break

                while not self.pause_event.is_set():
                    if self.stop_event.wait(0.1):
                        break

                if self.stop_event.is_set():
                    break

                if char == "\n":
                    if self.enter_enabled.get():
                        pyautogui.press("enter")

                elif char == "\t":
                    pyautogui.press("tab")

                else:
                    if (
                        self.typos_enabled.get()
                        and char.isalpha()
                        and random.randint(1, 100) <= self.typo_rate.get()
                    ):
                        wrong = random.choice("abcdefghijklmnopqrstuvwxyz")
                        if wrong == char.lower():
                            wrong = "x"

                        send_unicode_char(wrong)
                        pyautogui.press("backspace")

                    send_unicode_char(char)

                self.typed_chars += 1

                if self.typed_chars % 3 == 0:
                    self.after(0, self.update_progress)

                interval = 60 / max(30, self.speed.get())

                if self.random_pauses.get():
                    interval *= random.uniform(0.75, 1.3)

                if self.stop_event.wait(interval):
                    break

            self.after(0, self.finish_typing)

        except Exception:
            logging.exception("Błąd pisania")
            self.after(0, self.finish_error)

    def update_progress(self):
        value = (
            self.typed_chars / self.total_chars
            if self.total_chars else 0
        )

        self.progress.set(value)
        self.status.configure(
            text=f"Postęp: {int(value * 100)}%"
        )

    def toggle_pause(self):
        if not self.running:
            return

        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_button.configure(text="WZNÓW")
            self.status.configure(text="Wstrzymano")
        else:
            self.pause_event.set()
            self.pause_button.configure(text="PAUZA")
            self.status.configure(text="Wznawianie...")

    def stop_typing(self):
        if self.running:
            self.stop_event.set()
            self.pause_event.set()
            self.after(
                0,
                lambda: self.status.configure(text="Zatrzymywanie...")
            )

    def finish_typing(self):
        self.running = False

        self.start_button.configure(state="normal")
        self.pause_button.configure(state="disabled", text="PAUZA")
        self.stop_button.configure(state="disabled")

        self.update_progress()

        self.status.configure(
            text="Zatrzymano" if self.stop_event.is_set() else "Zakończono"
        )

    def finish_error(self):
        self.running = False

        self.start_button.configure(state="normal")
        self.pause_button.configure(state="disabled")
        self.stop_button.configure(state="disabled")

        self.status.configure(text="Wystąpił błąd")

        messagebox.showerror(
            "TypeFlow",
            f"Wystąpił błąd. Sprawdź plik:\n{LOG_FILE}"
        )

    def close_app(self):
        self.stop_event.set()
        self.pause_event.set()
        self.save_settings()

        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass

        self.destroy()


if __name__ == "__main__":
    app = TypeFlow()
    app.mainloop()
