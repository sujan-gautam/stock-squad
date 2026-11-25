from pathlib import Path
import shutil
import uuid

from .models import Inventory, Settings, whole_number


class Controller:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.model = Inventory(self.data_dir / "inventory.db")
        self.settings = Settings(self.data_dir / "settings.ini")

    def image_file(self, relative_path):
        return str(self.data_dir / relative_path) if relative_path else ""

    def copy_image(self, source):
        if not source:
            return ""
        source = Path(source)
        if not source.is_file() or source.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            raise ValueError("Choose a PNG or JPEG picture.")
        if source.stat().st_size > 10 * 1024 * 1024:
            raise ValueError("Choose a picture smaller than 10 MB.")
        from kivy.core.image import Image as CoreImage
        try:
            if CoreImage(str(source)).texture is None:
                raise ValueError
        except Exception:
            raise ValueError("That file could not be opened as a picture.") from None
        folder = self.data_dir / "images"
        folder.mkdir(exist_ok=True)
        name = f"{uuid.uuid4().hex}{source.suffix.lower()}"
        shutil.copyfile(source, folder / name)
        return f"images/{name}"

    def save_item(self, item_id, name, sku, price, quantity, limit, image_source):
        self.model.fields(name, sku, price, limit)
        if item_id is None:
            whole_number(quantity, "Starting quantity")
        old = self.model.get(item_id) if item_id is not None else None
        old_image = old["image_path"] if old else ""
        if image_source == self.image_file(old_image):
            image = old_image
        else:
            image = self.copy_image(image_source)
        try:
            if old:
                self.model.edit_item(item_id, name, sku, price, limit, image)
                return item_id
            return self.model.add_item(name, sku, price, quantity, limit, image)
        except Exception:
            if image and image != old_image:
                (self.data_dir / image).unlink(missing_ok=True)
            raise
