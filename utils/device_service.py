"""
Модуль обнаружения и перечисления системных устройств мультимедиа (микрофоны, камеры, аудиовыходы).
Использует аппаратную подсистему QtMultimedia (QMediaDevices).
"""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtMultimedia import QMediaDevices


class DeviceService(QObject):
    """Служба перечисления и мониторинга аппаратных аудио- и видеоустройств."""

    audio_inputs_changed = pyqtSignal()
    video_inputs_changed = pyqtSignal()

    _instance = None

    @classmethod
    def instance(cls) -> "DeviceService":
        if cls._instance is None:
            cls._instance = DeviceService()
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self._media_devices = QMediaDevices(self)
        self._media_devices.audioInputsChanged.connect(self.audio_inputs_changed.emit)
        self._media_devices.videoInputsChanged.connect(self.video_inputs_changed.emit)

    def get_audio_inputs(self) -> list[dict]:
        """Возвращает список доступных микрофонов / источников звука."""
        inputs = []
        for dev in QMediaDevices.audioInputs():
            desc = dev.description().strip()
            if not desc:
                continue
            dev_id = dev.id().data().decode("utf-8", errors="ignore")
            inputs.append(
                {
                    "id": dev_id,
                    "name": desc,
                    "is_default": dev.isDefault(),
                }
            )
        return inputs

    def get_video_inputs(self) -> list[dict]:
        """Возвращает список доступных веб-камер / видеоустройств."""
        inputs = []
        for dev in QMediaDevices.videoInputs():
            desc = dev.description().strip()
            if not desc:
                continue
            dev_id = dev.id().data().decode("utf-8", errors="ignore")
            inputs.append(
                {
                    "id": dev_id,
                    "name": desc,
                    "is_default": dev.isDefault(),
                }
            )
        return inputs

    def get_default_audio_name(self) -> str:
        """Возвращает название микрофона по умолчанию."""
        def_dev = QMediaDevices.defaultAudioInput()
        if def_dev and not def_dev.isNull():
            return def_dev.description()
        inputs = self.get_audio_inputs()
        return inputs[0]["name"] if inputs else ""

    def get_default_video_name(self) -> str:
        """Возвращает название камеры по умолчанию."""
        def_dev = QMediaDevices.defaultVideoInput()
        if def_dev and not def_dev.isNull():
            return def_dev.description()
        inputs = self.get_video_inputs()
        return inputs[0]["name"] if inputs else ""
