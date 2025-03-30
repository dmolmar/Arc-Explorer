import sys
import os
import subprocess
from pathlib import Path
from typing import Callable, TYPE_CHECKING

from PyQt6.QtWidgets import QLabel, QMenu, QApplication, QSizePolicy
from PyQt6.QtCore import Qt

# Use TYPE_CHECKING to avoid circular imports for type hints
if TYPE_CHECKING:
    # Assuming these will be defined in their respective modules later
    from gui.main_window import ImageGallery
    # from dialogs.export_jpg import ExportAsJPGDialog # Removed, imported locally

class ImageLabel(QLabel):
    """
    A custom QLabel specifically for displaying image thumbnails in the gallery.
    Handles mouse clicks and context menu actions for the image.
    """
    def __init__(self, image_path: str, on_click_callback: Callable[..., None], gallery: 'ImageGallery'):
        """
        Initializes the ImageLabel.

        Args:
            image_path: The full path to the image file this label represents.
            on_click_callback: The function to call when the label is left-clicked.
                               This is expected to be a method of the ImageGallery.
            gallery: A reference to the main ImageGallery instance.
        """
        super().__init__()
        self.image_path = image_path
        # The callback is expected to be a method bound to the gallery instance,
        # often gallery.handle_image_click, passing self.image_path
        self.on_click_callback = on_click_callback
        self.gallery = gallery
        self.setToolTip(image_path) # Show full path on hover
        # Allow the label to expand horizontally and vertically
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Ensure the pixmap scales nicely within the label
        self.setScaledContents(False) # Let the pixmap scaling handle aspect ratio
        self.setAlignment(Qt.AlignmentFlag.AlignCenter) # Center the image

    def mousePressEvent(self, event):
        """Handles left-click events to trigger the callback."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Call the provided callback, passing the image path
            # The callback itself (e.g., gallery.handle_image_click) will decide
            # if analysis is needed based on context.
            # We pass analyze=False here as the default click action.
            self.on_click_callback(self.image_path, analyze=False)
        # Pass other mouse events to the base class
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        """Creates and shows a context menu for image actions."""
        menu = QMenu(self)

        # --- Standard Actions ---
        open_in_viewer_action = menu.addAction("Open in default viewer")
        open_in_browser_action = menu.addAction("Show in file browser")
        copy_name_action = menu.addAction("Copy image filename")
        copy_image_action = menu.addAction("Copy image") # ADDED
        copy_tags_action = menu.addAction("Copy tags") # ADDED
        export_jpg_action = menu.addAction("Export as JPG...")

        menu.addSeparator()

        # --- Similarity Search ---
        search_similar_action = menu.addAction("Search Similar Images")

        # --- Execute Menu ---
        action = menu.exec(self.mapToGlobal(event.pos()))

        # --- Handle Selected Action ---
        if action == open_in_viewer_action:
            self.open_in_image_viewer()
        elif action == open_in_browser_action:
            self.open_in_file_browser()
        elif action == copy_name_action:
            self.copy_image_name()
        elif action == export_jpg_action:
            self.export_as_jpg()
        elif action == copy_image_action: # ADDED
            self.gallery._copy_image_to_clipboard(self.image_path) # ADDED
        elif action == copy_tags_action: # ADDED
            self.gallery._copy_tags_to_clipboard(self.image_path) # ADDED
        elif action == search_similar_action:
            self.search_similar_images()

    def open_in_image_viewer(self):
        """Opens the image file using the system's default application."""
        try:
            if sys.platform == "win32":
                os.startfile(self.image_path)
            elif sys.platform == "darwin": # macOS
                subprocess.run(["open", self.image_path], check=True)
            else: # Linux and other POSIX
                subprocess.run(["xdg-open", self.image_path], check=True)
        except Exception as e:
            print(f"Error opening image in viewer: {e}")
            # Optionally show a message box to the user in the gallery
            # self.gallery.show_status_message(f"Error opening image: {e}")

    def open_in_file_browser(self):
        """Opens the file browser and selects the image file."""
        try:
            file_path = Path(self.image_path).resolve()
            if not file_path.exists():
                 print(f"Cannot open in file browser, path not found: {file_path}")
                 return

            if sys.platform == "win32":
                # Use explorer with /select to highlight the file
                subprocess.run(["explorer", "/select,", str(file_path)], check=True)
            elif sys.platform == "darwin": # macOS
                # Use open with -R to reveal the file in Finder
                subprocess.run(["open", "-R", str(file_path)], check=True)
            else: # Linux - open the containing directory
                subprocess.run(["xdg-open", str(file_path.parent)], check=True)
        except Exception as e:
            print(f"Error opening file browser: {e}")
            # self.gallery.show_status_message(f"Error showing file: {e}")

    def copy_image_name(self):
        """Copies the filename (without path) to the clipboard."""
        try:
            clipboard = QApplication.clipboard()
            if clipboard:
                filename = Path(self.image_path).name
                clipboard.setText(filename)
                print(f"Copied to clipboard: {filename}")
                # self.gallery.show_status_message(f"Copied '{filename}' to clipboard.", 2000) # Show for 2 secs
            else:
                 print("Error: Could not access clipboard.")
        except Exception as e:
            print(f"Error copying filename: {e}")

    def export_as_jpg(self):
        """Opens the ExportAsJPGDialog."""
        # We need to import the dialog class here to avoid circular imports at module level
        # This is slightly less clean but necessary if dialogs depend on widgets or vice-versa indirectly.
        # A better approach might involve signal/slot connections or passing data differently.
        try:
            from ..dialogs.export_jpg import ExportAsJPGDialog
            # Pass self (the ImageLabel) or self.gallery as the parent?
            # Passing self.gallery might be better for modality.
            export_dialog = ExportAsJPGDialog(self.gallery, self.image_path)
            export_dialog.exec() # Show dialog modally
        except ImportError:
             print("Error: Could not import ExportAsJPGDialog.")
        except Exception as e:
             print(f"Error opening export dialog: {e}")


    def search_similar_images(self):
        """Triggers the similarity search in the main gallery."""
        print(f"Triggering similarity search for: {self.image_path}")
        # Call the method on the gallery instance, passing the image path
        if hasattr(self.gallery, 'search_similar_images'):
             self.gallery.search_similar_images(self.image_path)
        else:
             print("Error: Gallery instance does not have 'search_similar_images' method.")