from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class FlowNode:
    title: str
    description: str = ""

    icon: str = "character"

    status: str = "locked"
    completed: bool = False

    x: int = 0
    y: int = 0

    id: str = field(default_factory=lambda: str(uuid4()))
    children: list[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "icon": self.icon,
            "status": self.status,
            "completed": self.completed,
            "x": self.x,
            "y": self.y,
            "children": self.children,
        }

    @staticmethod
    def from_dict(data: dict):
        return FlowNode(
            id=data.get("id", str(uuid4())),
            title=data.get("title", ""),
            description=data.get("description", ""),
            icon=data.get("icon", "character"),
            status=data.get("status", "locked"),
            completed=data.get("completed", False),
            x=data.get("x", 0),
            y=data.get("y", 0),
            children=data.get("children", []),
        )