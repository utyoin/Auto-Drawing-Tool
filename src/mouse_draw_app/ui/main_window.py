from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QFrame,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from mouse_draw_app.models import DrawConfig, DrawRegion, OutlineDocument, PathStroke
from mouse_draw_app.services.image_outline_service import ImageOutlineError, ImageOutlineService
from mouse_draw_app.services.mouse_draw_service import MouseDrawService
from mouse_draw_app.services.path_transform_service import PathTransformService
from mouse_draw_app.services.text_outline_service import TextOutlineError, TextOutlineService
from mouse_draw_app.ui.region_selector import RegionSelector


class PreviewView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self.setRenderHints(self.renderHints() | QPainter.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor("#f8fafc")))
        self.setFrameShape(QFrame.NoFrame)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        scene = self.scene()
        if scene is not None and not scene.sceneRect().isNull():
            self.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)


class DrawingWorker(QObject):
    started = Signal()
    finished = Signal()
    failed = Signal(str)

    def __init__(
        self,
        service: MouseDrawService,
        paths: list[PathStroke],
        config: DrawConfig,
        stop_event: threading.Event,
    ) -> None:
        super().__init__()
        self._service = service
        self._paths = paths
        self._config = config
        self._stop_event = stop_event

    def run(self) -> None:
        self.started.emit()
        try:
            self._service.draw_paths(self._paths, self._config, self._stop_event)
        except Exception as exc:  # pragma: no cover - UI error path
            self.failed.emit(str(exc))
            return
        self.finished.emit()


