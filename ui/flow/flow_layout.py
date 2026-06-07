NODE_WIDTH = 440
NODE_HEIGHT = 136

ICON_BOX_SIZE = 72
ICON_ASSET_SCALE = 1.2
ICON_SIZE = int(ICON_ASSET_SCALE * ICON_BOX_SIZE)

TITLE_SIZE = 18
DESCRIPTION_SIZE = 13

BRANCH_SPACING = 90


def calculate_parent_anchor_x(index: int, count: int, width: int) -> float:
    center = width / 2

    if count <= 1:
        return center

    anchor_spread = width * 0.18
    start_x = center - anchor_spread / 2
    step = anchor_spread / (count - 1)

    return start_x + step * index

def calculate_subtree_width(node_id: str, nodes: dict, zoom_factor: float) -> int:
    node = nodes.get(node_id)

    if not node or not node.children:
        return int(NODE_WIDTH * zoom_factor)

    child_count = len(node.children)

    child_widths = [
        calculate_subtree_width(child_id, nodes, zoom_factor)
        for child_id in node.children
    ]

    children_total_width = (
        sum(child_widths)
        + (child_count - 1) * BRANCH_SPACING
    )

    return max(
        int(NODE_WIDTH * zoom_factor),
        children_total_width
    )

def calculate_branch_layout(node, nodes: dict, zoom_factor: float) -> dict:
    node_width = int(NODE_WIDTH * zoom_factor)
    child_count = len(node.children)

    if child_count > 0:
        child_widths = [
            calculate_subtree_width(child_id, nodes, zoom_factor)
            for child_id in node.children
        ]

        required_width = (
            sum(child_widths)
            + (child_count - 1) * BRANCH_SPACING
        )

        required_width = max(required_width, node_width)
    else:
        child_widths = []
        required_width = node_width

    return {
        "branch_spacing": BRANCH_SPACING,
        "node_width": node_width,
        "child_count": child_count,
        "child_widths": child_widths,
        "required_width": required_width,
    }