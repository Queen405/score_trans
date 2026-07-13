"""Publication-grade jianpu engraving engine.

This package is the only production rendering implementation.  Parsing and
conversion live in the domain layer; everything from intrinsic measurement to
SVG/PDF/PNG output lives here.
"""

from .renderer import PublicationRenderer
from .style import PublicationStyle

__all__ = ["PublicationRenderer", "PublicationStyle"]
