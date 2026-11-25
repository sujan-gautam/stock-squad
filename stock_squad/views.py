from datetime import date
from pathlib import Path
import sqlite3

from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.screenmanager import Screen

from .models import export_csv, money, whole_number
from .widgets import (Text, Panel, DataTable, action, column, row,
                      input_field, scroll_content, choose_file, confirm, message_popup)


class Page(Screen):
    title = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = Panel(orientation="vertical", variant="background")
        self.add_widget(self.layout)
        self.content = scroll_content(self.layout)

    @property
    def app(self):
        return App.get_running_app()

    @property
    def model(self):
        return self.app.controller.model

    def heading(self, subtitle):
        self.content.add_widget(Text(text=self.title, heading=True))
        self.content.add_widget(Text(text=subtitle, muted=True))

    def card(self, title=""):
        panel = column(10, 16, panel=True)
        if title:
            panel.add_widget(Text(text=title, heading=True))
        self.content.add_widget(panel)
        return panel

    def on_pre_enter(self, *_):
        self.refresh()

    def refresh(self):
        pass

    def attempt(self, operation, success=None):
        try:
            result = operation()
        except (ValueError, OSError, sqlite3.Error) as exc:
            message_popup("Could not save", str(exc))
            return None
        if success:
            success(result)
        return result


class Dashboard(Page):
    title = "Dashboard"

    def refresh(self):
        self.content.clear_widgets()
        self.heading("A quick look at your inventory.")
        summary = self.model.summary()
        cards = []
        for title, value in (("Item listings", summary["listings"]), ("Total units", summary["units"]),
                             ("Stock value", money(summary["value"]))):
            card = column(6, 12, panel=True)
            card.add_widget(Text(text=title, muted=True))
            card.add_widget(Text(text=str(value), heading=True))
            cards.append(card)
        self.content.add_widget(row(*cards))
        self.content.add_widget(Text(text="Stock value leaves out items without a price.", muted=True))
        self.content.add_widget(row(action("Add Item", lambda: self.app.open_form(), True),
                                    action("View Inventory", lambda: self.app.go("inventory"))))
        restocks = column(10, 12, panel=True)
        alerts = column(10, 12, panel=True)
        restocks.add_widget(Text(text="Recent Restocks", heading=True))
        alerts.add_widget(Text(text="Low Stock Alerts", heading=True))
        self.content.add_widget(row(restocks, alerts))
        data = [(r["item_id"], [r["name"], r["sku"], r["delta"], r["created_at"].replace("T", " ")])
                for r in self.model.restocks()]
        restocks.add_widget(DataTable(["Item", "SKU", "Added", "Date and time"], data,
                                      [150, 85, 75, 200], on_select=self.app.open_item))
        items = self.model.find(low_only=True)
        alerts.add_widget(Text(text="Select an item to open it.", muted=True))
        alerts.add_widget(DataTable(["Item", "SKU", "In stock", "Limit"], [
            (i["id"], [i["name"], i["sku"], i["quantity"], i["stock_limit"]]) for i in items],
            [150, 85, 85, 80], on_select=self.app.open_item))


class InventoryPage(Page):
    title = "Inventory"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.heading("Search, filter, or select an item. Click a column heading to sort.")
        search = column(8)
        self.search = input_field(search, "Search all stored item fields")
        self.content.add_widget(search)
        filters = self.card("Filters")
        line = row()
        self.field = input_field(line, "Field", "All fields", ["All fields", *self.model.columns])
        self.contains = input_field(line, "Contains")
        filters.add_widget(Text(text="From and To accept numbers or restock dates (YYYY-MM-DD).", muted=True))
        filters.add_widget(line)
        line = row()
        self.minimum = input_field(line, "From")
        self.maximum = input_field(line, "To")
        self.stock_mode = input_field(line, "Stock", "All items", ["All items", "Low stock"])
        filters.add_widget(line)
        filters.add_widget(row(action("Apply", self.apply, True), action("Clear", self.clear),
                               action("Add Item", lambda: self.app.open_form())))
        self.error = Text(text="", muted=True)
        self.content.add_widget(self.error)
        self.results = column(6)
        self.content.add_widget(self.results)

    def clear(self):
        self.search.text = self.contains.text = self.minimum.text = self.maximum.text = ""
        self.field.text = "All fields"
        self.stock_mode.text = "All items"
        self.apply()

    def refresh(self):
        self.apply()

    def apply(self):
        try:
            items = self.model.find(self.search.text, self.field.text, self.contains.text,
                                    self.minimum.text, self.maximum.text, self.stock_mode.text == "Low stock")
        except ValueError as exc:
            self.error.text = str(exc)
            return
        self.error.text = f"{len(items)} item(s). Select a row to open Item Details."
        self.results.clear_widgets()
        self.results.add_widget(DataTable(
            ["Name", "SKU", "Quantity", "Price", "Restocked", "Stock limit", "Picture"],
            [(i["id"], [i["name"], i["sku"], i["quantity"], i["price_cents"],
                        i["restocked_at"][:10] if i["restocked_at"] else None,
                        i["stock_limit"], Path(i["image_path"]).name]) for i in items],
            [220, 150, 120, 130, 160, 120, 170], on_select=self.app.open_item,
            formatters={3: money}))


