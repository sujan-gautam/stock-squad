# Testing

Tested on November 25, 2026, on Windows 11, Python 3.13.1, and Kivy 2.3.1.

The app was also installed in a new Python virtual environment using only `requirements.txt`. `pip check` reported no broken requirements.

## Automated checks

The 20 database and settings tests pass. They cover:

- Item creation, saved records, and starting-stock history.
- Case-insensitive duplicate SKUs, invalid fields, and exact price calculations.
- Stock additions, removals, reasons, and insufficient-stock errors.
- Rollback when writing a transaction fails.
- Editing item details without changing stock.
- Removed listings, retained history, and reserved SKUs.
- Summary totals and the low-stock boundary.
- Search, picture-name filtering, numeric ranges, and date filters.
- Inclusive report dates, item filtering, and highest/lowest movement.
- CSV quotes, Unicode, and text that could be read as a spreadsheet formula.
- Saved preferences and invalid settings.

The UI smoke check passes in both the existing Python installation and the new virtual environment. It exercises all six pages, invalid and duplicate item entry, picture copying, item edits, stock changes, sorting prices numerically, filters, the CSV save dialog, removal confirmation, Dark/Large settings, a smaller window, and saved data read through a new connection.

## Quick team demonstration

1. Start with an empty inventory. Check the zero totals and empty lists.
2. Add Rice with SKU R101, price 4.00, quantity 10, and stock limit 5. Add a picture if wanted.
3. Try another item using r101. The form should reject it and keep the entered values.
4. Remove 6 units with reason Used. The quantity should become 4, and Rice should appear in the low-stock list.
5. Try removing 5 more. The quantity and history should stay unchanged.
6. Add 2 units with reason Delivery. Quantity becomes 6, and the alert disappears. Check recent restocks and history.
7. Search R101, use Quantity From/To, and sort the price column. Open Rice and edit its name and low-stock limit.
8. Generate each report. Sort the results and export a CSV. Change the filters and check that old results are cleared. Try an invalid date range.
9. Save Dark theme, Large text, and a default limit of 9. Reopen the app and check the settings and item records. The existing item's limit should stay unchanged; a new item form should start at 9.
10. Remove a listing, cancel once, then confirm. It should leave active inventory while its history is still available in a movement report.

## Scope

This is a local desktop app. It was tested on Windows; macOS, Linux, and packaged mobile apps have not been verified. Records are loaded into the tables in memory, so very large inventories would need pagination. It has no login, network sync, or automatic backup. These were not part of the agreed project features.
