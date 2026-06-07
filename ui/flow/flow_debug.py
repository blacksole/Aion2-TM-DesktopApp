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