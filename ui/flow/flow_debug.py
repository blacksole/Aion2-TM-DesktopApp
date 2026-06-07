DEBUG_MODE = True
SHOW_MOUSE_COORDS = True
SHOW_NODE_CENTER = True
SHOW_ANCHORS = False
SHOW_LAYOUT_BOXES = False

def format_mouse_debug_text(
    content_pos,
    map_pos,
    viewport_center,
    map_area_pos,
    node_center_text,
):
    if not DEBUG_MODE:
        return ""

    return (
        f"Mouse | Content: {content_pos.x()}, {content_pos.y()} "
        f"| Map: {map_pos.x()}, {map_pos.y()} "
        f"| Viewport Center: {viewport_center.x()}, {viewport_center.y()} "
        f"| MapArea Pos: {map_area_pos.x()}, {map_area_pos.y()} "
        f"| {node_center_text}"
    )

def update_mouse_position_debug_label(window, pos, source_widget):
    if not DEBUG_MODE:
        window.mouse_debug_label.setText("")
        return

    global_pos = source_widget.mapToGlobal(pos)
    content_pos = window.content.mapFromGlobal(global_pos)
    map_pos = window.map_area.mapFromGlobal(global_pos)

    viewport_center = window.map_viewport.rect().center()
    map_area_pos = window.map_area.pos()

    node_center_text = "Nodes Center: -"

    if window.map_layout.count() > 0:
        flow_widget = window.map_layout.itemAt(0).widget()

        if flow_widget:
            flow_center = flow_widget.geometry().center()

            node_center_global = window.map_area.mapToGlobal(flow_center)
            node_center_viewport = window.map_viewport.mapFromGlobal(
                node_center_global
            )

            node_center_text = (
                f"Nodes Center Map: {flow_center.x()}, {flow_center.y()} "
                f"| Nodes Center Viewport: "
                f"{node_center_viewport.x()}, {node_center_viewport.y()}"
            )

    window.mouse_debug_label.setText(
        format_mouse_debug_text(
            content_pos,
            map_pos,
            viewport_center,
            map_area_pos,
            node_center_text,
        )
    )