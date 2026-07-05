"""Plugin Registry — singleton registry for strategies, factors, and workflows."""

from __future__ import annotations


class PluginRegistry:
    """Global registry for strategies, factors, and workflow plugins."""

    _instance: PluginRegistry | None = None
    _strategies: dict[str, type]
    _factors: dict[str, type]
    _workflows: dict[str, type]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._strategies = {}
            cls._instance._factors = {}
            cls._instance._workflows = {}
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset registry (for testing)."""
        cls._instance = None

    def register_strategy(self, name: str, cls_type: type) -> None:
        if name in self._strategies:
            raise ValueError(f"Strategy '{name}' already registered")
        self._strategies[name] = cls_type

    def register_factor(self, name: str, cls_type: type) -> None:
        if name in self._factors:
            raise ValueError(f"Factor '{name}' already registered")
        self._factors[name] = cls_type

    def register_workflow(self, name: str, cls_type: type) -> None:
        if name in self._workflows:
            raise ValueError(f"Workflow '{name}' already registered")
        self._workflows[name] = cls_type

    def remove_factor(self, name: str) -> None:
        """Remove a registered factor (no-op if not found)."""
        self._factors.pop(name, None)

    def get_strategy(self, name: str) -> type | None:
        return self._strategies.get(name)

    def get_factor(self, name: str) -> type | None:
        return self._factors.get(name)

    def get_workflow(self, name: str) -> type | None:
        return self._workflows.get(name)

    def list_strategies(self) -> dict[str, type]:
        return dict(self._strategies)

    def list_factors(self) -> dict[str, type]:
        return dict(self._factors)

    def list_workflows(self) -> dict[str, type]:
        return dict(self._workflows)
