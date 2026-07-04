"""
Base types for the Strategy Templates Library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TemplateInfo:
    """Metadata for a deployable strategy template.

    Parameters
    ----------
    name:
        Unique template identifier (e.g. ``amm_concentrated``).
    description:
        Human-readable description of the template's purpose.
    strategy_type:
        Which strategy backend to use (e.g. ``amm``, ``bands``).
    params:
        Default parameters for the strategy config.
    risk_limits:
        Recommended risk limits (max_position, max_exposure, etc.).
    tags:
        Searchable tags (e.g. ``maker``, ``low-risk``, ``beginner``).
    """

    name: str
    description: str
    strategy_type: str
    params: dict[str, Any] = field(default_factory=dict)
    risk_limits: dict[str, float] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a dict representation suitable for CLI display."""
        return {
            "name": self.name,
            "description": self.description,
            "type": self.strategy_type,
            "params": dict(self.params),
            "risk_limits": dict(self.risk_limits),
            "tags": list(self.tags),
        }
