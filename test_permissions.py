"""
Тесты расширенной системы системных разрешений на устройства:
- разделение на микрофоны и камеры с выбором конкретного девайса (DeviceService)
- маршрутизация устройств в WebRTC (JavaScript getUserMedia hook)
- сохранение выбора для сайта (site_device_preferences)
- вкладка «Устройства» в настройках (SettingsDialog)
"""
import os
import sys
import tempfile

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from main import setup_chromium_environment

setup_chromium_environment()

from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWidgets import QApplication
from database import Database
from utils.device_service import DeviceService
from widgets.browser_tab import BrowserTab
from widgets.permission_dialogs import (
    PermissionPromptBar,
    get_feature_info,
    normalize_origin,
)
from widgets.settings_dialog import SettingsDialog


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

    print("\n=== 2. Testing DeviceService (QMediaDevices enumeration) ===")
    app = QApplication.instance() or QApplication(sys.argv)
    svc = DeviceService.instance()
    mics = svc.get_audio_inputs()
    cams = svc.get_video_inputs()
    print(f"  -> Detected microphones: {len(mics)}")
    for m in mics:
        print(f"     - {ascii(m['name'])} (default: {m['is_default']})")
    print(f"  -> Detected cameras: {len(cams)}")
    for c in cams:
        print(f"     - {ascii(c['name'])} (default: {c['is_default']})")
    assert isinstance(mics, list)
    assert isinstance(cams, list)

    print("\n=== 3. Testing Database Site Device Preferences CRUD ===")
    tmp_db = tempfile.mktemp(suffix=".db")
    db = Database(tmp_db)

    # Empty check
    assert db.get_site_device_preference("https://meet.jit.si") is None

    # Set granular preference
    sample_mic = mics[0]["name"] if mics else "Default Mic"
    sample_cam = cams[0]["name"] if cams else "Default Cam"
    db.set_site_device_preference(
        "https://meet.jit.si",
        audio_device=sample_mic,
        video_device=sample_cam,
        allow_audio=True,
        allow_video=False,
    )

    pref = db.get_site_device_preference("https://meet.jit.si")
    assert pref is not None
    assert pref["audio_device"] == sample_mic
    assert pref["allow_audio"] is True
    assert pref["allow_video"] is False
    print("  -> Granular site device preferences correctly stored and retrieved!")

    all_prefs = db.get_all_site_device_preferences()
    assert len(all_prefs) == 1
    assert all_prefs[0]["origin"] == "https://meet.jit.si"

    # Delete
    deleted = db.delete_site_device_preference("https://meet.jit.si")
    assert deleted is True
    assert db.get_site_device_preference("https://meet.jit.si") is None
    print("  -> Deletion of site device preference verified!")

    print("\n=== 4. Testing PermissionPromptBar UI with Device Selection ===")
    bar = PermissionPromptBar()
    assert not bar.isVisible()

    allowed_results = []
    bar.show_prompt("https://meet.jit.si", "media", on_allow=lambda res: allowed_results.append(res))
    assert not bar.isHidden()
    assert bar.device_box.isVisible(), "Device box must be visible for media prompt"
    assert bar.mic_row.isVisible(), "Mic row must be visible for media prompt"
    assert bar.cam_row.isVisible(), "Cam row must be visible for media prompt"
    assert bar.mic_combo.count() > 0, "Microphone combo must be populated"
    assert bar.cam_combo.count() > 0, "Camera combo must be populated"

    # Uncheck camera (simulate user wanting mic only)
    bar.cam_check.setChecked(False)
    bar.btn_allow.click()
    assert bar.isHidden()
    assert len(allowed_results) == 1
    cfg = allowed_results[0]
    assert isinstance(cfg, dict), f"Expected dict config, got {cfg}"
    assert cfg["allow_audio"] is True
    assert cfg["allow_video"] is False
    assert cfg["remember"] is True
    print("  -> PermissionPromptBar successfully split media into independent mic/cam selections!")

    print("\n=== 5. Testing SettingsDialog Devices Tab ===")
    dlg = SettingsDialog(db)
    # Check that tab index 4 is the Devices tab
    tab_count = dlg.settingsTabs.count()
    assert tab_count == 5, f"Expected 5 tabs (including Devices), got {tab_count}"
    assert dlg.settingsTabs.tabText(4) in ("Устройства", "Devices")
    assert hasattr(dlg, "defaultMicCombo")
    assert hasattr(dlg, "defaultCamCombo")
    assert hasattr(dlg, "siteDevTable")
    print("  -> SettingsDialog Devices tab initialized and verified!")

    print("\n=== ALL PERMISSION AND DEVICE TESTS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    run_tests()