class MainWindow(QMainWindow):
    emergency_stop_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Auto-drawpic")
        self.resize(1280, 760)

        self.image_outline_service = ImageOutlineService()
        self.text_outline_service = TextOutlineService()
        self.path_transform_service = PathTransformService()
        self.mouse_draw_service = MouseDrawService()
        self.region_selector = RegionSelector()
        self.region_selector.region_selected.connect(self._handle_region_selected)
        self.region_selector.cancelled.connect(self._handle_region_selection_cancelled)

        self.current_document: OutlineDocument | None = None
        self.selected_region: DrawRegion | None = None
        self.pending_paths: list[PathStroke] = []
        self.stop_event = threading.Event()
        self.draw_thread: QThread | None = None
        self.draw_worker: DrawingWorker | None = None
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._tick_countdown)
        self.remaining_countdown = 0

        self._build_ui()
        self.emergency_stop_requested.connect(self.stop_drawing)
        self.mouse_draw_service.start_emergency_stop_listener(self.emergency_stop_requested.emit)
        self._set_status("待命")

    def closeEvent(self, event) -> None:
        self.stop_drawing()
        self.mouse_draw_service.stop_emergency_stop_listener()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(16)

        left_panel = QWidget()
        left_panel.setFixedWidth(360)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(12)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #0f172a;")
        left_layout.addWidget(self.status_label)

        left_layout.addWidget(self._build_image_group())
        left_layout.addWidget(self._build_text_group())
        left_layout.addWidget(self._build_draw_group())
        left_layout.addStretch(1)

        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(10)

        title = QLabel("实时线稿预览区")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #0f172a;")
        title.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(title)

        self.preview_scene = QGraphicsScene(self)
        self.preview_view = PreviewView(self.preview_scene)
        preview_layout.addWidget(self.preview_view, stretch=1)
        self._render_empty_preview()

        root_layout.addWidget(left_panel)
        root_layout.addWidget(preview_container, stretch=1)
        self.setCentralWidget(central)

        self.setStyleSheet(
            """
            QMainWindow { background: #eef2ff; }
            QGroupBox {
                border: 1px solid #cbd5e1;
                border-radius: 10px;
                margin-top: 12px;
                background: white;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
            QPushButton {
                min-height: 36px;
                border-radius: 8px;
                background: #dbeafe;
                border: 1px solid #93c5fd;
            }
            QPushButton:hover { background: #bfdbfe; }
            QPushButton#PrimaryAction {
                background: #16a34a;
                color: white;
                border: none;
                font-weight: 700;
            }
            QPushButton#DangerAction {
                background: #dc2626;
                color: white;
                border: none;
                font-weight: 700;
            }
            QLineEdit, QFontComboBox, QSpinBox {
                min-height: 32px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 8px;
                background: white;
            }
            """
        )

    def _build_image_group(self) -> QGroupBox:
        group = QGroupBox("方案 A：导入图片")
        layout = QVBoxLayout(group)

        self.image_path_label = QLabel("未选择图片")
        self.image_path_label.setWordWrap(True)
        layout.addWidget(self.image_path_label)

        self.detail_slider = QSlider(Qt.Horizontal)
        self.detail_slider.setRange(1, 100)
        self.detail_slider.setValue(55)
        self.detail_slider.valueChanged.connect(self._update_detail_label)

        detail_row = QHBoxLayout()
        detail_row.addWidget(QLabel("精细度"))
        detail_row.addWidget(self.detail_slider, stretch=1)
        self.detail_value_label = QLabel()
        detail_row.addWidget(self.detail_value_label)
        layout.addLayout(detail_row)
        self._update_detail_label(self.detail_slider.value())

        select_button = QPushButton("1. 选择图片")
        select_button.clicked.connect(self._select_image)
        layout.addWidget(select_button)

        self.refresh_image_button = QPushButton("2. 生成图片线稿")
        self.refresh_image_button.clicked.connect(self._generate_image_outline)
        self.refresh_image_button.setEnabled(False)
        layout.addWidget(self.refresh_image_button)
        return group

    def _build_text_group(self) -> QGroupBox:
        group = QGroupBox("方案 B：输入文字")
        layout = QFormLayout(group)

        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("请输入中文或英文内容...")
        layout.addRow("文字", self.text_input)

        self.font_combo = QFontComboBox()
        layout.addRow("字体", self.font_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(48, 320)
        self.font_size_spin.setValue(160)
        layout.addRow("字号", self.font_size_spin)

        create_button = QPushButton("生成文字线稿")
        create_button.clicked.connect(self._generate_text_outline)
        layout.addRow(create_button)
        return group

    def _build_draw_group(self) -> QGroupBox:
        group = QGroupBox("全局绘制设置")
        layout = QVBoxLayout(group)

        button_row = QHBoxLayout()
        button_row.addWidget(QLabel("绘制按键"))
        self.left_button_radio = QRadioButton("左键")
        self.right_button_radio = QRadioButton("右键")
        self.left_button_radio.setChecked(True)
        button_row.addWidget(self.left_button_radio)
        button_row.addWidget(self.right_button_radio)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("绘制速度"))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 300)
        self.speed_slider.setValue(65)
        self.speed_slider.valueChanged.connect(self._update_speed_label)
        speed_row.addWidget(self.speed_slider, stretch=1)
        self.speed_value_label = QLabel()
        speed_row.addWidget(self.speed_value_label)
        layout.addLayout(speed_row)
        self._update_speed_label(self.speed_slider.value())

        countdown_row = QHBoxLayout()
        countdown_row.addWidget(QLabel("倒计时"))
        self.countdown_spin = QSpinBox()
        self.countdown_spin.setRange(1, 10)
        self.countdown_spin.setValue(3)
        countdown_row.addWidget(self.countdown_spin)
        countdown_row.addStretch(1)
        layout.addLayout(countdown_row)

        self.region_label = QLabel("目标区域：未选择")
        self.region_label.setWordWrap(True)
        layout.addWidget(self.region_label)

        self.start_button = QPushButton("开始绘制线稿")
        self.start_button.setObjectName("PrimaryAction")
        self.start_button.clicked.connect(self._begin_draw_flow)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("停止绘制 / Esc")
        self.stop_button.setObjectName("DangerAction")
        self.stop_button.clicked.connect(self.stop_drawing)
        layout.addWidget(self.stop_button)
        return group

    def _render_empty_preview(self) -> None:
        self.preview_scene.clear()
        self.preview_scene.setSceneRect(0, 0, 900, 620)
        item = QGraphicsTextItem("请先在左侧导入图片或生成文字线稿。")
        font = QFont()
        font.setPointSize(16)
        item.setFont(font)
        item.setDefaultTextColor(QColor("#94a3b8"))
        item.setPos(220, 280)
        self.preview_scene.addItem(item)

    def _set_status(self, text: str) -> None:
        self.status_label.setText(f"状态：{text}")

    def _update_detail_label(self, value: int) -> None:
        self.detail_value_label.setText(str(value))

    def _update_speed_label(self, value: int) -> None:
        self.speed_value_label.setText(str(value))

    def _select_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not file_path:
            return
        self.image_path_label.setText(file_path)
        self.refresh_image_button.setEnabled(True)

    def _generate_image_outline(self) -> None:
        image_path = self.image_path_label.text().strip()
        if not image_path or not Path(image_path).exists():
            self._show_warning("请选择有效的图片文件。")
            return
        try:
            document = self.image_outline_service.generate_outline_from_image(
                image_path,
                self.detail_slider.value(),
            )
        except ImageOutlineError as exc:
            self._show_warning(str(exc))
            return
        self.current_document = document
        self.selected_region = None
        self.pending_paths = []
        self.region_label.setText("目标区域：未选择")
        self._render_document(document)
        self._set_status("图片线稿已生成")

    def _generate_text_outline(self) -> None:
        try:
            document = self.text_outline_service.generate_outline_from_text(
                self.text_input.text(),
                self.font_combo.currentFont().family(),
                self.font_size_spin.value(),
            )
        except TextOutlineError as exc:
            self._show_warning(str(exc))
            return
        self.current_document = document
        self.selected_region = None
        self.pending_paths = []
        self.region_label.setText("目标区域：未选择")
        self._render_document(document)
        self._set_status("文字线稿已生成")

    def _render_document(self, document: OutlineDocument, fitted_paths: list[PathStroke] | None = None) -> None:
        self.preview_scene.clear()
        paths = fitted_paths if fitted_paths is not None else document.paths
        if not paths:
            self._render_empty_preview()
            return

        pen = QPen(QColor("#111827"), 1.5)
        for stroke in paths:
            if len(stroke.points) < 2:
                continue
            path = QPainterPath()
            path.moveTo(stroke.points[0].x, stroke.points[0].y)
            for point in stroke.points[1:]:
                path.lineTo(point.x, point.y)
            if stroke.closed:
                path.closeSubpath()
            item = QGraphicsPathItem(path)
            item.setPen(pen)
            self.preview_scene.addItem(item)

        bounds = self.path_transform_service.bounds_for_paths(paths)
        if bounds.width <= 0 or bounds.height <= 0:
            self.preview_scene.setSceneRect(0, 0, 900, 620)
        else:
            padding = 24
            self.preview_scene.setSceneRect(
                bounds.left - padding,
                bounds.top - padding,
                bounds.width + padding * 2,
                bounds.height + padding * 2,
            )
        self.preview_view.fitInView(self.preview_scene.sceneRect(), Qt.KeepAspectRatio)

    def _begin_draw_flow(self) -> None:
        if self.draw_thread is not None:
            self._show_warning("当前已有绘制任务正在运行。")
            return
        if self.current_document is None or self.current_document.is_empty():
            self._show_warning("请先导入图片或生成文字线稿。")
            return
        self.stop_event.clear()
        self._set_status("即将最小化，请在目标软件中框选绘制区域")
        self.showMinimized()
        QTimer.singleShot(250, self.region_selector.show_selector)

    def _handle_region_selected(self, region: DrawRegion) -> None:
        self.selected_region = region
        self.region_label.setText(
            f"目标区域：({region.left}, {region.top}) - {region.width} x {region.height}"
        )
        if self.current_document is None:
            self._restore_window()
            self._set_status("区域已记录")
            return

        self.pending_paths = self.path_transform_service.fit_outline_to_region(
            self.current_document,
            region,
            simplify_tolerance=1.5,
        )
        self._render_document(self.current_document, fitted_paths=self.pending_paths)

        if not self.pending_paths:
            self._restore_window()
            self._show_warning("当前线稿无法适配到所选区域。")
            return

        self.remaining_countdown = self.countdown_spin.value()
        self._set_status(f"{self.remaining_countdown} 秒后开始绘制")
        self.countdown_timer.start(1000)

    def _handle_region_selection_cancelled(self) -> None:
        self._restore_window()
        self._set_status("区域选择已取消")

    def _tick_countdown(self) -> None:
        self.remaining_countdown -= 1
        if self.remaining_countdown > 0:
            self._set_status(f"{self.remaining_countdown} 秒后开始绘制")
            return
        self.countdown_timer.stop()
        self._launch_drawing()

    def _launch_drawing(self) -> None:
        if not self.pending_paths:
            self._restore_window()
            self._show_warning("没有可绘制的路径。")
            return

        config = DrawConfig(
            mouse_button="left" if self.left_button_radio.isChecked() else "right",
            move_speed=self.speed_slider.value(),
            countdown_seconds=self.countdown_spin.value(),
            simplify_tolerance=1.5,
        )
        self.draw_thread = QThread(self)
        self.draw_worker = DrawingWorker(
            service=self.mouse_draw_service,
            paths=self.pending_paths,
            config=config,
            stop_event=self.stop_event,
        )
        self.draw_worker.moveToThread(self.draw_thread)
        self.draw_thread.started.connect(self.draw_worker.run)
        self.draw_worker.started.connect(lambda: self._set_status("绘制中"))
        self.draw_worker.finished.connect(self._drawing_finished)
        self.draw_worker.failed.connect(self._drawing_failed)
        self.draw_worker.finished.connect(self.draw_thread.quit)
        self.draw_worker.failed.connect(self.draw_thread.quit)
        self.draw_thread.finished.connect(self._cleanup_drawing_thread)
        self.draw_thread.start()

    def stop_drawing(self) -> None:
        self.countdown_timer.stop()
        self.stop_event.set()
        self.region_selector.hide()
        self._restore_window()
        if self.draw_thread is None:
            self._set_status("已停止")

    def _drawing_finished(self) -> None:
        self._restore_window()
        if self.stop_event.is_set():
            self._set_status("绘制已停止")
        else:
            self._set_status("绘制完成")

    def _drawing_failed(self, message: str) -> None:
        self._restore_window()
        self._set_status("绘制失败")
        self._show_warning(f"绘制失败：{message}")

    def _cleanup_drawing_thread(self) -> None:
        if self.draw_worker is not None:
            self.draw_worker.deleteLater()
        if self.draw_thread is not None:
            self.draw_thread.deleteLater()
        self.draw_worker = None
        self.draw_thread = None

    def _restore_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _show_warning(self, message: str) -> None:
        QMessageBox.warning(self, "提示", message)
