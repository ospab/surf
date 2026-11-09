"""
Headless unit and integration tests for Speed Dial (Top Sites) functionality.
"""
import os
import sys

# Ensure both 'surf' package and root directory are in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
for p in (BASE_DIR, PARENT_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import tempfile
import PyQt6.QtWebEngineWidgets
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QPointF
from PyQt6.QtGui import QMouseEvent

os.environ["QT_QPA_PLATFORM"] = "offscreen"

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

try:
    from surf.database import Database
    from surf.i18n import tr, set_language
    from surf.widgets.browser_tab import (
        SpeedDialWidget,
        SpeedDialCard,
        SpeedDialAddCard,
        SpeedDialEditDialog,
        generate_tile_badge,
    )
except ModuleNotFoundError:
    from database import Database
    from i18n import tr, set_language
    from widgets.browser_tab import (
        SpeedDialWidget,
        SpeedDialCard,
        SpeedDialAddCard,
        SpeedDialEditDialog,
        generate_tile_badge,
    )

def run_tests():
    print("=== 1. Testing Database Initialization and Clean Shortcuts ===")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db_path = f.name

    try:
        db = Database(temp_db_path)
        tiles = db.get_speed_dial_tiles()
        assert len(tiles) == 0, f"Expected 0 default tiles (clean initial shortcuts), got {len(tiles)}"
        print("  -> Clean initial shortcuts verified: tiles count =", len(tiles))

        print("\n=== 2. Testing Database CRUD ===")
        # Add tile
        new_id = db.add_speed_dial_tile("OpenAI", "https://openai.com")
        assert new_id > 0, "add_speed_dial_tile failed"
        tiles = db.get_speed_dial_tiles()
        assert len(tiles) == 1
        added = [t for t in tiles if t["id"] == new_id][0]
        assert added["title"] == "OpenAI"
        assert added["url"] == "https://openai.com"
        print("  -> Add tile OK, new_id =", new_id)

        # Update tile
        ok = db.update_speed_dial_tile(new_id, "OpenAI ChatGPT", "https://chatgpt.com")
        assert ok is True
        tiles = db.get_speed_dial_tiles()
        updated = [t for t in tiles if t["id"] == new_id][0]
        assert updated["title"] == "OpenAI ChatGPT"
        assert updated["url"] == "https://chatgpt.com"
        print("  -> Update tile OK")

        # Delete tile
        ok = db.delete_speed_dial_tile(new_id)
        assert ok is True
        tiles = db.get_speed_dial_tiles()
        assert len(tiles) == 0
        print("  -> Delete tile OK")

        print("\n=== 3. Testing SpeedDialWidget UI & Signals ===")
        widget = SpeedDialWidget(db)
        assert widget.tiles_layout.count() == 1  # 0 tiles + 1 add card
        print("  -> SpeedDialWidget instantiated with 1 item (Add Card) in grid")

        # Test adding a tile and clicking on card
        new_id2 = db.add_speed_dial_tile("GitHub", "https://github.com")
        widget.refresh_tiles()
        assert widget.tiles_layout.count() == 2  # 1 tile + 1 add card

        opened_urls = []
        widget.open_url.connect(lambda url: opened_urls.append(url))

        first_card = widget.tiles_layout.itemAt(0).widget()
        assert isinstance(first_card, SpeedDialCard)
        # Simulate click
        press_event = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(20, 20), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        release_event = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(20, 20), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        first_card.mousePressEvent(press_event)
        first_card.mouseReleaseEvent(release_event)
        assert len(opened_urls) == 1
        assert "github.com" in opened_urls[0]
        print(f"  -> Tile clicked and emitted open_url: {opened_urls[0]}")

        print("\n=== 4. Testing Fallback to Top Visited History ===")
        # Seed some history
        db.add_history_entry("https://python.org", "Python Programming")
        db.add_history_entry("https://python.org", "Python Programming")
        db.add_history_entry("https://rust-lang.org", "Rust Programming")

        # Delete all speed dial tiles to test fallback
        for t in db.get_speed_dial_tiles():
            db.delete_speed_dial_tile(t["id"])

        assert len(db.get_speed_dial_tiles()) == 0
        print("  -> Speed dial table is now empty")

        top_history = db.get_top_visited_sites(6)
        assert len(top_history) >= 2
        print("  -> History top visited sites:", [(h["title"], h["url"]) for h in top_history])

        widget.refresh_tiles()
        # Should now have top history items + 1 add card
        assert widget.tiles_layout.count() == len(top_history) + 1
        first_fallback_card = widget.tiles_layout.itemAt(0).widget()
        assert isinstance(first_fallback_card, SpeedDialCard)
        assert first_fallback_card.tile_data.get("is_fallback") is True
        print("  -> Fallback properly triggered and displayed in grid!")

        print("\n=== 5. Testing Pinning Fallback Tile ===")
        first_fallback_card.pin_requested.emit(first_fallback_card.tile_data)
        pinned = db.get_speed_dial_tiles()
        assert len(pinned) == 1
        assert pinned[0]["url"] == "https://python.org"
        print("  -> Successfully pinned fallback tile to speed dial:", pinned[0]["title"])

        print("\n=== 6. Testing Badge Generator for various sites ===")
        badge_google = generate_tile_badge("Google", "https://www.google.com")
        assert not badge_google.isNull()
        badge_github = generate_tile_badge("GitHub", "https://github.com")
        assert not badge_github.isNull()
        badge_yt = generate_tile_badge("YouTube", "https://youtube.com")
        assert not badge_yt.isNull()
        badge_habr = generate_tile_badge("Habr", "https://habr.com")
        assert not badge_habr.isNull()
        badge_wiki = generate_tile_badge("Wikipedia", "https://wikipedia.org")
        assert not badge_wiki.isNull()
        badge_ya = generate_tile_badge("Яндекс", "https://ya.ru")
        assert not badge_ya.isNull()
        badge_generic = generate_tile_badge("CustomSite", "https://customsite.io")
        assert not badge_generic.isNull()
        badge_add = generate_tile_badge("", "", is_add_btn=True)
        assert not badge_add.isNull()
        print("  -> All badge pixmaps generated successfully with 2x resolution")

        print("\n=== 7. Testing Retranslation ===")
        set_language("en")
        widget.retranslate_ui()
        set_language("ru")
        widget.retranslate_ui()
        print("  -> Retranslation works without error")

        print("\n=== ALL TESTS PASSED! ===")
    finally:
        if os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except Exception:
                pass

if __name__ == "__main__":
    run_tests()
