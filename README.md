# Stock Squad

An inventory app for CSC 317. It keeps item details and stock history in a local SQLite database.

## Setup on Windows

Tested on Windows 11 with **Python 3.13.1 (64-bit)** and **Kivy 2.3.1**. Use Python 3.13 for these instructions. Python 3.14 is not the tested version.

Download or clone this repository, extract it if needed, and open PowerShell in the folder containing `main.py` and `requirements.txt`.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

There is no separate build step, database server, account, or API key. Internet is needed to install Kivy the first time. The app works offline after setup. These commands use the virtual environment directly, so PowerShell script activation is not needed.

To check the versions:

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -c "import kivy; print(kivy.__version__)"
```

If `py -3.13` cannot find Python, install 64-bit Python 3.13 from [python.org](https://www.python.org/downloads/). If the window cannot open, check that you are using a local desktop session and that the graphics driver supports OpenGL. Keep the terminal open to see any error message.

## Try the app

The first run starts with an empty inventory. Add your own items, or close the app and add the optional sample records:

```powershell
.\.venv\Scripts\python.exe seed_demo.py
.\.venv\Scripts\python.exe main.py
```

The sample script only adds records when the database has no items, including removed listings. It never replaces existing records.

1. Open **Add Item**. Enter a name, unique SKU, starting quantity, and low-stock limit. Price and picture are optional. Pictures must be PNG or JPEG, smaller than 10 MB.
2. Open **Inventory**. Search all stored item fields or choose a field under Filters. Use Contains for text and From/To for numeric or restock-date ranges. Dates use `YYYY-MM-DD`. Select Apply after changing the filters. Click a column heading to sort, and click an item row to open its details.
3. On **Item Details**, choose Add or Remove, enter a positive whole-number quantity and a reason, then Confirm Change. The app shows the expected new total and rejects removals above the available stock. Edit Item changes the listing; stock changes go through the transaction controls.
4. **Dashboard** shows recent restocks, low-stock alerts, item count, total units, and stock value. An alert appears below the item's limit, not when stock equals the limit. Stock value is quantity times unit price and leaves out items without a price. Click an item in either list to open it.
5. On **Reports**, choose Low Stock, Stock Movement, Highest Movement, or Lowest Movement. Movement reports use an inclusive date range. An optional item filter includes removed items so their history remains available. Generate loads the results. Click headings to sort, then Save CSV to choose a folder and filename. Changing filters clears the old results until Generate is selected again.
6. **Settings** saves Light/Dark theme, Small/Medium/Large text, and the default low-stock limit. The default is used for new items and does not change existing item limits.

Pages scroll vertically. Wide tables scroll horizontally, especially with Large text or a smaller window. The minimum intended window size is 900 by 600 pixels.

Removing a listing asks for confirmation. It hides the item from active inventory but keeps its transactions. Its SKU remains reserved so the old history is not mixed with another item. Movement rankings count units removed, not sales. The lowest-movement report includes active items with no removals in the date range.

## Saved files

The app creates this folder automatically next to `main.py`:

```text
data/
  inventory.db       Items and stock transactions
  settings.ini       Saved preferences
  images/            Copies of selected item pictures
```

Close the app before copying the `data` folder for a backup. Keep the whole folder together when moving saved records to another computer. The repository and submission ZIP start without personal inventory data. Both database tables are created on first launch.

For a separate data folder, set `STOCK_SQUAD_DATA_DIR` before starting the app. The default folder must be writable.

## Code layout

| File | Purpose |
| --- | --- |
| `main.py` | Starts the app |
| `stock_squad/app.py` | App setup, navigation, and theme |
| `stock_squad/models.py` | SQLite records, validation, reports, CSV, and settings |
| `stock_squad/controller.py` | Coordinates item saves and copied pictures |
| `stock_squad/views.py` | The six Kivy pages and their event handlers |
| `stock_squad/widgets.py` | Shared form controls, dialogs, and tables |
| `seed_demo.py` | Optional sample inventory |
| `tests/` | Database, settings, and UI checks |

The project follows MVC. Models own the data and calculations. Views display pages. The controller handles item-save requests; page event handlers call model methods for stock changes and reports. No extra UI framework is used.

## Tests

Run the database and settings checks:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run the UI check in a desktop session:

```powershell
.\.venv\Scripts\python.exe tests\smoke_ui.py
```

The UI check opens and closes a real Kivy window, uses a temporary database, and does not touch the normal inventory. See `TESTING.md` for test results and manual demonstration steps.

## Team

- Alish Acharya: Frontend Developer
- Faiza Faiz: Project Manager, Team Lead, and QA Tester
- Sujan Gautam: Backend and Database Developer
- TaKorey Finley: QA Tester
