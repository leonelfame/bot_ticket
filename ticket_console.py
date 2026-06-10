import hashlib
import json
import random
import threading
import time
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk

from zone_availability_parser import (
    parse_zone_availability_file,
    parse_zone_availability_html,
    summarize_zones,
)


APP_DIR = Path(__file__).resolve().parent
ENV_FILE = APP_DIR / ".env"
PAYMENT_PAGE = APP_DIR / "payment_test.html"


@dataclass
class Zone:
    code: str
    available: int
    price: int


@dataclass
class Account:
    index: int
    username: str
    password: str


def _clean_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_env_accounts(path: Path = ENV_FILE) -> list[Account]:
    if not path.exists():
        return []

    raw: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        raw[key.strip()] = _clean_env_value(value)

    account_indexes = sorted(
        {
            int(key.split("_")[1])
            for key in raw
            if key.startswith("ACCOUNT_")
            and key.endswith("_USERNAME")
            and key.split("_")[1].isdigit()
        }
    )
    accounts = []
    for index in account_indexes:
        username = raw.get(f"ACCOUNT_{index}_USERNAME", "")
        password = raw.get(f"ACCOUNT_{index}_PASSWORD", "")
        if username and password:
            accounts.append(Account(index=index, username=username, password=password))
    return accounts


class TicketDataProvider:
    """Local/offline data provider. It never calls a third-party ticketing service."""

    def __init__(self) -> None:
        self.zones = [
            Zone("A1", 18, 8169),
            Zone("B1", 12, 7200),
            Zone("C2", 8, 6500),
            Zone("D1", 6, 5900),
        ]

    def fetch_zones(self) -> list[Zone]:
        time.sleep(0.25)
        for zone in self.zones:
            zone.available = max(1, zone.available + random.randint(-3, 4))
        return self.zones

    def reserve_test_seat(self, zone_code: str, qty: int) -> str:
        time.sleep(random.uniform(0.4, 1.1))
        return f"TEST-{zone_code}-{qty}-{random.randint(1000, 9999)}"


class BrowserController:
    """Browser handoff for local demo pages only."""

    def open_local_payment(self, booking_id: str) -> None:
        url = PAYMENT_PAGE.as_uri() + f"?booking={booking_id}"
        webbrowser.open(url)

    def open_local_console(self) -> None:
        index_page = APP_DIR / "index.html"
        if index_page.exists():
            webbrowser.open(index_page.as_uri())


class TicketConsoleApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("TTM Flow Console")
        self.geometry("980x620")
        self.minsize(900, 560)
        self.configure(bg="#02040a")

        self.api = TicketDataProvider()
        self.browser = BrowserController()
        self.accounts = load_env_accounts()
        self.loaded_zone_rows = []
        self.response_file_path: Path | None = None
        self.watch_enabled = False
        self.watch_job = None
        self.task_counter = 1
        self.selected_booking = tk.StringVar(value="")
        self.login_status = tk.StringVar(value="AUTH: NOT CHECKED")

        self.api_key = tk.StringVar(value="")
        self.cookie = tk.StringVar(value="")
        self.event_url = tk.StringVar(
            value="https://www.thaiticketmajor.com/concert/the-weeknd-after-hours--til-dawn-tour.html"
        )
        self.availability_url = tk.StringVar(
            value="https://booking.thaiticketmajor.com/booking/3m/zonesavail.php?round=81728&tk=4bce2d4cb00eecce77d738d00d714e1089bf8f3fc05e0bb1c386add37f21f9b1"
        )
        self.event_date = tk.StringVar(value="10:00")
        self.delay_ms = tk.IntVar(value=1000)
        self.rounds = tk.IntVar(value=3)
        self.refresh_seconds = tk.IntVar(value=3)
        self.qty = tk.IntVar(value=1)
        self.price = tk.IntVar(value=8169)
        self.zone = tk.StringVar(value="A1 (ว่าง 18)")
        self.accs_on = tk.BooleanVar(value=False)

        self._setup_style()
        self._build_layout()
        self._draw_seats()
        self._log("ระบบพร้อมใช้งาน")
        self._log("ขั้นตอนซื้อบัตร/เข้าคิว/จ่ายเงินให้ทำต่อใน browser โดยมนุษย์", "warn")
        self._log(f"โหลดบัญชีจาก .env ได้ {len(self.accounts)} รายการ")

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Root.TFrame", background="#02040a")
        style.configure("Panel.TFrame", background="#05080f", bordercolor="#f0529d")
        style.configure("TLabel", background="#05080f", foreground="#e8f1ff")
        style.configure(
            "Hot.TButton",
            background="#10192a",
            foreground="#e8f1ff",
            bordercolor="#368dff",
            focusthickness=0,
            padding=(8, 4),
        )
        style.map("Hot.TButton", background=[("active", "#172743")])
        style.configure(
            "Danger.TButton",
            background="#251017",
            foreground="#ffc2cb",
            bordercolor="#ff4e5f",
            padding=(8, 4),
        )
        style.configure(
            "Green.TButton",
            background="#0b2415",
            foreground="#b9ffd0",
            bordercolor="#4cff88",
            padding=(8, 4),
        )
        style.configure(
            "Dark.TEntry",
            fieldbackground="#03050a",
            foreground="#f7fbff",
            bordercolor="#f0529d",
            insertcolor="#ffffff",
        )
        style.configure(
            "Dark.TCombobox",
            fieldbackground="#03050a",
            background="#10192a",
            foreground="#f7fbff",
            arrowcolor="#54a6ff",
        )

    def _build_layout(self) -> None:
        root = ttk.Frame(self, style="Root.TFrame", padding=8)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=0)
        root.rowconfigure(1, weight=1)

        top = tk.Frame(root, bg="#05080f", highlightbackground="#f0529d", highlightthickness=1)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        top.columnconfigure(2, weight=1)

        tk.Label(top, text="▰ TTM Auto-Book", bg="#05080f", fg="#d4e6ff").grid(
            row=0, column=0, padx=8, pady=5
        )
        ttk.Button(top, text="API", style="Hot.TButton").grid(row=0, column=1, padx=3)
        ttk.Entry(top, textvariable=self.api_key, style="Dark.TEntry", show="*", width=28).grid(
            row=0, column=2, sticky="ew", padx=3
        )
        ttk.Button(top, text="Accounts", style="Hot.TButton", command=self._show_accounts).grid(
            row=0, column=3, padx=3
        )
        self.acc_button = ttk.Button(
            top, text="Accs: OFF", style="Danger.TButton", command=self._toggle_accounts
        )
        self.acc_button.grid(row=0, column=4, padx=3)
        tk.Label(top, text="● READY", bg="#05080f", fg="#4cff88").grid(row=0, column=5, padx=8)

        left = tk.Frame(root, bg="#02040a")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)

        cookie_row = tk.Frame(left, bg="#05080f", highlightbackground="#f0529d", highlightthickness=1)
        cookie_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        cookie_row.columnconfigure(2, weight=1)
        ttk.Button(cookie_row, text="AllConcert", style="Hot.TButton").grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(cookie_row, text="COOKIE", style="Hot.TButton").grid(row=0, column=1, padx=5)
        ttk.Entry(cookie_row, textvariable=self.cookie, style="Dark.TEntry", show="*", width=60).grid(
            row=0, column=2, sticky="ew", padx=5
        )
        ttk.Button(cookie_row, text="Load Login Response", style="Hot.TButton", command=self._load_login_response).grid(
            row=0, column=3, padx=5
        )
        tk.Label(cookie_row, textvariable=self.login_status, bg="#05080f", fg="#4cff88").grid(
            row=0, column=4, padx=5
        )

        form = tk.Frame(left, bg="#05080f", highlightbackground="#f0529d", highlightthickness=1)
        form.grid(row=1, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        self._field(form, "Event URL", self.event_url, 0, 0, width=78, span=3)
        self._field(form, "Sale Time", self.event_date, 1, 0, width=34)
        ttk.Button(form, text="Open Event Page", style="Hot.TButton", command=self._open_event_page).grid(
            row=1, column=2, padx=5, pady=5, sticky="ew"
        )
        ttk.Button(form, text="Open Saved UI", style="Hot.TButton", command=self.browser.open_local_console).grid(
            row=1, column=3, padx=5, pady=5, sticky="ew"
        )

        tk.Label(form, text="ZONE", bg="#05080f", fg="#ff85ba").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.zone_box = ttk.Combobox(
            form,
            textvariable=self.zone,
            style="Dark.TCombobox",
            values=[f"{z.code} (ว่าง {z.available})" for z in self.api.zones],
            state="readonly",
            width=24,
        )
        self.zone_box.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        self._number(form, "Refresh s", self.refresh_seconds, 2, 2)
        self._field(form, "Availability URL", self.availability_url, 3, 0, width=78, span=3)

        buttons = tk.Frame(form, bg="#05080f")
        buttons.grid(row=4, column=0, columnspan=4, sticky="ew", padx=5, pady=6)
        for index in range(7):
            buttons.columnconfigure(index, weight=1)
        ttk.Button(buttons, text="Load Availability HTML", style="Hot.TButton", command=self._load_response_html).grid(
            row=0, column=0, sticky="ew", padx=3
        )
        ttk.Button(buttons, text="Watch Availability", style="Hot.TButton", command=self._toggle_watch_file).grid(
            row=0, column=1, sticky="ew", padx=3
        )
        ttk.Button(buttons, text="Paste Availability HTML", style="Hot.TButton", command=self._paste_availability_html).grid(
            row=0, column=2, sticky="ew", padx=3
        )
        ttk.Button(buttons, text="Load Login Response", style="Hot.TButton", command=self._load_login_response).grid(
            row=0, column=3, sticky="ew", padx=3
        )

        map_panel = tk.Frame(left, bg="#000000", highlightbackground="#263247", highlightthickness=1)
        map_panel.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        map_panel.rowconfigure(0, weight=1)
        map_panel.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(map_panel, bg="#000000", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        right = tk.Frame(root, bg="#02040a", width=290)
        right.grid(row=1, column=1, sticky="ns")
        right.grid_propagate(False)
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        task_panel = self._side_panel(right, "Zone Availability", 0)
        self.zone_list = tk.Listbox(
            task_panel,
            bg="#03050a",
            fg="#dbeaff",
            selectbackground="#13294a",
            highlightthickness=0,
            borderwidth=0,
            font=("Consolas", 10),
            height=16,
        )
        self.zone_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))
        self.zone_list.bind("<<ListboxSelect>>", self._on_zone_selected)
        log_panel = self._side_panel(right, "Log", 1)
        self.log_box = tk.Listbox(
            log_panel,
            bg="#03050a",
            fg="#bde8ff",
            selectbackground="#13294a",
            highlightthickness=0,
            borderwidth=0,
            font=("Consolas", 9),
        )
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def _field(self, parent, label, variable, row, column, width=30, span=1) -> None:
        tk.Label(parent, text=label, bg="#05080f", fg="#ff85ba").grid(
            row=row, column=column, padx=5, pady=5, sticky="w"
        )
        ttk.Entry(parent, textvariable=variable, style="Dark.TEntry", width=width).grid(
            row=row, column=column + 1, columnspan=span, padx=5, pady=5, sticky="ew"
        )

    def _number(self, parent, label, variable, row, column) -> None:
        frame = tk.Frame(parent, bg="#05080f")
        frame.grid(row=row, column=column, padx=5, pady=5, sticky="ew")
        tk.Label(frame, text=label, bg="#05080f", fg="#ff85ba").pack(side=tk.LEFT)
        ttk.Entry(frame, textvariable=variable, style="Dark.TEntry", width=7).pack(side=tk.RIGHT)

    def _side_panel(self, parent, title, row) -> tk.Frame:
        panel = tk.Frame(parent, bg="#05080f", highlightbackground="#f0529d", highlightthickness=1)
        panel.grid(row=row, column=0, sticky="nsew", pady=(0, 8 if row == 0 else 0))
        header = tk.Label(panel, text=f"■ {title}", bg="#05080f", fg="#ffd4e6", anchor="w")
        header.pack(fill=tk.X, padx=8, pady=5)
        return panel

    def _draw_seats(self) -> None:
        self.canvas.delete("all")
        width = 650
        self.canvas.create_arc(
            210,
            -95,
            440,
            95,
            start=180,
            extent=180,
            outline="#3359ff",
            width=3,
        )
        rows = ["H", "I", "J", "K", "L", "M"]
        start_y = 135
        for row_index, row in enumerate(rows):
            count = min(2 + row_index, 6)
            y = start_y + row_index * 27
            x_start = width // 2 - count * 13
            self.canvas.create_text(x_start - 24, y, text=row, fill="#9bc8ff", font=("Segoe UI", 9, "bold"))
            for seat_index in range(count):
                x = x_start + seat_index * 27
                number = str(6 - seat_index).zfill(2)
                self.canvas.create_oval(x, y - 11, x + 22, y + 11, fill="#d52b35", outline="#ff6870")
                self.canvas.create_text(x + 11, y, text=number, fill="#ffffff", font=("Segoe UI", 8, "bold"))

    def _toggle_accounts(self) -> None:
        if not self.accounts:
            self._log("ไม่พบ ACCOUNT_n_USERNAME/PASSWORD ใน .env", "warn")
            return
        value = not self.accs_on.get()
        self.accs_on.set(value)
        self.acc_button.configure(text="Accs: ON" if value else "Accs: OFF")
        self._log("เปิดบัญชีจำลอง" if value else "ปิดบัญชีจำลอง", "ok" if value else "warn")

    def _show_accounts(self) -> None:
        window = tk.Toplevel(self)
        window.title("Accounts from .env")
        window.geometry("430x240")
        window.configure(bg="#05080f")

        tk.Label(
            window,
            text="บัญชีที่อ่านจาก .env ใช้แสดงผลในการทดสอบเท่านั้น",
            bg="#05080f",
            fg="#e8f1ff",
        ).pack(anchor="w", padx=12, pady=(12, 6))

        box = tk.Listbox(
            window,
            bg="#03050a",
            fg="#dbeaff",
            selectbackground="#13294a",
            highlightthickness=1,
            highlightbackground="#f0529d",
            borderwidth=0,
            font=("Consolas", 10),
        )
        box.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        if not self.accounts:
            box.insert(tk.END, "No accounts found. Create .env from .env.example.")
            return

        for account in self.accounts:
            masked = "*" * min(max(len(account.password), 6), 12)
            box.insert(tk.END, f"ACCOUNT_{account.index}: {account.username} | {masked}")

    def _test_login(self) -> None:
        if not self.accounts:
            self._log("ไม่พบ account ใน .env สำหรับ test login", "warn")
            return

        account = self.accounts[0]
        user_hash = hashlib.sha256(account.username.encode("utf-8")).hexdigest()[:12]
        session_seed = f"{account.index}:{account.username}:{time.time()}:{random.random()}"
        session_hash = hashlib.sha256(session_seed.encode("utf-8")).hexdigest()
        self.cookie.set(
            f"TESTSESSID={session_hash[:32]}; TESTUSER={user_hash}; TESTAUTH=local-only"
        )
        self.accs_on.set(True)
        self.acc_button.configure(text="Accs: ON")
        self._log(f"test login สำเร็จจาก ACCOUNT_{account.index}; สร้าง cookie สำหรับทดสอบแล้ว")

    def _open_event_page(self) -> None:
        url = self.event_url.get().strip()
        if not url:
            self._log("event url is empty", "err")
            return
        webbrowser.open(url)
        self._log(f"opened event page; click buy/queue manually at sale time {self.event_date.get()}")

    def _load_login_response(self) -> None:
        path = filedialog.askopenfilename(
            title="Load getloginname response",
            initialdir=str(APP_DIR),
            filetypes=[
                ("JSON/Text files", "*.json *.txt"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        try:
            text = Path(path).read_text(encoding="utf-8").strip()
        except OSError as error:
            self.login_status.set("AUTH: READ FAILED")
            self._log(f"read login response failed: {error}", "err")
            return

        status, detail = self._classify_login_response(text)
        self.login_status.set(f"AUTH: {status}")
        self._log(f"login response check: {status} | {detail}")

    def _classify_login_response(self, text: str) -> tuple[str, str]:
        if not text:
            return "FAIL", "empty response"

        lowered = text.lower()
        if any(token in lowered for token in ["not login", "not_logged", "signin", "login required"]):
            return "FAIL", "login-required marker found"

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict):
            flat = " ".join(str(value) for value in payload.values() if value is not None)
            keys = ",".join(payload.keys())
            if any(key.lower() in keys.lower() for key in ["name", "email", "user", "member", "login"]):
                return "OK", f"json keys: {keys}"
            if "@" in flat or any(token in flat.lower() for token in ["logout", "profile", "member"]):
                return "OK", "json values contain account marker"
            return "UNKNOWN", f"json keys: {keys}"

        if "@" in text or any(token in lowered for token in ["logout", "profile", "member", "username"]):
            return "OK", "text contains account marker"

        return "UNKNOWN", "no clear login marker"

    def _fetch_zones(self) -> None:
        zones = self.api.fetch_zones()
        values = [f"{zone.code} (ว่าง {zone.available})" for zone in zones]
        self.zone_box.configure(values=values)
        self.zone.set(values[0])
        self.price.set(zones[0].price)
        self._log("ดึงโซน/ที่นั่งจาก offline data provider แล้ว")

    def _apply_zone_rows(self, zones, source_label: str) -> None:
        available_zones = [zone for zone in zones if zone.is_available]
        if not available_zones:
            self._log("no available zones found in response HTML", "warn")
            return

        self.loaded_zone_rows = zones
        values = [f"{zone.code} ({zone.availability})" for zone in available_zones]
        self.zone_box.configure(values=values)
        self.zone.set(values[0])
        self._render_zone_list(zones)
        self._draw_zone_map(zones)

        summary = summarize_zones(zones)
        self._log(
            f"{source_label}: total={summary['total']} available={summary['available']} sold_out={summary['sold_out']}"
        )

    def _render_zone_list(self, zones) -> None:
        self.zone_list.delete(0, tk.END)
        self.visible_zone_rows = []
        sorted_zones = sorted(
            zones,
            key=lambda zone: (
                zone.is_available,
                zone.available_count if zone.available_count is not None else 1,
                zone.code,
            ),
            reverse=True,
        )
        for zone in sorted_zones:
            status = "OK" if zone.is_available else "--"
            self.visible_zone_rows.append(zone)
            self.zone_list.insert(
                tk.END,
                f"{status} {zone.code:<5} {zone.availability:<10} {zone.flow}",
            )

    def _on_zone_selected(self, _event=None) -> None:
        selection = self.zone_list.curselection()
        if not selection:
            return
        index = selection[0]
        if index >= len(getattr(self, "visible_zone_rows", [])):
            return
        zone = self.visible_zone_rows[index]
        self.zone.set(f"{zone.code} ({zone.availability})")
        self._log(f"selected zone {zone.code}; continue manually in browser")

    def _draw_zone_map(self, zones) -> None:
        self.canvas.delete("all")
        sorted_zones = sorted(zones, key=lambda zone: zone.code)
        if not sorted_zones:
            self._draw_seats()
            return

        width = max(self.canvas.winfo_width(), 620)
        cell_w = 46
        cell_h = 28
        gap = 5
        columns = max(1, min(12, width // (cell_w + gap)))
        x0 = 14
        y0 = 14

        for index, zone in enumerate(sorted_zones):
            row = index // columns
            col = index % columns
            x = x0 + col * (cell_w + gap)
            y = y0 + row * (cell_h + gap)
            fill = "#173e25" if zone.is_available else "#3b1118"
            outline = "#4cff88" if zone.is_available else "#ff4e5f"
            text_color = "#dfffea" if zone.is_available else "#ffc6ce"
            self.canvas.create_rectangle(x, y, x + cell_w, y + cell_h, fill=fill, outline=outline)
            self.canvas.create_text(
                x + cell_w / 2,
                y + 11,
                text=zone.code,
                fill=text_color,
                font=("Segoe UI", 7, "bold"),
            )
            self.canvas.create_text(
                x + cell_w / 2,
                y + 21,
                text=zone.availability,
                fill=text_color,
                font=("Segoe UI", 7),
            )

    def _load_response_html(self) -> None:
        path = filedialog.askopenfilename(
            title="Load zones availability HTML",
            initialdir=str(APP_DIR),
            filetypes=[
                ("HTML files", "*.html *.htm"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        self.response_file_path = Path(path)
        try:
            zones = parse_zone_availability_file(self.response_file_path)
        except OSError as error:
            self._log(f"read file failed: {error}", "err")
            return

        self._apply_zone_rows(zones, "loaded response")

    def _paste_availability_html(self) -> None:
        window = tk.Toplevel(self)
        window.title("Paste Availability HTML")
        window.geometry("760x480")
        window.configure(bg="#05080f")

        tk.Label(
            window,
            text="Paste zones availability response body here",
            bg="#05080f",
            fg="#e8f1ff",
        ).pack(anchor="w", padx=10, pady=(10, 4))

        text_box = tk.Text(
            window,
            bg="#03050a",
            fg="#dbeaff",
            insertbackground="#ffffff",
            highlightthickness=1,
            highlightbackground="#f0529d",
            borderwidth=0,
            font=("Consolas", 10),
            wrap=tk.NONE,
        )
        text_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        def apply_pasted_html() -> None:
            html = text_box.get("1.0", tk.END).strip()
            if not html:
                self._log("availability response is empty", "err")
                return
            zones = parse_zone_availability_html(html)
            self._apply_zone_rows(zones, "pasted response")
            window.destroy()

        ttk.Button(
            window,
            text="Apply To Map",
            style="Green.TButton",
            command=apply_pasted_html,
        ).pack(anchor="e", padx=10, pady=(0, 10))

    def _toggle_watch_file(self) -> None:
        if self.watch_enabled:
            self.watch_enabled = False
            if self.watch_job is not None:
                self.after_cancel(self.watch_job)
                self.watch_job = None
            self._log("stopped response file watcher", "warn")
            return

        if self.response_file_path is None:
            self._load_response_html()
            if self.response_file_path is None:
                return

        self.watch_enabled = True
        self._log(f"watching response file every {self.refresh_seconds.get()}s")
        self._refresh_response_file()

    def _refresh_response_file(self) -> None:
        if not self.watch_enabled or self.response_file_path is None:
            return

        try:
            zones = parse_zone_availability_file(self.response_file_path)
        except OSError as error:
            self._log(f"refresh failed: {error}", "err")
        else:
            self._apply_zone_rows(zones, "refreshed response")

        interval_ms = max(1, self.refresh_seconds.get()) * 1000
        self.watch_job = self.after(interval_ms, self._refresh_response_file)

    def _start_batch(self) -> None:
        count = max(1, min(self.rounds.get(), 8))
        self._log(f"เริ่ม batch จำลอง {count} task", "warn")
        for _ in range(count):
            self._create_task()

    def _create_task(self) -> None:
        task_id = self.task_counter
        self.task_counter += 1
        zone_code = self.zone.get().split()[0]
        qty = max(1, min(self.qty.get(), 6))
        delay = max(250, self.delay_ms.get())
        label = f"Task #{task_id:02d} | {zone_code} | qty {qty} | READY"
        self.task_box.insert(0, label)
        self._log(f"สร้าง task จำลอง #{task_id:02d} zone {zone_code} qty {qty}")
        thread = threading.Thread(
            target=self._run_task,
            args=(task_id, zone_code, qty, delay),
            daemon=True,
        )
        thread.start()

    def _run_task(self, task_id: int, zone_code: str, qty: int, delay: int) -> None:
        time.sleep(delay / 1000)
        self._thread_log(f"Task #{task_id:02d} ตรวจที่นั่งจำลองใน {zone_code}", "warn")
        booking_id = self.api.reserve_test_seat(zone_code, qty)
        self.selected_booking.set(booking_id)
        self._thread_log(f"Task #{task_id:02d} ได้ booking test: {booking_id}")
        self.after(0, self._mark_task_payment, task_id, booking_id)

    def _mark_task_payment(self, task_id: int, booking_id: str) -> None:
        for index in range(self.task_box.size()):
            text = self.task_box.get(index)
            if text.startswith(f"Task #{task_id:02d}"):
                self.task_box.delete(index)
                self.task_box.insert(index, f"Task #{task_id:02d} | {booking_id} | PAYMENT READY")
                break

    def _open_payment(self) -> None:
        booking_id = self.selected_booking.get()
        if not booking_id:
            booking_id = "TEST-MANUAL-0000"
            self.selected_booking.set(booking_id)
            self._log("ยังไม่มี booking จาก task จึงเปิด payment test แบบ manual", "warn")
        self.browser.open_local_payment(booking_id)
        self._log(f"เปิดหน้า payment test: {booking_id}")

    def _thread_log(self, message: str, level: str = "ok") -> None:
        self.after(0, self._log, message, level)

    def _log(self, message: str, level: str = "ok") -> None:
        prefix = {
            "ok": "✓",
            "warn": "!",
            "err": "x",
        }.get(level, "-")
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {prefix} {message}"
        self.log_box.insert(tk.END, line)
        self.log_box.yview_moveto(1)


if __name__ == "__main__":
    app = TicketConsoleApp()
    app.mainloop()
