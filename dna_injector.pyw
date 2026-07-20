#!/usr/bin/env python3
"""
Adult VR Game Room - DNA Storage Injector
Reads/writes the game's DNA storage (Unity PlayerPrefs in the registry) with a GUI.
Everything ships with Python (tkinter + winreg) - no installs needed.
Game stores samples as: REG_BINARY = base64( JSON )  + trailing null byte.
"""

import base64
import datetime
import json
import os
import subprocess
import traceback

import tkinter as tk
from tkinter import ttk, messagebox

try:
    import winreg
except ImportError:
    winreg = None

try:
    import ctypes
    # Opt in to per-monitor DPI awareness so Windows doesn't blurry-stretch
    # the window and throw off tkinter's pixel measurements on scaled displays.
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# ---------------------------------------------------------------- constants
KEY_PATH        = r"Software\AdultVRGameRoom\Adult VR Game Room"
VALUE_NAME      = "stats_dna_samples_h3759496538"
STORAGE_LVL_KEY = "stats_sample_storage_level_h4265996530"
CREDITS_KEY     = "stats_credits_h981088197"    # base64(ascii int) + null
ATOMS_KEY       = "stats_atoms_h684834367"      # base64(ascii int) + null
MAX_SLOTS       = 16                       # your maxed DNA storage capacity
MAX_CURRENCY    = 999_999_999              # safe headroom below int32 max
BACKUP_DIR      = os.path.expandvars(
    r"%USERPROFILE%\AppData\LocalLow\AdultVRGameRoom\Adult VR Game Room")

RARITIES     = [("Common", 1), ("Rare", 2), ("Epic", 3),
                ("Legendary", 4), ("Mythic", 5)]
RARITY_NAME  = {1: "Common", 2: "Rare", 3: "Epic", 4: "Legendary", 5: "Mythic"}
RARITY_PRICE = {1: 25, 2: 50, 3: 100, 4: 200, 5: 400}   # 100/200/400 estimated
RARITY_COLOR = {1: "#8a9099", 2: "#3b82f6", 3: "#a855f7",
                4: "#f59e0b", 5: "#ef4444"}
RARITY_FG    = {1: "#ffffff", 2: "#ffffff", 3: "#ffffff",
                4: "#101010", 5: "#ffffff"}

RACES        = ["human", "elf", "orc", "naiad", "savage"]
REALM_KNOWN  = {"human": 1, "elf": 2, "savage": 3,  # all confirmed from live saves
                "orc": 5, "naiad": 2}               # naiad shares realm 2 with elf
GENDERS      = [("Female", "f"), ("Male", "m")]

BG   = "#1e1f24"
CARD = "#26272e"
FG   = "#e6e7ea"
MUTE = "#9aa0a6"
ACC  = "#22c55e"


# ------------------------------------------------------------ registry layer
def read_samples():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY_PATH) as k:
        raw, _ = winreg.QueryValueEx(k, VALUE_NAME)
    txt = bytes(raw).decode("utf-8", "ignore").rstrip("\x00")
    if not txt:
        return []
    obj = json.loads(base64.b64decode(txt).decode("utf-8"))
    return obj.get("samples", [])


def current_raw_b64():
    """Return the exact base64 string currently stored (for backups)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY_PATH) as k:
            raw, _ = winreg.QueryValueEx(k, VALUE_NAME)
        return bytes(raw).decode("utf-8", "ignore").rstrip("\x00")
    except FileNotFoundError:
        return ""


def read_storage_level():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY_PATH) as k:
            val, _ = winreg.QueryValueEx(k, STORAGE_LVL_KEY)
        return int(val)
    except Exception:
        return None


def write_samples(samples):
    for i, s in enumerate(samples):        # renumber slots 0..n-1
        s["dnaStorageIndex"] = i
    raw = json.dumps({"samples": samples}, separators=(",", ":"))
    b64 = base64.b64encode(raw.encode("utf-8")).decode("ascii")
    data = b64.encode("utf-8") + b"\x00"   # Unity trailing null
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY_PATH, 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, VALUE_NAME, 0, winreg.REG_BINARY, data)


def read_currency(name):
    """Return the int stored at `name`, or None if missing/unreadable."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY_PATH) as k:
            raw, _ = winreg.QueryValueEx(k, name)
        txt = bytes(raw).decode("ascii", "ignore").rstrip("\x00")
        return int(base64.b64decode(txt).decode("ascii"))
    except Exception:
        return None


