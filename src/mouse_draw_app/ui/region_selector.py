from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from mouse_draw_app.models import DrawRegion


class RegionSelector(QWidget):
    region_selected = Signal(DrawRegion)
    cancelled = Signal()

    def __init__(self) -> None:
        super().__init__()
        geometry = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(geometry)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowState(Qt.WindowFullScreen)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)

        self._origin = QPoint()
        self._selection = QRect()
        self._dragging = False
        self._background = QPixmap()

    def show_selector(self) -> None:
        screen = QGuiApplication.primaryScreen()
        geometry = screen.virtualGeometry()
        self.setGeometry(geometry)
        self._background = screen.grabWindow(
            0,
            geometry.x(),
            geometry.y(),
            geometry.width(),
            geometry.height(),
        )
        self._selection = QRect()
        self._dragging = False
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton:
            return
        self._origin = event.globalPosition().toPoint()
        self._selection = QRect(self._origin, self._origin)
        self._dragging = True
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._dragging:
            return
        current = event.globalPosition().toPoint()
        self._selection = QRect(self._origin, current).normalized()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton or not self._dragging:
            return
        self._dragging = False
        self._selection = QRect(self._origin, event.globalPosition().toPoint()).normalized()
        if self._selection.width() < 20 or self._selection.height() < 20:
            self.hide()
            self.cancelled.emit()
            return
        self.hide()
        self.region_selected.emit(
            DrawRegion(
                left=self._selection.left(),
                top=self._selection.top(),
                width=self._selection.width(),
                height=self._selection.height(),
            )
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self.hide()
            self.cancelled.emit()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not self._background.isNull():
            painter.drawPixmap(self.rect(), self._background)

        painter.setPen(QPen(QColor("#3da9fc"), 2))

        if not self._selection.isNull():
            local_selection = QRect(
                self.mapFromGlobal(self._selection.topLeft()),
                self.mapFromGlobal(self._selection.bottomRight()),
            ).normalized()
            painter.drawRect(local_selection)
