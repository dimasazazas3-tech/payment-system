"""Шар взаємодії з блокчейном (web3.py). Не залежить від tkinter.

Приватний ключ використовується ЛИШЕ в пам'яті: з нього створюється об'єкт акаунта,
яким підписуються транзакції. Сам рядок ключа ніде не зберігається і не логується.
"""
import json
import re
from datetime import datetime
from pathlib import Path

from eth_account import Account
from web3 import Web3

BASE = Path(__file__).parent


class ChainError(Exception):
    """Зрозуміла користувачу помилка взаємодії з блокчейном."""


class PaymentClient:
    def __init__(self, rpc_url: str = "http://127.0.0.1:8545"):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
        if not self.w3.is_connected():
            raise ChainError(f"Не вдалося підключитися до вузла {rpc_url}. Запущено `npx hardhat node`?")

        addresses = json.loads((BASE / "contracts.json").read_text(encoding="utf-8"))
        self.collector = self._load("FeeCollector", addresses)
        self.processor = self._load("PaymentProcessor", addresses)
        if not self.w3.eth.get_code(self.processor.address):
            raise ChainError("За адресою з contracts.json немає контракту. Виконайте деплой і `node scripts/export-to-python.js`.")

        self._errors = self._build_error_table()
        self._account = None  # LocalAccount — єдине місце, де живе ключ (лише в RAM)

    # ------------------------------------------------------------------ init
    def _load(self, name, addresses):
        abi = json.loads((BASE / "abi" / f"{name}.json").read_text(encoding="utf-8"))
        return self.w3.eth.contract(address=Web3.to_checksum_address(addresses[name]), abi=abi)

    def _build_error_table(self):
        table = {}
        for c in (self.collector, self.processor):
            for item in c.abi:
                if item.get("type") == "error":
                    sig = f'{item["name"]}({",".join(i["type"] for i in item["inputs"])})'
                    table[Web3.keccak(text=sig)[:4].hex().removeprefix("0x")] = item["name"]
        return table

    # --------------------------------------------------------------- акаунт
    def login(self, private_key: str) -> str:
        key = (private_key or "").strip()
        if not re.fullmatch(r"(0x)?[0-9a-fA-F]{64}", key):
            raise ChainError("Приватний ключ має бути 64 hex-символи (з префіксом 0x або без).")
        self._account = Account.from_key(key)
        return self._account.address

    def logout(self):
        self._account = None

    @property
    def address(self):
        return self._account.address if self._account else None

    def balance_of(self, address=None) -> float:
        addr = address or self.address
        return float(Web3.from_wei(self.w3.eth.get_balance(addr), "ether"))

    # ------------------------------------------------------------ транзакції
    def _send(self, fn, value_wei: int = 0):
        if not self._account:
            raise ChainError("Спочатку увійдіть, ввівши приватний ключ.")
        try:
            tx = fn.build_transaction({
                "from": self._account.address,
                "nonce": self.w3.eth.get_transaction_count(self._account.address),
                "chainId": self.w3.eth.chain_id,
                "value": value_wei,
            })  # gas оцінюється автоматично; тут же ловиться revert
            signed = self._account.sign_transaction(tx)  # підпис локально, в пам'яті
            # web3 v7+ -> raw_transaction, старіші версії -> rawTransaction
            raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
            tx_hash = self.w3.eth.send_raw_transaction(raw)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        except ChainError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ChainError(self._explain(e)) from e
        if receipt.status != 1:
            raise ChainError("Транзакцію відхилено (revert).")
        return receipt

    def _explain(self, exc) -> str:
        text = str(exc)
        for m in re.finditer(r"0x([0-9a-fA-F]{8})", text):
            if m.group(1).lower() in self._errors:
                return self._friendly(self._errors[m.group(1).lower()])
        for name in self._errors.values():
            if name in text:
                return self._friendly(name)
        if "insufficient funds" in text.lower():
            return "Недостатньо коштів на балансі (сума + газ)."
        return text

    @staticmethod
    def _friendly(name: str) -> str:
        return {
            "NotOwner": "Дія доступна лише власнику контракту.",
            "NotProcessor": "Комісію може надсилати лише PaymentProcessor.",
            "ZeroAddress": "Нульова адреса недопустима.",
            "ZeroAmount": "Сума платежу має бути більшою за 0.",
            "FeeTooHigh": "Комісія не може перевищувати 10 % (1000 б.п.).",
            "InsufficientBalance": "У FeeCollector недостатньо коштів для виведення.",
            "TransferFailed": "Не вдалося переказати Ether отримувачу.",
            "Reentrancy": "Повторний вхід заблоковано.",
            "IndexOutOfRange": "Платежу з таким номером немає.",
        }.get(name, name)

    # --------------------------------------------------------- PaymentProcessor
    def fee_bps(self) -> int:
        return self.processor.functions.feeBps().call()

    def preview_fee(self, amount_eth: str):
        wei = self._to_wei(amount_eth)
        fee = self.processor.functions.calculateFee(wei).call()
        return (float(Web3.from_wei(fee, "ether")), float(Web3.from_wei(wei - fee, "ether")))

    def pay(self, recipient: str, amount_eth: str):
        if not Web3.is_address(recipient):
            raise ChainError("Некоректна адреса отримувача.")
        return self._send(self.processor.functions.pay(Web3.to_checksum_address(recipient)),
                          self._to_wei(amount_eth))

    def history(self, address=None):
        addr = address or self.address
        rows = self.processor.functions.getUserPayments(addr).call()
        return [
            {
                "from": r[0], "to": r[1],
                "amount": float(Web3.from_wei(r[2], "ether")),
                "fee": float(Web3.from_wei(r[3], "ether")),
                "time": datetime.fromtimestamp(r[4]).strftime("%Y-%m-%d %H:%M:%S"),
            } for r in rows
        ]

    def set_fee_bps(self, bps: int):
        return self._send(self.processor.functions.setFeeBps(int(bps)))

    # ------------------------------------------------------------ FeeCollector
    def stats(self) -> dict:
        p, c = self.processor.functions, self.collector.functions
        return {
            "fee_bps": p.feeBps().call(),
            "total_volume": float(Web3.from_wei(p.totalVolume().call(), "ether")),
            "payments": p.paymentsCount().call(),
            "processor_owner": p.owner().call(),
            "collector_owner": c.owner().call(),
            "collector_balance": float(Web3.from_wei(c.balance().call(), "ether")),
            "total_collected": float(Web3.from_wei(c.totalCollected().call(), "ether")),
            "total_withdrawn": float(Web3.from_wei(c.totalWithdrawn().call(), "ether")),
        }

    def withdraw(self, to: str, amount_eth: str):
        if not Web3.is_address(to):
            raise ChainError("Некоректна адреса для виведення.")
        return self._send(self.collector.functions.withdraw(Web3.to_checksum_address(to),
                                                            self._to_wei(amount_eth)))

    def withdraw_all(self):
        return self._send(self.collector.functions.withdrawAll())

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _to_wei(amount_eth: str) -> int:
        try:
            value = Web3.to_wei(str(amount_eth).replace(",", ".").strip(), "ether")
        except Exception as e:  # noqa: BLE001
            raise ChainError("Некоректна сума. Приклад: 0.5") from e
        if value <= 0:
            raise ChainError("Сума має бути більшою за 0.")
        return value
