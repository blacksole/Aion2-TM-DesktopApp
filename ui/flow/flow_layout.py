NODE_WIDTH = 440
NODE_HEIGHT = 136

ICON_BOX_SIZE = 72
ICON_ASSET_SCALE = 1.2
ICON_SIZE = int(ICON_ASSET_SCALE * ICON_BOX_SIZE)

TITLE_SIZE = 18
DESCRIPTION_SIZE = 13

BRANCH_SPACING = 90

CONNECTOR_BASE_HEIGHT = 70
CONNECTOR_EXTRA_PER_CHILD = 14


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

def calculate_connector_height(child_count: int, zoom_factor: float) -> int:
    return (
        CONNECTOR_BASE_HEIGHT
        + int(zoom_factor * child_count * CONNECTOR_EXTRA_PER_CHILD)
    )

def build_connections(
    child_count: int,
    child_widths: list[int],
    branch_spacing: int,
    node_width: int,
    required_width: int,
) -> list[tuple[float, float]]:
    connections = []

    for index in range(child_count):
        parent_anchor_x = calculate_parent_anchor_x(
            index=index,
            count=child_count,
            width=node_width,
        )

        parent_offset_x = (required_width - node_width) / 2
        start_x = parent_offset_x + parent_anchor_x

        child_x = sum(child_widths[:index]) + index * branch_spacing
        child_top_center_x = child_x + child_widths[index] / 2

        connections.append((start_x, child_top_center_x))

    return connections

