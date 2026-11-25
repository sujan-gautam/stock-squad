from pathlib import Path
import os

from kivy.app import App
from kivy.core.window import Window
from kivy.properties import ListProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, NoTransition

from .controller import Controller
from .widgets import Text, Panel, action
from .views import Dashboard, InventoryPage, ItemForm, ItemDetails, Reports, Preferences


class StockSquadApp(App):
    title = "Stock Squad"
    font_size = NumericProperty(16)
    background = ListProperty([0.96, 0.97, 0.98, 1])
    surface = ListProperty([1, 1, 1, 1])
    control = ListProperty([0.91, 0.93, 0.95, 1])
    ink = ListProperty([0.09, 0.13, 0.17, 1])
    muted = ListProperty([0.34, 0.39, 0.44, 1])
    sidebar = ListProperty([0.09, 0.13, 0.17, 1])
    accent = ListProperty([0.95, 0.77, 0.30, 1])
    accent_text = ListProperty([0.09, 0.13, 0.17, 1])
    danger = ListProperty([0.65, 0.17, 0.17, 1])

    def __init__(self, data_dir=None, **kwargs):
        super().__init__(**kwargs)
        default = Path(__file__).resolve().parents[1] / "data"
        self.controller = Controller(data_dir or os.environ.get("STOCK_SQUAD_DATA_DIR", default))

    def build(self):
        Window.size = (1200, 820)
        Window.minimum_width, Window.minimum_height = 900, 600
        self.apply_settings()
        root = Panel(variant="background")
        sidebar = Panel(orientation="vertical", variant="side", size_hint_x=None,
                        width=190, padding=16, spacing=12)
        sidebar.add_widget(Text(text="STOCK\nSQUAD", heading=True, side=True, height=100))
        self.navigation = {}
        for label, name in (("Dashboard", "dashboard"), ("Inventory", "inventory"),
                            ("Add Item", "add"), ("Reports", "reports"), ("Settings", "settings")):
            callback = (lambda: self.open_form()) if name == "add" else (lambda n=name: self.go(n))
            button = action(label, callback)
            sidebar.add_widget(button)
            self.navigation[name] = button
        sidebar.add_widget(BoxLayout())
        root.add_widget(sidebar)
        self.manager = ScreenManager(transition=NoTransition())
        for cls, name in ((Dashboard, "dashboard"), (InventoryPage, "inventory"), (ItemForm, "add"),
                          (ItemDetails, "details"), (Reports, "reports"), (Preferences, "settings")):
            self.manager.add_widget(cls(name=name))
        root.add_widget(self.manager)
        self.go("dashboard")
        return root

    def apply_settings(self):
        values = self.controller.settings.values
        self.font_size = {"Small": 14, "Medium": 16, "Large": 20}[values["text_size"]]
        if values["theme"] == "Dark":
            self.background = [0.075, 0.09, 0.11, 1]
            self.surface = [0.12, 0.14, 0.17, 1]
            self.control = [0.20, 0.23, 0.27, 1]
            self.ink = [0.95, 0.96, 0.98, 1]
            self.muted = [0.72, 0.77, 0.82, 1]
        else:
            self.background = [0.96, 0.97, 0.98, 1]
            self.surface = [1, 1, 1, 1]
            self.control = [0.91, 0.93, 0.95, 1]
            self.ink = [0.09, 0.13, 0.17, 1]
            self.muted = [0.34, 0.39, 0.44, 1]
        Window.clearcolor = self.background

    def go(self, name):
        if self.manager.current == name:
            self.manager.get_screen(name).refresh()
        else:
            self.manager.current = name
        for key, button in self.navigation.items():
            button.primary = key == name or (key == "inventory" and name == "details")

    def open_form(self, item_id=None):
        self.manager.get_screen("add").load(item_id)
        self.go("add")

    def open_item(self, item_id):
        self.manager.get_screen("details").item_id = item_id
        self.go("details")

    def on_stop(self):
        self.controller.model.close()
