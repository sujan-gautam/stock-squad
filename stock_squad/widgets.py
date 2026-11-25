from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput


class Text(Label):
    muted = BooleanProperty(False)
    heading = BooleanProperty(False)
    side = BooleanProperty(False)


class Action(Button):
    primary = BooleanProperty(False)
    danger = BooleanProperty(False)


class Choice(Spinner):
    pass


class Entry(TextInput):
    pass


class Panel(BoxLayout):
    variant = StringProperty("surface")


Builder.load_string('''
<Text>:
    color: (1,1,1,1) if self.side else (app.muted if self.muted else app.ink)
    font_size: app.font_size + (7 if self.heading else 0)
    bold: self.heading
    size_hint_y: None
    text_size: self.width, None
    height: max(dp(30), self.texture_size[1] + dp(8))
    halign: 'left'
    valign: 'middle'
    padding: dp(2), dp(2)
    markup: False
<Action>:
    background_normal: ''
    background_down: ''
    background_color: app.danger if self.danger else (app.accent if self.primary else app.control)
    color: (1,1,1,1) if self.danger else (app.accent_text if self.primary else app.ink)
    font_size: app.font_size
    size_hint_y: None
    height: dp(44) + max(0, app.font_size - 16)
    text_size: self.width - dp(10), None
    halign: 'center'
    valign: 'middle'
<Choice>:
    background_normal: ''
    background_color: app.control
    color: app.ink
    font_size: app.font_size
    size_hint_y: None
    height: dp(44) + max(0, app.font_size - 16)
    text_size: self.width - dp(12), None
    halign: 'center'
<SpinnerOption>:
    background_normal: ''
    background_color: app.control
    color: app.ink
    font_size: app.font_size
    height: dp(46)
<Entry>:
    multiline: False
    write_tab: False
    background_normal: ''
    background_active: ''
    background_color: app.control
    foreground_color: app.ink
    cursor_color: app.ink
    hint_text_color: app.muted
    font_size: app.font_size
    size_hint_y: None
    height: dp(44) + max(0, app.font_size - 16)
    padding: dp(10), dp(10)
<Panel>:
    canvas.before:
        Color:
            rgba: app.sidebar if self.variant == 'side' else (app.background if self.variant == 'background' else app.surface)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(8)]
''')


def column(spacing=10, padding=0, panel=False):
    cls = Panel if panel else BoxLayout
    widget = cls(orientation="vertical", size_hint_y=None, spacing=dp(spacing), padding=dp(padding))
    widget.bind(minimum_height=widget.setter("height"))
    return widget


def row(*widgets):
    widget = BoxLayout(size_hint_y=None, spacing=dp(10))
    for child in widgets:
        widget.add_widget(child)
    def fit(*_):
        widget.height = max([dp(44)] + [c.height for c in widget.children])
    def children_changed(*_):
        for child in widget.children:
            child.bind(height=fit)
        Clock.schedule_once(lambda _: fit(), 0)
    widget.bind(children=children_changed)
    children_changed()
    fit()
    return widget


def action(label, callback, primary=False, danger=False):
    widget = Action(text=label, primary=primary, danger=danger)
    widget.bind(on_release=lambda *_: callback())
    return widget


def input_field(parent, label, value="", choices=None):
    wrap = column(4)
    wrap.add_widget(Text(text=label))
    widget = Choice(text=str(value), values=choices) if choices else Entry(text=str(value))
    wrap.add_widget(widget)
    parent.add_widget(wrap)
    return widget


def scroll_content(parent):
    scroll = ScrollView(do_scroll_x=False)
    content = column(14, 16)
    scroll.add_widget(content)
    parent.add_widget(scroll)
    return content


def message_popup(title, text):
    content = column(12, 18, panel=True)
    content.add_widget(Text(text=text))
    popup = Popup(title=title, content=content, size_hint=(0.75, None), height=dp(230))
    content.add_widget(action("Close", popup.dismiss))
    popup.open()
    return popup


def confirm(title, description, callback):
    content = column(14, 18, panel=True)
    content.add_widget(Text(text=description))
    popup = Popup(title=title, content=content, size_hint=(0.8, None), height=dp(250))
    def accept():
        popup.dismiss()
        callback()
    content.add_widget(row(action("Confirm", accept, primary=True), action("Cancel", popup.dismiss)))
    popup.open()
    return popup


