from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen


class FlowCanvas(QWidget):
    def __init__(self):
        super().__init__()

        self.setObjectName("FlowCanvas")

    def set_pan_target(self, widget):
        self.pan_target = widget

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        spacing = 72
        color = QColor(255, 255, 255, 12)

        pen = QPen(color)
        pen.setWidth(1)

        painter.setPen(pen)

        for x in range(0, self.width(), spacing):
            for y in range(0, self.height(), spacing):
                painter.drawLine(x - 4, y, x + 4, y)
                painter.drawLine(x, y - 4, x, y + 4)