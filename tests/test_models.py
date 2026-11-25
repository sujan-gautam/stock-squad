import csv
from datetime import date
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from stock_squad.controller import Controller
from stock_squad.models import Inventory, Settings, export_csv, price_to_cents


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.path = Path(self.folder.name) / "inventory.db"
        self.model = Inventory(self.path)

    def tearDown(self):
        self.model.close()
        self.folder.cleanup()

    def add(self, sku="R1", **changes):
        data = dict(name="Rice", sku=sku, price="4.25", quantity="10", stock_limit="5")
        data.update(changes)
        return self.model.add_item(**data)

    def test_item_and_initial_history_are_saved(self):
        item_id = self.add()
        self.assertEqual(self.model.get(item_id)["price_cents"], 425)
        self.assertEqual(self.model.history(item_id)[0]["delta"], 10)
        other = Inventory(self.path)
        try:
            self.assertEqual(other.get(item_id)["quantity"], 10)
        finally:
            other.close()

    def test_duplicate_sku_is_case_insensitive(self):
        self.add()
        with self.assertRaisesRegex(ValueError, "SKU"):
            self.add(sku="r1")
        self.assertEqual(len(self.model.items()), 1)

    def test_input_checks(self):
        for changes in ({"name": ""}, {"sku": ""}, {"price": "-1"}, {"price": "nan"},
                        {"price": "1.005"}, {"quantity": "-1"}, {"quantity": "1.5"},
                        {"stock_limit": "x"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.add(**changes)
        self.assertFalse(self.model.items())

    def test_money_uses_exact_cents(self):
        self.assertEqual(price_to_cents("0.29"), 29)
        self.assertEqual(price_to_cents(""), None)
        self.assertEqual(price_to_cents("0"), 0)

    def test_stock_changes_keep_a_history(self):
        item_id = self.add()
        self.assertEqual(self.model.change_stock(item_id, "Remove", "3", "Used"), 7)
        self.assertEqual(self.model.change_stock(item_id, "Add", "2", "Delivery"), 9)
        self.assertEqual(len(self.model.history(item_id)), 3)

    def test_failed_removal_does_not_write_anything(self):
        item_id = self.add()
        before = self.model.get(item_id)
        with self.assertRaisesRegex(ValueError, "more stock"):
            self.model.change_stock(item_id, "Remove", "11", "Used")
        self.assertEqual(self.model.get(item_id), before)
        self.assertEqual(len(self.model.history(item_id)), 1)

    def test_database_failure_rolls_back_stock(self):
        item_id = self.add()
        self.model.connection.execute("""CREATE TRIGGER reject_history BEFORE INSERT ON transactions
            BEGIN SELECT RAISE(ABORT,'test failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.model.change_stock(item_id, "Add", "2", "Delivery")
        self.assertEqual(self.model.get(item_id)["quantity"], 10)

    def test_zero_removal_and_missing_reason_are_rejected(self):
        item_id = self.add()
        for amount, reason in (("0", "Used"), ("2", " ")):
            with self.assertRaises(ValueError):
                self.model.change_stock(item_id, "Remove", amount, reason)

    def test_edit_changes_details_but_not_stock(self):
        item_id = self.add()
        self.model.edit_item(item_id, "Brown rice", "B1", "", "12", "")
        item = self.model.get(item_id)
        self.assertEqual((item["name"], item["quantity"], item["price_cents"]), ("Brown rice", 10, None))
        self.assertEqual(len(self.model.find(low_only=True)), 1)

    def test_removed_listing_keeps_history_and_sku(self):
        item_id = self.add()
        self.model.remove_item(item_id)
        self.assertFalse(self.model.items())
        self.assertEqual(len(self.model.history(item_id)), 1)
        self.assertEqual(self.model.summary()["units"], 0)
        with self.assertRaises(ValueError):
            self.model.change_stock(item_id, "Add", "1", "Delivery")
        with self.assertRaises(ValueError):
            self.add()

    def test_summary_and_low_stock_boundary(self):
        self.add(quantity="5", stock_limit="5")
        self.add(sku="B1", name="Bread", price="", quantity="2", stock_limit="3")
        self.assertEqual(self.model.summary(), {"listings": 2, "units": 7, "value": 2125})
        self.assertEqual(self.model.find(low_only=True)[0]["sku"], "B1")

    def test_search_and_field_filters(self):
        item_id = self.add(image_path="images/rice.png")
        self.assertEqual(self.model.find(search="rIcE")[0]["id"], item_id)
        self.assertEqual(len(self.model.find(field="SKU", contains="r1")), 1)
        self.assertEqual(len(self.model.find(field="Picture", contains="rice.png")), 1)
        self.assertEqual(len(self.model.find(field="Price", minimum="4.00", maximum="4.25")), 1)
        self.assertFalse(self.model.find(field="Quantity", minimum="11"))
        self.assertEqual(len(self.model.find(field="Stock limit", minimum="5", maximum="5")), 1)
        today = date.today().isoformat()
        self.assertEqual(len(self.model.find(field="Restocked", minimum=today, maximum=today)), 1)

    def test_bad_ranges_are_rejected(self):
        for fields in (dict(field="Quantity", minimum="6", maximum="2"),
                       dict(field="Restocked", minimum="yesterday"), dict(minimum="4")):
            with self.assertRaises(ValueError):
                self.model.find(**fields)

    def test_movement_report_uses_inclusive_end_date(self):
        item_id = self.add()
        self.model.change_stock(item_id, "Remove", "2", "Used")
        today = date.today().isoformat()
        headers, rows = self.model.report("Stock Movement", today, today)
        self.assertEqual(sum(row[3] for row in rows), 8)
        self.assertEqual(len(rows), 2)
        self.assertEqual(headers[3], "Change")

    def test_movement_rankings_and_removed_items(self):
        first = self.add()
        second = self.add(sku="B1", name="Bread")
        third = self.add(sku="M1", name="Milk")
        self.model.change_stock(first, "Remove", "3", "Used")
        self.model.change_stock(second, "Remove", "1", "Used")
        self.model.remove_item(first)
        today = date.today().isoformat()
        _, high = self.model.report("Highest Movement", today, today)
        _, low = self.model.report("Lowest Movement", today, today)
        self.assertEqual(high[0][1:], ["R1", 3])
        self.assertEqual(low[0][1:], ["M1", 0])
        self.assertEqual(len(self.model.report("Stock Movement", today, today, second)[1]), 2)

    def test_low_stock_report_does_not_use_dates(self):
        item_id = self.add(quantity="0")
        _, rows = self.model.report("Low Stock", "", "", item_id)
        self.assertEqual(rows[0][2:], [0, 5])

    def test_invalid_report_dates(self):
        for start, end in (("2026-02-30", "2026-03-01"), ("2026-04-02", "2026-04-01"), ("", "")):
            with self.assertRaises(ValueError):
                self.model.report("Stock Movement", start, end)

    def test_csv_handles_quotes_unicode_and_formula_text(self):
        path = Path(self.folder.name) / "report.csv"
        export_csv(path, ["Item", "Change"], [['Rice, "brown"', -2], ["=SUM(A1)", 0], ["Café", 4]])
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        self.assertEqual(rows[1], ['Rice, "brown"', "-2"])
        self.assertTrue(rows[2][0].startswith("'="))
        self.assertEqual(rows[3][0], "Café")


class SettingsTests(unittest.TestCase):
    def test_preferences_survive_reopening_and_do_not_change_items(self):
        with TemporaryDirectory() as folder:
            controller = Controller(folder)
            item_id = controller.model.add_item("Rice", "R1", "", "0", "5")
            controller.settings.save("Dark", "Large", "9")
            self.assertEqual(Settings(Path(folder) / "settings.ini").values,
                             {"theme": "Dark", "text_size": "Large", "stock_limit": "9"})
            self.assertEqual(controller.model.get(item_id)["stock_limit"], 5)
            controller.model.close()

    def test_invalid_settings_leave_previous_values(self):
        with TemporaryDirectory() as folder:
            settings = Settings(Path(folder) / "settings.ini")
            settings.save("Light", "Small", "4")
            for args in (("Blue", "Small", "4"), ("Light", "Tiny", "4"), ("Dark", "Large", "-2")):
                with self.assertRaises(ValueError):
                    settings.save(*args)
            self.assertEqual(settings.values["stock_limit"], "4")


if __name__ == "__main__":
    unittest.main()
