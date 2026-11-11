from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class OverlayWindow(QWidget):
    """Floating, always-on-top status overlay. Shows mic state, transcript and result."""

    trigger_listen = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(420, 140)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        self.status_label = QLabel("JARVIS idle")
        self.status_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.status_label.setStyleSheet("color: #7ec8ff;")

        self.transcript_label = QLabel("")
        self.transcript_label.setWordWrap(True)
        self.transcript_label.setFont(QFont("Segoe UI", 10))
        self.transcript_label.setStyleSheet("color: #e6e6e6;")

        layout.addWidget(self.status_label)
        layout.addWidget(self.transcript_label)

        self.setStyleSheet(
            "background-color: rgba(10, 14, 23, 220); border-radius: 10px;"
        )

        self._position_top_right()

        self._drag_pos = None

    def _position_top_right(self):
        screen = self.screen().availableGeometry()
        x = screen.right() - self.width() - 24
        y = screen.top() + 24
        self.move(x, y)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_transcript(self, text: str):
        self.transcript_label.setText(text)

    def show_overlay(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_overlay(self):
        self.hide()
