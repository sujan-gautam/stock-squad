from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
import configparser
import csv
import os
import sqlite3


MAX_NUMBER = 1_000_000_000


def whole_number(value, label, positive=False):
    text = str(value).strip()
    if not text.isascii() or not text.isdigit():
        raise ValueError(f"{label} must be a whole number.")
    number = int(text)
    if number > MAX_NUMBER or (positive and number == 0):
        raise ValueError(f"{label} must be between {1 if positive else 0} and {MAX_NUMBER:,}.")
    return number


def price_to_cents(value):
    if not str(value).strip():
        return None
    try:
        amount = Decimal(str(value).strip())
        if not amount.is_finite() or amount < 0 or amount > MAX_NUMBER:
            raise ValueError
        if amount * 100 != (amount * 100).to_integral_value():
            raise ValueError
        return int(amount * 100)
    except (InvalidOperation, ValueError):
        raise ValueError("Price must be zero or more, with at most two decimal places.") from None


def money(cents):
    return "" if cents is None else f"${cents // 100:,}.{cents % 100:02d}"


def check_dates(start, end):
    try:
        first = date.fromisoformat(start)
        last = date.fromisoformat(end)
        if first > last:
            raise ValueError
        return first.isoformat(), (last + timedelta(days=1)).isoformat()
    except (ValueError, TypeError, OverflowError):
        raise ValueError("Enter a valid From and To date as YYYY-MM-DD, with From first.") from None


class Settings:
    def __init__(self, path):
        self.path = Path(path)
        self.values = {"theme": "Light", "text_size": "Medium", "stock_limit": "5"}
        self.warning = ""
        if self.path.exists():
            try:
                config = configparser.ConfigParser()
                config.read(self.path, encoding="utf-8")
                self.values = self.validate(dict(config["preferences"]))
            except (configparser.Error, KeyError, ValueError, OSError):
                self.warning = "Saved settings could not be read. Default settings are in use."

    @staticmethod
    def validate(values):
        if values.get("theme") not in ("Light", "Dark"):
            raise ValueError("Choose Light or Dark.")
        if values.get("text_size") not in ("Small", "Medium", "Large"):
            raise ValueError("Choose Small, Medium, or Large text.")
        limit = whole_number(values.get("stock_limit", ""), "Stock limit")
        return {"theme": values["theme"], "text_size": values["text_size"], "stock_limit": str(limit)}

    def save(self, theme, text_size, stock_limit):
        values = self.validate(dict(theme=theme, text_size=text_size, stock_limit=stock_limit))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        config = configparser.ConfigParser()
        config["preferences"] = values
        temp = self.path.with_suffix(".tmp")
        with temp.open("w", encoding="utf-8") as stream:
            config.write(stream)
        os.replace(temp, self.path)
        self.values = values
        self.warning = ""


