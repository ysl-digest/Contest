from .base import Source
from .linkareer import LinkareerSource
from .wevity import WevitySource

SOURCES: dict[str, type[Source]] = {
    WevitySource.name: WevitySource,
    LinkareerSource.name: LinkareerSource,
}

__all__ = ["SOURCES", "Source", "WevitySource", "LinkareerSource"]