class ItemForm(Page):
    title = "Add Item"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.item_id = None
        self.image_source = ""
        self.title_label = Text(text=self.title, heading=True)
        self.content.add_widget(self.title_label)
        card = self.card()
        self.name_input = input_field(card, "Item name *")
        self.sku = input_field(card, "SKU *")
        self.price = input_field(card, "Price (optional, for example 4.50)")
        self.quantity = input_field(card, "Starting quantity *", "0")
        self.limit = input_field(card, "Low-stock limit *", "5")
        self.image = Image(size_hint_y=None, height=dp(170), fit_mode="contain")
        card.add_widget(self.image)
        self.picture_label = Text(text="No picture selected.", muted=True)
        card.add_widget(self.picture_label)
        card.add_widget(row(action("Choose Picture", self.choose_picture), action("Clear Picture", self.clear_picture)))
        self.error = Text(text="", muted=True)
        card.add_widget(self.error)
        card.add_widget(row(action("Save Item", self.save, True), action("Cancel", self.cancel)))

    def load(self, item_id=None):
        self.item_id = item_id
        item = self.model.get(item_id) if item_id is not None else None
        self.title_label.text = "Edit Item" if item else "Add Item"
        self.name_input.text = item["name"] if item else ""
        self.sku.text = item["sku"] if item else ""
        cents = item["price_cents"] if item else None
        self.price.text = f"{cents // 100}.{cents % 100:02d}" if cents is not None else ""
        self.quantity.text = str(item["quantity"] if item else 0)
        self.quantity.disabled = bool(item)
        self.limit.text = str(item["stock_limit"] if item else self.app.controller.settings.values["stock_limit"])
        self.set_picture(self.app.controller.image_file(item["image_path"]) if item else "")
        self.error.text = "Change stock on Item Details, not in this form." if item else ""

    def refresh(self):
        pass

    def set_picture(self, path):
        self.image_source = path
        self.image.source = path
        self.picture_label.text = Path(path).name if path else "No picture selected."

    def clear_picture(self):
        self.set_picture("")

    def choose_picture(self):
        choose_file(self.set_picture)

    def cancel(self):
        self.app.open_item(self.item_id) if self.item_id else self.app.go("inventory")

    def save(self):
        try:
            item_id = self.app.controller.save_item(self.item_id, self.name_input.text, self.sku.text,
                self.price.text, self.quantity.text, self.limit.text, self.image_source)
        except (ValueError, OSError, sqlite3.Error) as exc:
            self.error.text = str(exc)
            return
        self.app.open_item(item_id)


class ItemDetails(Page):
    title = "Item Details"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.item_id = None

    def refresh(self):
        self.content.clear_widgets()
        self.heading("View an item and record stock changes.")
        self.content.add_widget(action("Back to Inventory", lambda: self.app.go("inventory")))
        if self.item_id is None:
            return
        try:
            item = self.model.get(self.item_id)
        except ValueError:
            self.content.add_widget(Text(text="This listing has been removed."))
            return
        card = self.card(item["name"])
        if item["image_path"]:
            card.add_widget(Image(source=self.app.controller.image_file(item["image_path"]),
                                  size_hint_y=None, height=dp(150), fit_mode="contain"))
        card.add_widget(Text(text=f"SKU: {item['sku']}    |    In stock: {item['quantity']}"))
        card.add_widget(Text(text=f"Price: {money(item['price_cents']) or 'Not set'}    |    Stock limit: {item['stock_limit']}"))
        card.add_widget(Text(text=f"Last restock: {(item['restocked_at'] or 'Not restocked').replace('T', ' ')}", muted=True))
        line = row()
        self.action = input_field(line, "Action", "Add", ["Add", "Remove"])
        self.amount = input_field(line, "Quantity")
        card.add_widget(line)
        self.reason = input_field(card, "Reason *")
        self.preview = Text(text="Enter a quantity to see the new stock total.", muted=True)
        card.add_widget(self.preview)
        def preview(*_):
            try:
                number = whole_number(self.amount.text, "Quantity", positive=True)
                total = item["quantity"] + (number if self.action.text == "Add" else -number)
                self.preview.text = f"New stock after change: {total}" if total >= 0 else "Not enough stock for this removal."
            except ValueError:
                self.preview.text = "Enter a positive whole-number quantity."
        self.amount.bind(text=preview)
        self.action.bind(text=preview)
        card.add_widget(row(action("Confirm Change", self.change_stock, True),
                            action("Edit Item", lambda: self.app.open_form(self.item_id)),
                            action("Remove Listing", self.remove, danger=True)))
        history = self.card("Stock History")
        history.add_widget(DataTable(["Date and time", "Change", "Reason"], [
            (r["id"], [r["created_at"].replace("T", " "), r["delta"], r["reason"]])
            for r in self.model.history(self.item_id)], [230, 110, 400]))

    def change_stock(self):
        self.attempt(lambda: self.model.change_stock(self.item_id, self.action.text, self.amount.text, self.reason.text),
                     lambda _: self.refresh())

    def remove(self):
        item = self.model.get(self.item_id)
        confirm("Remove listing", f"Remove {item['name']} from active inventory? Its history will be kept.",
                lambda: self.attempt(lambda: self.model.remove_item(self.item_id), lambda _: self.app.go("inventory")))


