"""Research Harness — a harness for long-horizon research agents.

The kernel never calls a model. An agent performs the packets the harness
hands out; the harness verifies each pass against a ground the model cannot
smooth away. See ``docs/REBUILD_DESIGN.md``.
"""

__version__ = "1.0.0a0"
__all__ = ["__version__"]
