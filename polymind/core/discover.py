"""Entry point-based plugin discovery for strategies, factors, and workflows.

Uses ``importlib.metadata.entry_points`` to find installed packages that
register themselves under the ``polymind.strategies``, ``polymind.factors``,
and ``polymind.workflows`` entry point groups.
"""

from __future__ import annotations

from importlib.metadata import entry_points


def discover_strategies() -> dict[str, type]:
    """Discover installed strategy plugins via ``polymind.strategies`` entry point group.

    Returns
    -------
    dict[str, type]
        Mapping of entry point name to loaded class.
        Empty dict when no plugins are installed.
    """
    return _discover("strategies")


def discover_factors() -> dict[str, type]:
    """Discover installed factor plugins via ``polymind.factors`` entry point group.

    Returns
    -------
    dict[str, type]
        Mapping of entry point name to loaded class.
        Empty dict when no plugins are installed.
    """
    return _discover("factors")


def discover_workflows() -> dict[str, type]:
    """Discover installed workflow plugins via ``polymind.workflows`` entry point group.

    Returns
    -------
    dict[str, type]
        Mapping of entry point name to loaded class.
        Empty dict when no plugins are installed.
    """
    return _discover("workflows")


def discover_all() -> dict[str, dict[str, type]]:
    """Run all discover functions.

    Returns
    -------
    dict[str, dict[str, type]]
        Nested dictionary::

            {
                "strategies": {"name": class, ...},
                "factors": {"name": class, ...},
                "workflows": {"name": class, ...},
            }
    """
    return {
        "strategies": discover_strategies(),
        "factors": discover_factors(),
        "workflows": discover_workflows(),
    }


def _discover(kind: str) -> dict[str, type]:
    """Generic discovery for a given plugin kind.

    Parameters
    ----------
    kind : str
        One of ``"strategies"``, ``"factors"``, or ``"workflows"``.

    Returns
    -------
    dict[str, type]
        Discovered plugins keyed by entry point name.
    """
    group = f"polymind.{kind}"
    result: dict[str, type] = {}

    for ep in entry_points(group=group):
        try:
            cls = ep.load()
            result[ep.name] = cls
        except Exception:  # noqa: BLE001
            # Skip entry points that fail to load — the user may not have
            # all dependencies installed for every plugin.
            continue

    return result
