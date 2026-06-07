from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt

class FlowMapViewport(QWidget):
    def __init__(self, parent_window=None):
        super().__init__()

        self.parent_window = parent_window

        self.setObjectName("FlowMapViewport")
        self.setCursor(Qt.OpenHandCursor)

        self.is_panning = False
        self.pan_start_pos = None
        self.pan_target = None

    def set_pan_target(self, widget):
        self.pan_target = widget

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_panning = True
            self.pan_start_pos = event.position().toPoint()
            if self.parent_window:
                self.parent_window.set_tool_cursor(
                    "cursor_hold.png"
                )

    def mouseMoveEvent(self, event):
        #print("Viewport Mouse Move")
        if self.parent_window:
            self.parent_window.update_mouse_position_debug(
                event.position().toPoint(),
                self
            )

        if not self.is_panning or not self.pan_target:
            return

        current_pos = event.position().toPoint()
        delta = current_pos - self.pan_start_pos
        self.pan_start_pos = current_pos

        self.pan_target.move(
            self.pan_target.x() + delta.x(),
            self.pan_target.y() + delta.y()
        )

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_panning = False

            if self.parent_window:
                self.parent_window.apply_current_tool_cursor()

    def wheelEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            if self.parent_window:
                delta = event.angleDelta().y()

                if delta > 0:
                    self.parent_window.adjust_zoom(0.1)
                else:
                    self.parent_window.adjust_zoom(-0.1)

            event.accept()
            return

        super().wheelEvent(event)