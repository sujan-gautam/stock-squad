"""Run the main app workflows in a temporary folder using a real Kivy window."""
import csv
import base64
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup

from stock_squad.app import StockSquadApp
from stock_squad.models import Inventory, Settings
from stock_squad.widgets import Action, Entry


def main():
    folder = TemporaryDirectory()
    app = StockSquadApp(data_dir=folder.name)
    failures = []
    captures = os.environ.get("STOCK_SQUAD_SCREENSHOTS")

    def capture(name):
        if captures:
            path = Path(captures)
            path.mkdir(parents=True, exist_ok=True)
            def take(*_):
                Window.unbind(on_flip=take)
                saved = Window.screenshot(name=str(path / f"{name}.png"))
                # Kivy adds a sequence number to window screenshots.
                Path(saved).replace(path / f"{name}.png")
            Window.bind(on_flip=take)
            Window.canvas.ask_update()

    def steps():
        assert len(app.manager.screens) == 6
        assert not app.controller.model.items()
        yield
        capture("empty_dashboard")
        yield
        app.open_form()
        form = app.manager.get_screen("add")
        form.save()
        assert form.error.text
        assert not app.controller.model.items()
        form.name_input.text, form.sku.text = "Rice", "R101"
        form.price.text, form.quantity.text, form.limit.text = "4.00", "20", "5"
        picture = Path(folder.name) / "picture.png"
        picture.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aOZkAAAAASUVORK5CYII="))
        form.set_picture(str(picture))
        form.save()
        assert app.manager.current == "details"
        item_id = app.manager.get_screen("details").item_id
        copied = app.controller.model.get(item_id)["image_path"]
        assert copied.startswith("images/")
        assert Path(app.controller.image_file(copied)).read_bytes() == picture.read_bytes()
        yield
        capture("item_details")
        yield
        details = app.manager.get_screen("details")
        details.amount.text, details.reason.text, details.action.text = "3", "Used", "Remove"
        details.change_stock()
        assert app.controller.model.get(item_id)["quantity"] == 17
        details.action.text = "Remove"
        details.amount.text, details.reason.text = "100", "Too much"
        details.change_stock()
        assert app.controller.model.get(item_id)["quantity"] == 17
        yield
        for widget in Window.children:
            if isinstance(widget, Popup):
                widget.dismiss(animation=False)
        yield
        app.open_form()
        form.name_input.text, form.sku.text, form.price.text = "Another rice", "r101", "4.00"
        form.save()
        assert "SKU" in form.error.text
        app.open_form(item_id)
        form.name_input.text = "Brown Rice"
        form.save()
        assert app.controller.model.get(item_id)["name"] == "Brown Rice"
        model = app.controller.model
        model.add_item("Milk", "M102", "3.00", "12", "4")
        eggs = model.add_item("Eggs", "E103", "2.50", "2", "5")
        model.add_item("Bread", "B104", "2.00", "1", "4")
        app.go("dashboard")
        yield
        capture("dashboard")
        yield
        app.go("inventory")
        inventory = app.manager.get_screen("inventory")
        inventory.field.text, inventory.minimum.text = "Quantity", "10"
        inventory.apply()
        assert len(inventory.results.children[0].records) == 2
        inventory.clear()
        inventory.results.children[0].sort(3)
        assert inventory.results.children[0].records[0][1][3] == 200
        yield
        capture("inventory")
        yield
        app.open_form()
        yield
        capture("add_item")
        yield
        app.go("reports")
        reports = app.manager.get_screen("reports")
        reports.kind.text = "Stock Movement"
        reports.generate()
        assert reports.table is not None and not reports.save_button.disabled
        reports.table.sort(0)
        reports.save_csv()
        yield
        popups = [w for w in Window.children if isinstance(w, Popup)]
        assert popups
        popup = popups[0]
        chooser = next(w for w in popup.walk() if isinstance(w, FileChooserListView))
        chooser.path = folder.name
        filename = next(w for w in popup.walk() if isinstance(w, Entry))
        filename.text = "ui_report.csv"
        next(w for w in popup.walk() if isinstance(w, Action) and w.text == "Save").dispatch("on_release")
        yield
        report_file = Path(folder.name) / "ui_report.csv"
        assert report_file.exists()
        with report_file.open(encoding="utf-8-sig", newline="") as stream:
            exported = list(csv.reader(stream))
        assert len(exported) > 1 and exported[0][0] == "Item"
        capture("reports")
        yield
        reports.item.text = next(k for k in reports.item_ids if "E103" in k)
        assert reports.save_button.disabled and reports.table is None
        app.go("settings")
        prefs = app.manager.get_screen("settings")
        prefs.theme.text, prefs.text_size.text, prefs.limit.text = "Dark", "Large", "9"
        prefs.save()
        assert prefs.status.text == "Settings saved."
        assert app.font_size == 20
        yield
        capture("settings_dark_large")
        yield
        app.open_form()
        assert form.limit.text == "9"
        assert model.get(item_id)["stock_limit"] == 5
        app.go("inventory")
        yield
        capture("inventory_dark_large")
        yield
        Window.size = (900, 600)
        yield
        capture("inventory_small_window")
        yield
        Window.size = (1200, 820)
        prefs.theme.text, prefs.text_size.text = "Light", "Medium"
        prefs.save()
        app.go("settings")
        yield
        capture("settings")
        yield
        app.open_item(eggs)
        app.manager.get_screen("details").remove()
        yield
        popup = next(w for w in Window.children if isinstance(w, Popup))
        next(w for w in popup.walk() if isinstance(w, Action) and w.text == "Confirm").dispatch("on_release")
        assert app.manager.current == "inventory"
        assert model.get(eggs, include_removed=True)["active"] == 0
        assert model.history(eggs)
        reopened = Inventory(Path(folder.name) / "inventory.db")
        assert reopened.get(item_id)["quantity"] == 17
        reopened.close()
        saved = Settings(Path(folder.name) / "settings.ini")
        assert saved.values["stock_limit"] == "9"
        print("PASS: six pages, item form, stock changes, filters, numeric sorting, CSV dialog, settings, removal, and saved data")

    sequence = steps()
    def advance(_):
        try:
            next(sequence)
            Clock.schedule_once(advance, 0.4)
        except StopIteration:
            app.stop()
        except Exception as exc:
            failures.append(exc)
            app.stop()
    Clock.schedule_once(advance, 0.4)
    try:
        app.run()
    finally:
        folder.cleanup()
    if failures:
        raise failures[0]


if __name__ == "__main__":
    main()
