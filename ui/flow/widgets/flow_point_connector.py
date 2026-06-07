from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QPainterPath,
    QPolygonF,
)


class FlowPointConnector(QWidget):
    def __init__(
        self,
        connections,
        zoom=1.0,
        height=110,
        parent_window=None,
    ):
        super().__init__()

        self.connections = connections
        self.zoom = zoom
        self.parent_window = parent_window

        self.setFixedHeight(int(height * zoom))
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        color = QColor(95, 170, 255, 210)

        pen = QPen(color)
        pen.setWidth(max(2, int(3 * self.zoom)))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)

        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        for start_x, end_x in self.connections:
            start = QPointF(start_x, 0)

            arrow_tip = QPointF(end_x, self.height())
            line_end = QPointF(
                end_x,
                self.height() - int(14 * self.zoom)
            )

            dx = arrow_tip.x() - start.x()

            if abs(dx) < 2:
                painter.drawLine(start, line_end)
            else:
                cp1 = QPointF(
                    start.x(),
                    start.y() + self.height() * 0.35
                )

                cp2 = QPointF(
                    line_end.x(),
                    line_end.y() - self.height() * 0.35
                )

                path = QPainterPath()
                path.moveTo(start)
                path.cubicTo(cp1, cp2, line_end)

                painter.drawPath(path)

            self.paint_arrow(painter, color, arrow_tip)

    def paint_arrow(self, painter, color, end):
        arrow_size = int(10 * self.zoom)

        arrow_tip = QPointF(end.x(), end.y())

        arrow = QPolygonF([
            arrow_tip,
            QPointF(end.x() - arrow_size, end.y() - arrow_size * 1.6),
            QPointF(end.x() + arrow_size, end.y() - arrow_size * 1.6),
        ])

        painter.setBrush(color)
        painter.drawPolygon(arrow)
        painter.setBrush(Qt.NoBrush)