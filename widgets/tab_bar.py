"""Панель вкладок surf и фильтр масштабирования колесом мыши."""

import os

from PyQt6.QtCore import QEvent, QObject, QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QMouseEvent
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QTabBar, QToolButton, QWidget

try:
    from surf.i18n import tr
except ModuleNotFoundError:
    from i18n import tr


class ZoomWheelFilter(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window

    def eventFilter(self, obj, event):
        # Фильтр стоит на всём приложении, поэтому реагируем только на события своего окна
        if not isinstance(obj, QWidget) or obj.window() is not self.main_window:
            return False
        if event.type() == QEvent.Type.Wheel and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            delta = event.angleDelta().y()
            if delta > 0:
                self.main_window._zoom_in()
            elif delta < 0:
                self.main_window._zoom_out()
            return True
        return False


class ClosableTabBar(QTabBar):
    """Фирменная панель вкладок surf: фавиконы, индикатор аудио/mute, кнопка закрытия, отрыв вкладок."""

    tabAudioMuteRequested = pyqtSignal(int)
    tabDetachRequested = pyqtSignal(int, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(False)
        self.setIconSize(QSize(16, 16))
        self._is_dark = True
        icon_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "icons")
        self._close_icon_dark = QIcon(os.path.join(icon_dir, "close_dark.svg"))
        self._close_icon_light = QIcon(os.path.join(icon_dir, "close_light.svg"))
        self._vol_icon = QIcon(os.path.join(icon_dir, "volume-2.svg"))
        self._vol_x_icon = QIcon(os.path.join(icon_dir, "volume-x.svg"))
        self._audio_states: dict[int, tuple[bool, bool]] = {}

        self._drag_start_pos: QPoint | None = None
        self._drag_tab_idx: int = -1
        self._is_detached_mode: bool = False
        self._cursor_overridden: bool = False

        self.tabMoved.connect(self._sync_audio_states_on_tab_moved)
        self.update_movable_state()

    def update_movable_state(self) -> None:
        """Перемещать вкладки можно только когда их 2 или более."""
        self.setMovable(self.count() > 1)

    def _set_drag_cursor(self, enabled: bool) -> None:
        if enabled and not self._cursor_overridden:
            QApplication.setOverrideCursor(Qt.CursorShape.DragMoveCursor)
            self._cursor_overridden = True
        elif not enabled and self._cursor_overridden:
            QApplication.restoreOverrideCursor()
            self._cursor_overridden = False

    def set_theme_mode(self, is_dark: bool, vol_icon: QIcon | None = None, vol_x_icon: QIcon | None = None) -> None:
        self._is_dark = is_dark
        if vol_icon and not vol_icon.isNull():
            self._vol_icon = vol_icon
        if vol_x_icon and not vol_x_icon.isNull():
            self._vol_x_icon = vol_x_icon

        close_icon = self._close_icon_dark if is_dark else self._close_icon_light
        for i in range(self.count()):
            container = self.tabButton(i, QTabBar.ButtonPosition.RightSide)
            if container:
                btn_close = container.findChild(QToolButton, "tabCloseBtn")
                if btn_close:
                    btn_close.setIcon(close_icon)
                btn_audio = container.findChild(QToolButton, "tabAudioBtn")
                if btn_audio and btn_audio.isVisible():
                    _, muted = self._audio_states.get(i, (False, False))
                    btn_audio.setIcon(self._vol_x_icon if muted else self._vol_icon)

    def retranslate_close_buttons(self) -> None:
        tip_close = tr("act_close_tab")
        for i in range(self.count()):
            container = self.tabButton(i, QTabBar.ButtonPosition.RightSide)
            if container:
                btn_close = container.findChild(QToolButton, "tabCloseBtn")
                if btn_close:
                    btn_close.setToolTip(tip_close)
                btn_audio = container.findChild(QToolButton, "tabAudioBtn")
                if btn_audio:
                    _, muted = self._audio_states.get(i, (False, False))
                    btn_audio.setToolTip(tr("tip_unmute_tab") if muted else tr("tip_mute_tab"))

    def tabInserted(self, index: int) -> None:
        super().tabInserted(index)
        self.update_movable_state()

        new_audio = {}
        for k, v in self._audio_states.items():
            if k >= index:
                new_audio[k + 1] = v
            else:
                new_audio[k] = v
        self._audio_states = new_audio

        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(2)

        btn_audio = QToolButton(container)
        btn_audio.setObjectName("tabAudioBtn")
        btn_audio.setFixedSize(18, 18)
        btn_audio.setIconSize(QSize(12, 12))
        btn_audio.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_audio.setVisible(False)
        btn_audio.clicked.connect(lambda _, c=container: self._on_audio_clicked(c))
        layout.addWidget(btn_audio)

        btn_close = QToolButton(container)
        btn_close.setObjectName("tabCloseBtn")
        btn_close.setIcon(self._close_icon_dark if self._is_dark else self._close_icon_light)
        btn_close.setIconSize(QSize(12, 12))
        btn_close.setFixedSize(18, 18)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setToolTip(tr("act_close_tab"))
        btn_close.clicked.connect(lambda _, c=container: self._on_close_clicked(c))
        layout.addWidget(btn_close)

        self.setTabButton(index, QTabBar.ButtonPosition.RightSide, container)

    def tabRemoved(self, index: int) -> None:
        super().tabRemoved(index)
        self.update_movable_state()

        new_audio = {}
        for k, v in self._audio_states.items():
            if k < index:
                new_audio[k] = v
            elif k > index:
                new_audio[k - 1] = v
        self._audio_states = new_audio

    def _sync_audio_states_on_tab_moved(self, from_idx: int, to_idx: int) -> None:
        if from_idx in self._audio_states:
            st = self._audio_states.pop(from_idx)
            new_audio = {}
            for k, v in self._audio_states.items():
                if from_idx < to_idx:
                    if from_idx < k <= to_idx:
                        new_audio[k - 1] = v
                    else:
                        new_audio[k] = v
                else:
                    if to_idx <= k < from_idx:
                        new_audio[k + 1] = v
                    else:
                        new_audio[k] = v
            new_audio[to_idx] = st
            self._audio_states = new_audio

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.update_movable_state()
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
            self._drag_tab_idx = self.tabAt(event.pos())
            self._is_detached_mode = False

            if self.count() <= 1:
                # Если вкладка всего одна, запрещаем внутреннее перемещение в QTabBar
                idx = self.tabAt(event.pos())
                if idx >= 0:
                    self.setCurrentIndex(idx)
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            (event.buttons() & Qt.MouseButton.LeftButton)
            and self._drag_start_pos is not None
            and self._drag_tab_idx >= 0
        ):
            dist = (event.pos() - self._drag_start_pos).manhattanLength()
            if dist > QApplication.startDragDistance():
                if self.count() > 1:
                    cur_global = event.globalPosition().toPoint()
                    local_pt = self.mapFromGlobal(cur_global)
                    win = self.window()
                    win_geo = win.frameGeometry() if win else None

                    # Проверяем, вытянут ли курсор за пределы окна или полосы вкладок
                    is_outside = False
                    if win_geo and not win_geo.contains(cur_global):
                        is_outside = True
                    elif (
                        local_pt.y() < -20
                        or local_pt.y() > self.height() + 35
                        or local_pt.x() < -30
                        or local_pt.x() > self.width() + 40
                    ):
                        is_outside = True

                    if is_outside:
                        if not self._is_detached_mode:
                            self._is_detached_mode = True
                            self._set_drag_cursor(True)
                    else:
                        if self._is_detached_mode:
                            self._is_detached_mode = False
                            self._set_drag_cursor(False)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._is_detached_mode:
            self._set_drag_cursor(False)
            self._is_detached_mode = False

            if self.count() > 1:
                cur_global = event.globalPosition().toPoint()
                detach_idx = self.currentIndex()
                if detach_idx < 0:
                    detach_idx = self._drag_tab_idx
                if 0 <= detach_idx < self.count():
                    self.tabDetachRequested.emit(detach_idx, cur_global)

                self._drag_start_pos = None
                self._drag_tab_idx = -1
                event.accept()
                return

        self._set_drag_cursor(False)
        self._is_detached_mode = False
        self._drag_start_pos = None
        self._drag_tab_idx = -1
        super().mouseReleaseEvent(event)

    def set_tab_audio(self, index: int, audible: bool, muted: bool) -> None:
        self._audio_states[index] = (audible, muted)
        container = self.tabButton(index, QTabBar.ButtonPosition.RightSide)
        if not container:
            return
        btn_audio = container.findChild(QToolButton, "tabAudioBtn")
        if not btn_audio:
            return
        if audible or muted:
            btn_audio.setVisible(True)
            btn_audio.setIcon(self._vol_x_icon if muted else self._vol_icon)
            btn_audio.setToolTip(tr("tip_unmute_tab") if muted else tr("tip_mute_tab"))
        else:
            btn_audio.setVisible(False)

    def _on_close_clicked(self, container: QWidget) -> None:
        for i in range(self.count()):
            if self.tabButton(i, QTabBar.ButtonPosition.RightSide) == container:
                self.tabCloseRequested.emit(i)
                break

    def _on_audio_clicked(self, container: QWidget) -> None:
        for i in range(self.count()):
            if self.tabButton(i, QTabBar.ButtonPosition.RightSide) == container:
                self.tabAudioMuteRequested.emit(i)
                break
