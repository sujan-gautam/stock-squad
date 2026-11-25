"""Add a few sample records to an empty database for the class demonstration."""
from pathlib import Path
import os

from stock_squad.controller import Controller


def main():
    folder = os.environ.get("STOCK_SQUAD_DATA_DIR", Path(__file__).resolve().parent / "data")
    controller = Controller(folder)
    model = controller.model
    try:
        if model.items(include_removed=True):
            print("The database already has items. No sample data was added.")
            return
        model.add_item("Rice", "R101", "4.00", "20", "5")
        model.add_item("Milk", "M102", "3.00", "12", "4")
        eggs = model.add_item("Eggs", "E103", "2.50", "6", "5")
        model.change_stock(eggs, "Remove", "4", "Used in the kitchen")
        model.add_item("Bread", "B104", "2.00", "1", "4")
        print("Added four sample items. Run python main.py to open the app.")
    finally:
        model.close()


if __name__ == "__main__":
    main()