class Inventory:
    columns = {
        "Name": "name", "SKU": "sku", "Quantity": "quantity", "Price": "price_cents",
        "Restocked": "restocked_at", "Stock limit": "stock_limit", "Picture": "image_path",
    }

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                sku TEXT NOT NULL COLLATE NOCASE UNIQUE,
                quantity INTEGER NOT NULL CHECK(quantity >= 0),
                price_cents INTEGER CHECK(price_cents >= 0),
                stock_limit INTEGER NOT NULL CHECK(stock_limit >= 0),
                image_path TEXT NOT NULL DEFAULT '',
                restocked_at TEXT,
                created_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY,
                item_id INTEGER NOT NULL REFERENCES items(id),
                delta INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('initial','add','remove'))
            );
            CREATE INDEX IF NOT EXISTS transaction_item_date ON transactions(item_id, created_at);
        """)

    @contextmanager
    def write(self):
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            yield self.connection
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    @staticmethod
    def fields(name, sku, price, stock_limit):
        name, sku = name.strip(), sku.strip().upper()
        if not name or len(name) > 100:
            raise ValueError("Enter an item name with 1 to 100 characters.")
        if not sku or len(sku) > 64:
            raise ValueError("Enter a SKU with 1 to 64 characters.")
        return name, sku, price_to_cents(price), whole_number(stock_limit, "Stock limit")

    def add_item(self, name, sku, price, quantity, stock_limit, image_path=""):
        name, sku, cents, limit = self.fields(name, sku, price, stock_limit)
        quantity = whole_number(quantity, "Starting quantity")
        now = datetime.now().isoformat(timespec="seconds")
        try:
            with self.write() as db:
                cursor = db.execute("""INSERT INTO items
                    (name,sku,price_cents,quantity,stock_limit,image_path,restocked_at,created_at)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (name, sku, cents, quantity, limit, image_path, now if quantity else None, now))
                item_id = cursor.lastrowid
                db.execute("INSERT INTO transactions(item_id,delta,reason,created_at,kind) VALUES (?,?,?,?,?)",
                           (item_id, quantity, "Starting stock", now, "initial"))
                return item_id
        except sqlite3.IntegrityError as exc:
            if "sku" in str(exc).lower():
                raise ValueError("That SKU is already used, including removed listings.") from None
            raise

    def get(self, item_id, include_removed=False):
        item = self.connection.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if item is None or (not item["active"] and not include_removed):
            raise ValueError("This item is no longer in the active inventory.")
        return dict(item)

    def edit_item(self, item_id, name, sku, price, stock_limit, image_path):
        name, sku, cents, limit = self.fields(name, sku, price, stock_limit)
        try:
            with self.write() as db:
                self.get(item_id)
                db.execute("UPDATE items SET name=?,sku=?,price_cents=?,stock_limit=?,image_path=? WHERE id=?",
                           (name, sku, cents, limit, image_path, item_id))
        except sqlite3.IntegrityError:
            raise ValueError("That SKU is already used, including removed listings.") from None

    def change_stock(self, item_id, action, quantity, reason):
        quantity = whole_number(quantity, "Quantity", positive=True)
        if action not in ("Add", "Remove"):
            raise ValueError("Choose Add or Remove.")
        reason = reason.strip()
        if not reason or len(reason) > 240:
            raise ValueError("Enter a reason with 1 to 240 characters.")
        delta = quantity if action == "Add" else -quantity
        now = datetime.now().isoformat(timespec="seconds")
        with self.write() as db:
            item = self.get(item_id)
            total = item["quantity"] + delta
            if total < 0:
                raise ValueError("You cannot remove more stock than is available.")
            if total > MAX_NUMBER:
                raise ValueError(f"Stock cannot exceed {MAX_NUMBER:,} units.")
            db.execute("UPDATE items SET quantity=?, restocked_at=? WHERE id=?",
                       (total, now if delta > 0 else item["restocked_at"], item_id))
            db.execute("INSERT INTO transactions(item_id,delta,reason,created_at,kind) VALUES (?,?,?,?,?)",
                       (item_id, delta, reason, now, action.lower()))
        return total

    def remove_item(self, item_id):
        with self.write() as db:
            self.get(item_id)
            db.execute("UPDATE items SET active=0 WHERE id=?", (item_id,))

    def items(self, include_removed=False):
        sql = "SELECT * FROM items" + ("" if include_removed else " WHERE active=1") + " ORDER BY name COLLATE NOCASE"
        return [dict(row) for row in self.connection.execute(sql)]

    def find(self, search="", field="All fields", contains="", minimum="", maximum="", low_only=False):
        if field not in ("All fields", *self.columns):
            raise ValueError("Choose a valid filter field.")
        lower = upper = None
        column = self.columns.get(field)
        numeric = field in ("Quantity", "Price", "Stock limit")
        if minimum or maximum:
            if numeric:
                parse = price_to_cents if field == "Price" else lambda x: whole_number(x, field)
                lower = parse(minimum) if minimum.strip() else None
                upper = parse(maximum) if maximum.strip() else None
            elif field == "Restocked":
                try:
                    lower = date.fromisoformat(minimum).isoformat() if minimum else None
                    upper = date.fromisoformat(maximum).isoformat() if maximum else None
                except ValueError:
                    raise ValueError("Restock dates must use YYYY-MM-DD.") from None
            else:
                raise ValueError("From and To work with Quantity, Price, Stock limit, or Restocked.")
            if lower is not None and upper is not None and lower > upper:
                raise ValueError("From must not be greater than To.")
        result = []
        for item in self.items():
            if low_only and item["quantity"] >= item["stock_limit"]:
                continue
            values = {label: self.display(item, label) for label in self.columns}
            all_text = " ".join(values.values()).casefold()
            if search.strip().casefold() not in all_text:
                continue
            if contains.strip().casefold() not in (values.get(field, all_text)).casefold():
                continue
            if lower is not None or upper is not None:
                value = item[column]
                if field == "Restocked" and value:
                    value = value[:10]
                if value is None or (lower is not None and value < lower) or (upper is not None and value > upper):
                    continue
            result.append(item)
        return result

    @staticmethod
    def display(item, label):
        value = item[Inventory.columns[label]]
        if label == "Price":
            return money(value)
        if label == "Restocked":
            return value[:10] if value else ""
        return str(value)

    def history(self, item_id):
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM transactions WHERE item_id=? ORDER BY created_at DESC,id DESC", (item_id,))]

    def summary(self):
        return dict(self.connection.execute("""SELECT COUNT(*) AS listings,
            COALESCE(SUM(quantity),0) AS units, COALESCE(SUM(quantity * price_cents),0) AS value
            FROM items WHERE active=1""").fetchone())

    def restocks(self):
        return [dict(row) for row in self.connection.execute("""SELECT t.*,i.name,i.sku FROM transactions t
            JOIN items i ON i.id=t.item_id WHERE i.active=1 AND t.delta>0
            ORDER BY t.created_at DESC,t.id DESC LIMIT 8""")]

    def report(self, report_type, start, end, item_id=None):
        if report_type == "Low Stock":
            rows = self.connection.execute("""SELECT id,name,sku,quantity,stock_limit
                FROM items WHERE active=1 AND quantity<stock_limit AND (? IS NULL OR id=?)
                ORDER BY quantity,name COLLATE NOCASE""", (item_id, item_id))
            return ["Item", "SKU", "Quantity", "Stock limit"], [
                [r["name"], r["sku"], r["quantity"], r["stock_limit"]] for r in rows]
        first, after = check_dates(start, end)
        if report_type == "Stock Movement":
            rows = self.connection.execute("""SELECT i.name,i.sku,t.created_at,t.delta,t.reason
                FROM transactions t JOIN items i ON i.id=t.item_id
                WHERE t.created_at>=? AND t.created_at<? AND (? IS NULL OR i.id=?)
                ORDER BY t.created_at DESC,t.id DESC""", (first, after, item_id, item_id))
            return ["Item", "SKU", "Date and time", "Change", "Reason"], [list(r) for r in rows]
        if report_type in ("Highest Movement", "Lowest Movement"):
            order = "DESC" if report_type == "Highest Movement" else "ASC"
            rows = self.connection.execute(f"""SELECT i.name,i.sku,
                COALESCE(SUM(CASE WHEN t.delta<0 THEN -t.delta ELSE 0 END),0) AS removed
                FROM items i LEFT JOIN transactions t ON t.item_id=i.id AND t.created_at>=? AND t.created_at<?
                WHERE (? IS NULL OR i.id=?) AND (i.active=1 OR t.id IS NOT NULL)
                GROUP BY i.id ORDER BY removed {order},i.name COLLATE NOCASE""", (first, after, item_id, item_id))
            return ["Item", "SKU", "Units removed"], [list(r) for r in rows]
        raise ValueError("Choose a report type.")

    def close(self):
        self.connection.close()


def export_csv(path, headers, rows):
    # A leading apostrophe keeps spreadsheet programs from treating text as a formula.
    def safe(value):
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows([[safe(v) for v in row] for row in rows])
