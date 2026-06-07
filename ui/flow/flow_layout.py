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