def write_currency(name, value):
    b64 = base64.b64encode(str(int(value)).encode("ascii")).decode("ascii")
    data = b64.encode("ascii") + b"\x00"       # same encoding the game uses
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY_PATH, 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_BINARY, data)


def make_currency_backup():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = os.path.join(BACKUP_DIR, f"currency_backup_{ts}.txt")
    with open(path, "w", encoding="utf-8") as f:
        for name in (CREDITS_KEY, ATOMS_KEY):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY_PATH) as k:
                    raw, _ = winreg.QueryValueEx(k, name)
                b64 = bytes(raw).decode("ascii", "ignore").rstrip("\x00")
            except FileNotFoundError:
                b64 = ""
            f.write(f"{name}={b64}\n")
    return path


def game_running():
    try:
        out = subprocess.run(["tasklist"], capture_output=True, text=True,
                             creationflags=0x08000000).stdout.lower()
        return "adult vr game" in out
    except Exception:
        return False


def make_backup():
    b64 = current_raw_b64()
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = os.path.join(BACKUP_DIR, f"dna_backup_{ts}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(b64)
    return path


# ------------------------------------------------------------------- the app
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Adult VR Game Room  —  DNA Storage Injector")
        self.configure(bg=BG)
        self.samples = []
        self.dirty = False

        self._init_style()
        self._build_header()
        self._build_currency()
        self._build_body()
        self._build_footer()

        self._fit_window()

        self.reload(initial=True)

    def _fit_window(self):
        """Size the window so every widget is visible on first open.

        A hard-coded geometry clips the footer buttons on scaled/HiDPI
        displays, so ask tkinter what the built UI actually needs and use
        that as the floor (capped to the screen just in case).
        """
        self.update_idletasks()
        req_w = self.winfo_reqwidth()
        req_h = self.winfo_reqheight()
        w = min(max(req_w, 860), self.winfo_screenwidth() - 80)
        h = min(max(req_h, 560), self.winfo_screenheight() - 120)
        self.geometry(f"{w}x{h}")
        self.minsize(min(req_w, w), min(req_h, h))

    # ---- styling
    def _init_style(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure(".", background=BG, foreground=FG, fieldbackground=CARD)
        st.configure("TFrame", background=BG)
        st.configure("Card.TFrame", background=CARD)
        st.configure("TLabel", background=BG, foreground=FG)
        st.configure("Card.TLabel", background=CARD, foreground=FG)
        st.configure("Mute.TLabel", background=BG, foreground=MUTE)
        st.configure("Head.TLabel", background=BG, foreground=FG,
                     font=("Segoe UI Semibold", 15))
        st.configure("TButton", padding=6)
        st.configure("Accent.TButton", padding=8)
        st.configure("Treeview", background=CARD, fieldbackground=CARD,
                     foreground=FG, rowheight=26, borderwidth=0)
        st.configure("Treeview.Heading", background="#2f3038",
                     foreground=FG, relief="flat")
        st.map("Treeview", background=[("selected", "#3a3d47")])
        st.configure("TCombobox", fieldbackground=CARD, background=CARD)
        st.configure("TSpinbox", fieldbackground=CARD, background=CARD)

    # ---- header
    def _build_header(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=16, pady=(14, 6))
        ttk.Label(top, text="\U0001f9ec  DNA Storage Injector",
                  style="Head.TLabel").pack(side="left")
        self.cap_lbl = ttk.Label(top, text="", style="Mute.TLabel",
                                 font=("Segoe UI", 11))
        self.cap_lbl.pack(side="right")

    # ---- currency bar
    def _build_currency(self):
        bar = ttk.Frame(self, style="Card.TFrame", padding=10)
        bar.pack(fill="x", padx=16, pady=(0, 4))
        ttk.Label(bar, text="\U0001f4b0  Currency", style="Card.TLabel",
                  font=("Segoe UI Semibold", 12)).pack(side="left", padx=(0, 16))

        self.v_credits = tk.StringVar()
        self.v_atoms   = tk.StringVar()
        ttk.Label(bar, text="Credits", style="Card.TLabel").pack(side="left")
        ttk.Spinbox(bar, from_=0, to=MAX_CURRENCY, width=12,
                    textvariable=self.v_credits).pack(side="left", padx=(4, 16))
        ttk.Label(bar, text="Atoms", style="Card.TLabel").pack(side="left")
        ttk.Spinbox(bar, from_=0, to=MAX_CURRENCY, width=12,
                    textvariable=self.v_atoms).pack(side="left", padx=(4, 16))

        ttk.Button(bar, text="Max both",
                   command=self.max_currency).pack(side="left")
        ttk.Button(bar, text="\U0001f4be  Save Currency",
                   style="Accent.TButton",
                   command=self.save_currency).pack(side="right")

    # ---- body: list (left) + add form (right)
    def _build_body(self):
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=16, pady=6)

        # right - add form (packed FIRST so its fixed width is reserved before
        # the expanding table claims the rest; otherwise the table squeezes it out)
        form = ttk.Frame(body, style="Card.TFrame", padding=14)
        form.pack(side="right", fill="y", padx=(14, 0))

        # left - table
        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True)

        cols = ("slot", "rarity", "race", "gender", "realm", "price")
        self.tree = ttk.Treeview(left, columns=cols, show="headings",
                                 selectmode="extended")
        heads = {"slot": ("Slot", 46), "rarity": ("Rarity", 92),
                 "race": ("Race", 74), "gender": ("Gender", 66),
                 "realm": ("Realm", 56), "price": ("Price", 66)}
        for c, (txt, w) in heads.items():
            self.tree.heading(c, text=txt)
            self.tree.column(c, width=w, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)
        for r, col in RARITY_COLOR.items():
            self.tree.tag_configure(f"r{r}", background=col,
                                    foreground=RARITY_FG[r])
        self.tree.bind("<Double-1>", lambda e: self.remove_selected())

        rowbtns = ttk.Frame(left)
        rowbtns.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Button(rowbtns, text="Remove Selected",
                   command=self.remove_selected).pack(side="left")
        ttk.Button(rowbtns, text="Clear All",
                   command=self.clear_all).pack(side="left", padx=6)
        ttk.Label(rowbtns, text="(double-click a row to remove it)",
                  style="Mute.TLabel").pack(side="left", padx=8)

        # add-form contents (frame itself was created/packed above)
        ttk.Label(form, text="Add DNA", style="Card.TLabel",
                  font=("Segoe UI Semibold", 12)).grid(
                      row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self.v_race   = tk.StringVar(value="human")
        self.v_rarity = tk.StringVar(value="Mythic")
        self.v_gender = tk.StringVar(value="Female")
        self.v_realm  = tk.StringVar(value="1")
        self.v_price  = tk.StringVar(value=str(RARITY_PRICE[5]))
        self.v_qty    = tk.StringVar(value="1")

        def field(r, label, widget):
            ttk.Label(form, text=label, style="Card.TLabel").grid(
                row=r, column=0, sticky="w", pady=4, padx=(0, 8))
            widget.grid(row=r, column=1, sticky="ew", pady=4)

        cb_race = ttk.Combobox(form, textvariable=self.v_race, values=RACES,
                               state="readonly", width=14)
        cb_race.bind("<<ComboboxSelected>>", self._on_race)
        field(1, "Race", cb_race)

        cb_rar = ttk.Combobox(form, textvariable=self.v_rarity,
                              values=[n for n, _ in RARITIES],
                              state="readonly", width=14)
        cb_rar.bind("<<ComboboxSelected>>", self._on_rarity)
        field(2, "Rarity", cb_rar)

        cb_gen = ttk.Combobox(form, textvariable=self.v_gender,
                              values=[n for n, _ in GENDERS],
                              state="readonly", width=14)
        field(3, "Gender", cb_gen)

        field(4, "Realm", ttk.Spinbox(form, from_=1, to=9,
                                      textvariable=self.v_realm, width=12))
        field(5, "Price", ttk.Spinbox(form, from_=0, to=999999,
                                      textvariable=self.v_price, width=12))
        field(6, "Quantity", ttk.Spinbox(form, from_=1, to=MAX_SLOTS,
                                         textvariable=self.v_qty, width=12))

        self.warn_lbl = ttk.Label(form, text="", style="Card.TLabel",
                                  foreground="#f59e0b", wraplength=190,
                                  justify="left")
        self.warn_lbl.grid(row=7, column=0, columnspan=2, sticky="w", pady=(6, 4))

        ttk.Button(form, text="➕  Add to Storage",
                   command=self.add).grid(row=8, column=0, columnspan=2,
                                          sticky="ew", pady=(6, 0))
        form.columnconfigure(1, weight=1)

        # rarity legend
        leg = ttk.Frame(form, style="Card.TFrame")
        leg.grid(row=9, column=0, columnspan=2, sticky="w", pady=(14, 0))
        ttk.Label(leg, text="Rarity", style="Card.TLabel",
                  foreground=MUTE).pack(anchor="w")
        for name, r in RARITIES:
            row = tk.Frame(leg, bg=CARD)
            row.pack(anchor="w", pady=1)
            tk.Label(row, text="  ", bg=RARITY_COLOR[r]).pack(side="left")
            tk.Label(row, text=f" {r} = {name}  (~{RARITY_PRICE[r]})",
                     bg=CARD, fg=FG).pack(side="left")

    # ---- footer
    def _build_footer(self):
        foot = ttk.Frame(self)
        foot.pack(fill="x", padx=16, pady=(4, 12))
        ttk.Button(foot, text="↻  Reload from Game",
                   command=self.reload).pack(side="left")
        ttk.Button(foot, text="\U0001f4be  Save to Game",
                   style="Accent.TButton",
                   command=self.save).pack(side="right")
        self.status = ttk.Label(foot, text="", style="Mute.TLabel")
        self.status.pack(side="left", padx=12)

    # ------------------------------------------------------------- behaviour
    def _on_race(self, _=None):
        race = self.v_race.get()
        if race in REALM_KNOWN:
            self.v_realm.set(str(REALM_KNOWN[race]))
            self.warn_lbl.config(text="")
        else:
            self.warn_lbl.config(
                text=f"⚠ Realm for '{race}' is not verified yet. "
                     "Collect one common sample of this race in-game and "
                     "check its realm number, then set it here.")

    def _on_rarity(self, _=None):
        rv = self._rarity_val()
        self.v_price.set(str(RARITY_PRICE.get(rv, 0)))

    def _rarity_val(self):
        for n, v in RARITIES:
            if n == self.v_rarity.get():
                return v
        return 1

    def _gender_val(self):
        for n, v in GENDERS:
            if n == self.v_gender.get():
                return v
        return "f"

    def set_status(self, text, ok=True):
        self.status.config(text=text, foreground=ACC if ok else "#ef4444")

    def refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        for s in self.samples:
            r = int(s.get("rarity", 1))
            self.tree.insert("", "end", tags=(f"r{r}",), values=(
                s.get("dnaStorageIndex"), RARITY_NAME.get(r, r),
                s.get("race"), s.get("gender"), s.get("realm"),
                s.get("price")))
        used = len(self.samples)
        lvl = read_storage_level()
        lvltxt = f"storage lvl {lvl}  ·  " if lvl is not None else ""
        self.cap_lbl.config(
            text=f"{lvltxt}{used} / {MAX_SLOTS} slots used"
                 + ("   • unsaved changes" if self.dirty else ""))

    def add(self):
        try:
            qty = int(self.v_qty.get())
            realm = int(self.v_realm.get())
            price = int(self.v_price.get())
        except ValueError:
            messagebox.showerror("Invalid input",
                                 "Realm, Price and Quantity must be numbers.")
            return
        if qty < 1:
            return
        free = MAX_SLOTS - len(self.samples)
        if free <= 0:
            messagebox.showwarning("Storage full",
                                   f"Storage is full ({MAX_SLOTS}/{MAX_SLOTS}). "
                                   "Remove something first.")
            return
        if qty > free:
            if not messagebox.askyesno(
                    "Not enough room",
                    f"Only {free} slot(s) free but you asked for {qty}.\n"
                    f"Add {free} instead?"):
                return
            qty = free
        rar = self._rarity_val()
        for _ in range(qty):
            self.samples.append({
                "rarity": rar, "price": price, "dnaStorageIndex": 0,
                "race": self.v_race.get(), "gender": self._gender_val(),
                "realm": realm})
        self.dirty = True
        self.refresh_table()
        self.set_status(f"Added {qty} × {self.v_rarity.get()} "
                        f"{self.v_race.get()} (not saved yet)")

    def load_currency(self):
        c = read_currency(CREDITS_KEY)
        a = read_currency(ATOMS_KEY)
        self.v_credits.set(str(c) if c is not None else "")
        self.v_atoms.set(str(a) if a is not None else "")

    def max_currency(self):
        self.v_credits.set(str(MAX_CURRENCY))
        self.v_atoms.set(str(MAX_CURRENCY))

    def save_currency(self):
        if game_running():
            messagebox.showwarning(
                "Game is running",
                "Adult VR Game Room is currently running. It will overwrite "
                "these values when it saves.\n\nClose the game fully, then "
                "save again.")
            return
        try:
            c = int(self.v_credits.get())
            a = int(self.v_atoms.get())
        except ValueError:
            messagebox.showerror("Invalid input",
                                 "Credits and Atoms must be whole numbers.")
            return
        if not (0 <= c <= MAX_CURRENCY) or not (0 <= a <= MAX_CURRENCY):
            if not messagebox.askyesno(
                    "Out of safe range",
                    f"Values should be between 0 and {MAX_CURRENCY:,} to stay "
                    "safely below the game's 32-bit limit.\n\n"
                    f"Clamp to that range and save?"):
                return
            c = max(0, min(c, MAX_CURRENCY))
            a = max(0, min(a, MAX_CURRENCY))
            self.v_credits.set(str(c))
            self.v_atoms.set(str(a))
        try:
            bpath = make_currency_backup()
            write_currency(CREDITS_KEY, c)
            write_currency(ATOMS_KEY, a)
        except Exception as e:
            messagebox.showerror("Write error",
                                 f"Could not save currency:\n{e}\n\n"
                                 + traceback.format_exc())
            return
        self.set_status(f"Saved credits {c:,} · atoms {a:,} to game ✓")
        messagebox.showinfo(
            "Saved",
            f"Credits: {c:,}\nAtoms:   {a:,}\n\n"
            f"Backup of the previous values:\n{bpath}\n\n"
            "Launch the game to see them.")

    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idxs = sorted((self.tree.index(i) for i in sel), reverse=True)
        for i in idxs:
            del self.samples[i]
        self.dirty = True
        self.refresh_table()
        self.set_status(f"Removed {len(idxs)} sample(s) (not saved yet)")

    def clear_all(self):
        if not self.samples:
            return
        if messagebox.askyesno("Clear all",
                               "Remove ALL samples from the list?"):
            self.samples = []
            self.dirty = True
            self.refresh_table()
            self.set_status("Cleared (not saved yet)")

    def reload(self, initial=False):
        if not initial and self.dirty:
            if not messagebox.askyesno(
                    "Discard changes?",
                    "Reloading from the game will discard unsaved changes. "
                    "Continue?"):
                return
        try:
            self.samples = read_samples()
        except FileNotFoundError:
            self.samples = []
        except Exception as e:
            messagebox.showerror("Read error",
                                 f"Could not read DNA storage:\n{e}")
            return
        self.dirty = False
        self.refresh_table()
        self.load_currency()
        self.set_status(f"Loaded {len(self.samples)} sample(s) from game")

    def save(self):
        if game_running():
            messagebox.showwarning(
                "Game is running",
                "Adult VR Game Room is currently running. It will overwrite "
                "these values when it saves.\n\nClose the game fully, then "
                "save again.")
            return
        if len(self.samples) > MAX_SLOTS:
            messagebox.showwarning("Too many samples",
                                   f"{len(self.samples)} samples exceeds the "
                                   f"{MAX_SLOTS}-slot storage.")
            return
        try:
            bpath = make_backup()
            write_samples(self.samples)
        except Exception as e:
            messagebox.showerror("Write error",
                                 f"Could not save:\n{e}\n\n"
                                 + traceback.format_exc())
            return
        self.dirty = False
        self.refresh_table()
        self.set_status(f"Saved {len(self.samples)} sample(s) to game ✓")
        messagebox.showinfo(
            "Saved",
            f"Wrote {len(self.samples)} sample(s) to DNA storage.\n\n"
            f"Backup of the previous state:\n{bpath}\n\n"
            "Launch the game to see them.")


def main():
    if winreg is None:
        tk.Tk().withdraw()
        messagebox.showerror("Unsupported",
                             "This tool only runs on Windows (needs winreg).")
        return
    try:
        App().mainloop()
    except Exception:
        try:
            r = tk.Tk(); r.withdraw()
            messagebox.showerror("Crash", traceback.format_exc())
        except Exception:
            print(traceback.format_exc())


if __name__ == "__main__":
    main()