def choose_file(callback, save=False, title="Choose a picture"):
    layout = Panel(orientation="vertical", spacing=dp(10), padding=dp(12))
    chooser = FileChooserListView(path=str(Path.home()), dirselect=save)
    if not save:
        chooser.filters = ["*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG"]
    layout.add_widget(chooser)
    filename = Entry(text="inventory_report.csv") if save else None
    if filename:
        layout.add_widget(filename)
    status = Text(text="Choose a folder and enter a filename." if save else "Choose a PNG or JPEG file.", muted=True)
    layout.add_widget(status)
    popup = Popup(title=title, content=layout, size_hint=(0.93, 0.9))
    def finish(path):
        try:
            callback(str(path))
        except (OSError, ValueError) as exc:
            status.text = str(exc)
            return
        popup.dismiss()
    def select():
        if save:
            name = filename.text.strip()
            if not name or Path(name).name != name or "/" in name or "\\" in name:
                status.text = "Enter a filename without a folder path."
                return
            if not name.lower().endswith(".csv"):
                name += ".csv"
            directory = Path(chooser.selection[0]) if chooser.selection and Path(chooser.selection[0]).is_dir() else Path(chooser.path)
            path = directory / name
            if path.exists():
                confirm("Replace file", f"Replace {path.name}?", lambda: finish(path))
            else:
                finish(path)
        elif chooser.selection and Path(chooser.selection[0]).is_file():
            finish(Path(chooser.selection[0]))
        else:
            status.text = "Choose a picture first."
    layout.add_widget(row(action("Save" if save else "Choose", select, primary=True), action("Cancel", popup.dismiss)))
    popup.open()
    return popup


class DataTable(BoxLayout):
    """A horizontally scrollable table with sortable headings and selectable rows."""
    def __init__(self, headers, records, widths=None, on_select=None, formatters=None, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, spacing=dp(2), **kwargs)
        self.headers, self.records = headers, list(records)
        self.widths = widths or [max(140, len(h) * 10) for h in headers]
        self.on_select = on_select
        self.formatters = formatters or {}
        self.sort_column = None
        self.reverse = False
        self.scroll = ScrollView(do_scroll_y=False, size_hint_y=None)
        self.grid = column(2)
        self.grid.size_hint_x = None
        self.scroll.add_widget(self.grid)
        self.add_widget(self.scroll)
        self.grid.bind(height=self.fit_height)
        self.bind(width=self.draw)
        App.get_running_app().bind(font_size=self.draw)
        self.draw()

    def fit_height(self, *_):
        self.scroll.height = self.grid.height + dp(16)
        self.height = self.scroll.height

    def sort(self, column):
        self.reverse = not self.reverse if self.sort_column == column else False
        self.sort_column = column
        def key(record):
            value = record[1][column]
            return (value is None, value.casefold() if isinstance(value, str) else value or 0)
        self.records.sort(key=key, reverse=self.reverse)
        self.draw()

    def draw(self, *_):
        self.grid.clear_widgets()
        app = App.get_running_app()
        scale = app.font_size / 16
        widths = [dp(w) * scale for w in self.widths]
        self.grid.width = max(self.width, sum(widths) + dp(2) * (len(widths) - 1))
        extra = (self.grid.width - sum(widths) - dp(2) * (len(widths) - 1)) / len(widths)
        line_height = dp(48) * max(1, scale)
        for index, (key, values) in enumerate([(None, self.headers), *self.records]):
            cells = BoxLayout(size_hint=(None, None), width=self.grid.width, height=line_height, spacing=dp(2))
            for col, value in enumerate(values):
                if index and col in self.formatters:
                    value = self.formatters[col](value)
                display = "" if value is None else str(value)
                if index == 0:
                    suffix = (" v" if self.reverse else " ^") if self.sort_column == col else ""
                    cell = action(display + suffix, lambda c=col: self.sort(c))
                elif self.on_select:
                    cell = action(display, lambda k=key: self.on_select(k))
                else:
                    cell = Text(text=display)
                cell.size_hint_x = None
                cell.width = widths[col] + extra
                if index:
                    estimated_lines = max(1, (len(display) + max(1, int(cell.width / (app.font_size * 0.6))) - 1)
                                          // max(1, int(cell.width / (app.font_size * 0.6))))
                    cells.height = max(cells.height, estimated_lines * app.font_size * 1.5 + dp(12))
                cells.add_widget(cell)
            for cell in cells.children:
                if isinstance(cell, Action):
                    cell.height = cells.height
            self.grid.add_widget(cells)
        if not self.records:
            self.grid.add_widget(Text(text="No results.", muted=True))
        self.fit_height()