class Reports(Page):
    title = "Reports"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.heading("Review inventory and save a report.")
        card = self.card("Report Filters")
        self.kind = input_field(card, "Report type", "Low Stock",
                               ["Low Stock", "Stock Movement", "Highest Movement", "Lowest Movement"])
        line = row()
        today = date.today()
        self.start = input_field(line, "From (YYYY-MM-DD)", today.replace(day=1).isoformat())
        self.end = input_field(line, "To (YYYY-MM-DD)", today.isoformat())
        card.add_widget(line)
        self.item = input_field(card, "Item", "All items", ["All items"])
        card.add_widget(Text(text="Low Stock uses current quantities. Movement rankings use units removed, not sales.", muted=True))
        self.save_button = action("Save CSV", self.save_csv)
        self.save_button.disabled = True
        card.add_widget(row(action("Generate", self.generate, True), self.save_button))
        self.status = Text(text="Choose your filters, then Generate.", muted=True)
        self.content.add_widget(self.status)
        self.results = column(8)
        self.content.add_widget(self.results)
        self.table = None
        self.headers = []
        for widget in (self.kind, self.start, self.end, self.item):
            widget.bind(text=self.invalidate)
        self.kind.bind(text=self.toggle_dates)
        self.toggle_dates()

    def toggle_dates(self, *_):
        self.start.disabled = self.end.disabled = self.kind.text == "Low Stock"

    def invalidate(self, *_):
        self.save_button.disabled = True
        self.table = None
        self.results.clear_widgets()
        self.status.text = "Filters changed. Select Generate to load current results."

    def refresh(self):
        self.item_ids = {f"{i['name']} | {i['sku']}" + (" (removed)" if not i["active"] else ""): i["id"]
                         for i in self.model.items(include_removed=True)}
        self.item.values = ["All items", *self.item_ids]
        if self.item.text not in self.item.values:
            self.item.text = "All items"
        self.invalidate()

    def generate(self):
        try:
            item_id = None if self.item.text == "All items" else self.item_ids[self.item.text]
            self.headers, records = self.model.report(self.kind.text, self.start.text, self.end.text, item_id)
        except (ValueError, KeyError, sqlite3.Error) as exc:
            self.status.text = str(exc)
            self.save_button.disabled = True
            return
        self.results.clear_widgets()
        self.table = DataTable(self.headers, [(i, r) for i, r in enumerate(records)],
                               [220 if h in ("Item", "Date and time") else 320 if h == "Reason" else 140 for h in self.headers])
        self.results.add_widget(self.table)
        self.status.text = f"{len(records)} result(s). Click headings to sort."
        if self.kind.text == "Stock Movement":
            added = sum(r[3] for r in records if r[3] > 0)
            removed = -sum(r[3] for r in records if r[3] < 0)
            self.status.text += f" Added: {added} | Removed: {removed} | Net change: {added - removed}"
        self.save_button.disabled = False

    def save_csv(self):
        if self.table is None:
            return
        headers = list(self.headers)
        records = [list(values) for _, values in self.table.records]
        def save(path):
            export_csv(path, headers, records)
            self.status.text = f"Report saved to {path}"
        choose_file(save, save=True, title="Save report as CSV")


class Preferences(Page):
    title = "Settings"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.heading("Choose how the app looks and set the default stock limit.")
        card = self.card("App Preferences")
        self.theme = input_field(card, "Color theme", "Light", ["Light", "Dark"])
        self.text_size = input_field(card, "Text size", "Medium", ["Small", "Medium", "Large"])
        self.limit = input_field(card, "Default low-stock limit", "5")
        card.add_widget(Text(text="The default is used for new items. It does not change existing item limits.", muted=True))
        card.add_widget(action("Save Settings", self.save, True))
        self.status = Text(text="", muted=True)
        card.add_widget(self.status)

    def refresh(self):
        values = self.app.controller.settings.values
        self.theme.text, self.text_size.text, self.limit.text = values["theme"], values["text_size"], values["stock_limit"]
        self.status.text = self.app.controller.settings.warning

    def save(self):
        try:
            self.app.controller.settings.save(self.theme.text, self.text_size.text, self.limit.text)
        except (ValueError, OSError) as exc:
            self.status.text = str(exc)
            return
        self.app.apply_settings()
        self.status.text = "Settings saved."

