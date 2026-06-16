from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath, QPolygonF

from ui.flow.flow_layout import NODE_WIDTH, NODE_HEIGHT


class FlowMapArea(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self.resize(8000, 8000)
        self.setMouseTracking(True)

    def paintEvent(self, event):
        super().paintEvent(event)
        self._draw_connections()

    def _draw_connections(self):
        nodes = getattr(self.window, "nodes", {})
        if not nodes:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        zoom = self.window.zoom_factor
        node_w = NODE_WIDTH * zoom
        node_h = NODE_HEIGHT * zoom

        color = QColor(95, 170, 255, 210)
        pen = QPen(color)
        pen.setWidth(max(2, int(3 * zoom)))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        for node_id, node in nodes.items():
            for child_id in node.children:
                child = nodes.get(child_id)
                if not child:
                    continue

                px = node.x * zoom + node_w / 2
                py = node.y * zoom + node_h
                cx = child.x * zoom + node_w / 2
                cy = child.y * zoom

                arrow_tip = QPointF(cx, cy)
                line_end = QPointF(cx, cy - int(14 * zoom))
                dy = cy - py

                if abs(cx - px) < 2:
                    painter.drawLine(QPointF(px, py), line_end)
                else:
                    cp1 = QPointF(px, py + dy * 0.35)
                    cp2 = QPointF(cx, cy - dy * 0.35)
                    path = QPainterPath()
                    path.moveTo(QPointF(px, py))
                    path.cubicTo(cp1, cp2, line_end)
                    painter.drawPath(path)

                s = int(10 * zoom)
                arrow = QPolygonF([
                    arrow_tip,
                    QPointF(cx - s, cy - s * 1.6),
                    QPointF(cx + s, cy - s * 1.6),
                ])
                painter.setBrush(color)
                painter.drawPolygon(arrow)
                painter.setBrush(Qt.NoBrush)
