"""Віконний інтерфейс (tkinter) для платіжної системи з комісією.

Приватний ключ вводиться в поле з приховуванням символів, після входу поле
очищується; ключ існує лише в пам'яті об'єкта акаунта (див. chain.py).
"""
import tkinter as tk
from tkinter import messagebox, ttk

from chain import ChainError, PaymentClient


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Платіжна система з комісією")
        self.geometry("900x640")
        self.client = None
        self._build_connection_bar()
        self._build_tabs()
        self._build_log()
        self._set_logged_in(False)

    # ================================================================ UI
    def _build_connection_bar(self):
        bar = ttk.LabelFrame(self, text="Підключення та акаунт")
        bar.pack(fill="x", padx=8, pady=6)

        ttk.Label(bar, text="RPC:").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        self.rpc_var = tk.StringVar(value="http://127.0.0.1:8545")
        ttk.Entry(bar, textvariable=self.rpc_var, width=28).grid(row=0, column=1, padx=4)
        ttk.Button(bar, text="Підключитись", command=self.connect).grid(row=0, column=2, padx=4)
        self.conn_lbl = ttk.Label(bar, text="не підключено", foreground="gray")
        self.conn_lbl.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(bar, text="Приватний ключ:").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        # show="•" — введені символи приховано
        self.key_entry = ttk.Entry(bar, show="•", width=60)
        self.key_entry.grid(row=1, column=1, columnspan=2, padx=4, sticky="we")
        self.login_btn = ttk.Button(bar, text="Увійти", command=self.login)
        self.login_btn.grid(row=1, column=3, sticky="w", padx=4)
        self.logout_btn = ttk.Button(bar, text="Вийти", command=self.logout)
        self.logout_btn.grid(row=1, column=4, sticky="w", padx=4)
        self.key_entry.bind("<Return>", lambda _e: self.login())

        self.acc_lbl = ttk.Label(bar, text="Акаунт: —")
        self.acc_lbl.grid(row=2, column=0, columnspan=5, sticky="w", padx=6, pady=3)

    def _build_tabs(self):
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=4)

        # ---- Платіж
        pay = ttk.Frame(self.tabs)
        self.tabs.add(pay, text="Платіж")
        ttk.Label(pay, text="Адреса отримувача:").grid(row=0, column=0, sticky="e", padx=6, pady=8)
        self.to_var = tk.StringVar()
        ttk.Entry(pay, textvariable=self.to_var, width=52).grid(row=0, column=1, sticky="w")
        ttk.Label(pay, text="Сума (ETH):").grid(row=1, column=0, sticky="e", padx=6, pady=8)
        self.amount_var = tk.StringVar()
        amount = ttk.Entry(pay, textvariable=self.amount_var, width=20)
        amount.grid(row=1, column=1, sticky="w")
        amount.bind("<KeyRelease>", lambda _e: self.update_preview())
        self.preview_lbl = ttk.Label(pay, text="Комісія: —")
        self.preview_lbl.grid(row=2, column=1, sticky="w", pady=4)
        self.pay_btn = ttk.Button(pay, text="Надіслати платіж", command=self.do_pay)
        self.pay_btn.grid(row=3, column=1, sticky="w", pady=10)

        # ---- Історія
        hist = ttk.Frame(self.tabs)
        self.tabs.add(hist, text="Історія")
        cols = ("dir", "from", "to", "amount", "fee", "time")
        self.tree = ttk.Treeview(hist, columns=cols, show="headings", height=14)
        for c, title, w in (("dir", "Тип", 70), ("from", "Від", 190), ("to", "Кому", 190),
                            ("amount", "Сума, ETH", 90), ("fee", "Комісія, ETH", 100),
                            ("time", "Час", 150)):
            self.tree.heading(c, text=title)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)
        ttk.Button(hist, text="Оновити", command=self.refresh_history).pack(anchor="w", padx=6, pady=4)

        # ---- Власник / FeeCollector
        own = ttk.Frame(self.tabs)
        self.tabs.add(own, text="Комісії (власник)")
        self.stats_lbl = ttk.Label(own, text="", justify="left", font=("Consolas", 10))
        self.stats_lbl.grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=8)
        ttk.Button(own, text="Оновити статистику", command=self.refresh_stats)\
            .grid(row=1, column=0, sticky="w", padx=8)

        ttk.Label(own, text="Нова комісія (б.п., 100 = 1 %):").grid(row=2, column=0, sticky="e", padx=8, pady=8)
        self.fee_var = tk.StringVar()
        ttk.Entry(own, textvariable=self.fee_var, width=10).grid(row=2, column=1, sticky="w")
        self.fee_btn = ttk.Button(own, text="Змінити", command=self.do_set_fee)
        self.fee_btn.grid(row=2, column=2, sticky="w")

        ttk.Label(own, text="Вивести на адресу:").grid(row=3, column=0, sticky="e", padx=8, pady=4)
        self.w_to_var = tk.StringVar()
        ttk.Entry(own, textvariable=self.w_to_var, width=48).grid(row=3, column=1, columnspan=2, sticky="w")
        ttk.Label(own, text="Сума (ETH):").grid(row=4, column=0, sticky="e", padx=8, pady=4)
        self.w_amt_var = tk.StringVar()
        ttk.Entry(own, textvariable=self.w_amt_var, width=20).grid(row=4, column=1, sticky="w")
        self.w_btn = ttk.Button(own, text="Вивести суму", command=self.do_withdraw)
        self.w_btn.grid(row=4, column=2, sticky="w")
        self.wall_btn = ttk.Button(own, text="Вивести весь прибуток собі", command=self.do_withdraw_all)
        self.wall_btn.grid(row=5, column=1, sticky="w", pady=8)

    def _build_log(self):
        frame = ttk.LabelFrame(self, text="Журнал")
        frame.pack(fill="x", padx=8, pady=6)
        self.log = tk.Text(frame, height=7, state="disabled", wrap="word")
        self.log.pack(fill="x", padx=4, pady=4)

    # ============================================================ helpers
    def write(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_logged_in(self, on: bool):
        state = "normal" if on else "disabled"
        for w in (self.pay_btn, self.fee_btn, self.w_btn, self.wall_btn, self.logout_btn):
            w.configure(state=state)
        self.login_btn.configure(state="disabled" if on else "normal")

    def _need_client(self):
        if not self.client:
            messagebox.showwarning("Підключення", "Спочатку підключіться до вузла.")
            return False
        return True

    def _run(self, action, ok_msg=None):
        """Виконує дію з обробкою помилок і виводом у журнал."""
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            result = action()
            if ok_msg:
                self.write(ok_msg(result) if callable(ok_msg) else ok_msg)
            return result
        except ChainError as e:
            self.write(f"✖ {e}")
            messagebox.showerror("Помилка", str(e))
        except Exception as e:  # noqa: BLE001
            self.write(f"✖ Неочікувана помилка: {e}")
            messagebox.showerror("Помилка", str(e))
        finally:
            self.config(cursor="")
        return None

    # =========================================================== actions
    def connect(self):
        def act():
            self.client = PaymentClient(self.rpc_var.get().strip())
            return self.client
        if self._run(act):
            self.conn_lbl.configure(text=f"підключено, chainId={self.client.w3.eth.chain_id}", foreground="green")
            self.write("✔ Підключено. PaymentProcessor: " + self.client.processor.address)
            self.write("  FeeCollector: " + self.client.collector.address)
            self.update_preview()
            self.refresh_stats()
        else:
            self.client = None
            self.conn_lbl.configure(text="не підключено", foreground="red")

    def login(self):
        if not self._need_client():
            return
        key = self.key_entry.get()
        address = self._run(lambda: self.client.login(key))
        key = None  # не тримаємо копію ключа
        self.key_entry.delete(0, "end")  # очищаємо поле одразу після входу
        if address:
            self._set_logged_in(True)
            self.write(f"✔ Вхід виконано: {address}")
            self.refresh_account()
            self.refresh_history()
            self.refresh_stats()

    def logout(self):
        if self.client:
            self.client.logout()
        self.key_entry.delete(0, "end")
        self._set_logged_in(False)
        self.acc_lbl.configure(text="Акаунт: —")
        self.tree.delete(*self.tree.get_children())
        self.write("Вихід виконано, ключ видалено з пам'яті.")

    def refresh_account(self):
        if self.client and self.client.address:
            bal = self._run(self.client.balance_of)
            if bal is not None:
                self.acc_lbl.configure(text=f"Акаунт: {self.client.address}   Баланс: {bal:.6f} ETH")

    def update_preview(self):
        if not self.client:
            return
        try:
            fee, net = self.client.preview_fee(self.amount_var.get() or "0")
            pct = self.client.fee_bps() / 100
            self.preview_lbl.configure(text=f"Комісія ({pct:g} %): {fee:.6f} ETH   Отримувач отримає: {net:.6f} ETH")
        except Exception:  # noqa: BLE001
            self.preview_lbl.configure(text="Комісія: —")

    def do_pay(self):
        if not self._need_client():
            return
        r = self._run(lambda: self.client.pay(self.to_var.get().strip(), self.amount_var.get()),
                      lambda rc: f"✔ Платіж надіслано. tx: {rc.transactionHash.hex()}")
        if r:
            self.amount_var.set("")
            self.refresh_account(); self.refresh_history(); self.refresh_stats()

    def refresh_history(self):
        if not (self.client and self.client.address):
            return
        rows = self._run(self.client.history)
        if rows is None:
            return
        self.tree.delete(*self.tree.get_children())
        me = self.client.address.lower()
        for r in reversed(rows):
            kind = "вихідний" if r["from"].lower() == me else "вхідний"
            self.tree.insert("", "end", values=(kind, r["from"], r["to"],
                                                f'{r["amount"]:.6f}', f'{r["fee"]:.6f}', r["time"]))

    def refresh_stats(self):
        if not self.client:
            return
        s = self._run(self.client.stats)
        if not s:
            return
        self.stats_lbl.configure(text=(
            f"Комісія:               {s['fee_bps']} б.п. ({s['fee_bps'] / 100:g} %)\n"
            f"Обіг платежів:         {s['total_volume']:.6f} ETH  (платежів: {s['payments']})\n"
            f"Зібрано комісій:       {s['total_collected']:.6f} ETH\n"
            f"Виведено:              {s['total_withdrawn']:.6f} ETH\n"
            f"Доступно до виведення: {s['collector_balance']:.6f} ETH\n"
            f"Власник Processor:     {s['processor_owner']}\n"
            f"Власник Collector:     {s['collector_owner']}"))

    def do_set_fee(self):
        if not self._need_client():
            return
        try:
            bps = int(self.fee_var.get())
        except ValueError:
            messagebox.showerror("Помилка", "Введіть ціле число базисних пунктів.")
            return
        if self._run(lambda: self.client.set_fee_bps(bps), f"✔ Комісію змінено на {bps} б.п."):
            self.update_preview(); self.refresh_stats()

    def do_withdraw(self):
        if not self._need_client():
            return
        if self._run(lambda: self.client.withdraw(self.w_to_var.get().strip(), self.w_amt_var.get()),
                     "✔ Прибуток виведено."):
            self.refresh_account(); self.refresh_stats()

    def do_withdraw_all(self):
        if not self._need_client():
            return
        if self._run(self.client.withdraw_all, "✔ Весь прибуток виведено власнику."):
            self.refresh_account(); self.refresh_stats()


if __name__ == "__main__":
    App().mainloop()
