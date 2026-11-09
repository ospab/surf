"""
Тесты системы системных разрешений на устройства (Permissions), WebUSB, WebXR и Media.
"""
import os
import sys
import tempfile

# Обеспечиваем пути импорта
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from main import setup_chromium_environment

setup_chromium_environment()

from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWidgets import QApplication
from database import Database
from widgets.browser_tab import BrowserTab
from widgets.permission_dialogs import (
    PermissionPromptBar,
    get_feature_info,
    normalize_origin,
)


def run_tests():
    print("=== 1. Testing Chromium Environment Flags (WebUSB, WebXR, WebRTC) ===")
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    assert "WebUSB" in flags, "WebUSB flag missing"
    assert "WebXR" in flags, "WebXR flag missing"
    assert "WebBluetooth" in flags, "WebBluetooth flag missing"
    assert "WebHID" in flags, "WebHID flag missing"
    assert "WebSerial" in flags, "WebSerial flag missing"
    assert "EnumerateDevices" in flags, "EnumerateDevices flag missing"
    print("  -> All Chromium flags for devices, WebUSB, WebXR, WebRTC are present!")

    print("\n=== 2. Testing Database Site Permissions CRUD ===")
    tmp_db = tempfile.mktemp(suffix=".db")
    db = Database(tmp_db)

    # Empty check
    assert db.get_site_permission("https://meet.jit.si", "media") is None

    # Set allow
    db.set_site_permission("https://meet.jit.si", "media", "allow")
    assert db.get_site_permission("https://meet.jit.si", "media") == "allow"

    # Set deny
    db.set_site_permission("https://example.com", "notifications", "deny")
    assert db.get_site_permission("https://example.com", "notifications") == "deny"

    all_perms = db.get_all_site_permissions()
    assert len(all_perms) == 2, f"Expected 2 permissions, got {len(all_perms)}"

    # Delete single
    db.delete_site_permission("https://example.com", "notifications")
    assert db.get_site_permission("https://example.com", "notifications") is None
    assert len(db.get_all_site_permissions()) == 1

    # Clear all
    db.clear_site_permissions()
    assert len(db.get_all_site_permissions()) == 0
    print("  -> Database permissions table and CRUD work correctly!")

    print("\n=== 3. Testing PermissionPromptBar UI & Callbacks ===")
    app = QApplication.instance() or QApplication(sys.argv)

    bar = PermissionPromptBar()
    assert not bar.isVisible()

    allowed = []
    bar.show_prompt("https://meet.jit.si", "media", on_allow=lambda rem: allowed.append(rem))
    assert not bar.isHidden()
    assert "meet.jit.si" in bar.text_label.text()
    bar.btn_allow.click()
    assert bar.isHidden()
    assert allowed == [True]
    print("  -> PermissionPromptBar renders correctly and responds to user interaction!")

    print("\n=== 4. Testing End-to-End getUserMedia Stream Granting & Prompting ===")
    tab = BrowserTab(db)

    def on_load(ok):
        tab.browser_page.runJavaScript(
            """
            navigator.mediaDevices.getUserMedia({ audio: true, video: true })
                .then(s => { window.__granted = true; })
                .catch(e => { window.__error = e.name; });
            """
        )
        QTimer.singleShot(700, click_allow)

    def click_allow():
        assert not tab.permission_bar.isHidden(), "Permission bar was expected to be visible"
        tab.permission_bar.btn_allow.click()
        assert db.get_site_permission("https://meet.jit.si", "media") == "allow"
        QTimer.singleShot(600, verify_result)

    def verify_result():
        def cb(res):
            assert res.get("granted") is True, f"Failed granting stream: {res}"
            print("  -> End-to-end device permission prompt granted media stream to page!")
            app.quit()

        tab.browser_page.runJavaScript(
            "({ granted: window.__granted || false, error: window.__error || null })",
            cb,
        )

    tab.browser_page.loadFinished.connect(on_load)
    tab.browser_page.setHtml("<html><body>Test</body></html>", QUrl("https://meet.jit.si/test"))
    app.exec()

    print("\n=== ALL PERMISSION TESTS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    run_tests()
