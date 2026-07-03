"""
Emergency stop mechanism for Polymind.

A KillSwitch can be triggered via a sentinel file on disk or an
environment variable, allowing rapid circuit-breaking of trading
operations.
"""

from __future__ import annotations

import os


class KillSwitch:
    """Emergency stop that can be activated by a file or environment variable.

    The switch checks for the existence of a sentinel file on disk, or
    the presence of a named environment variable set to ``"1"`` or
    ``"true"`` (case-insensitive).

    Args:
        env_var: Name of the environment variable to check.
            Defaults to ``"POLYMIND_KILL"``.
        file_path: Absolute or relative path to the sentinel file.
            If ``None``, file-based checks are skipped.
    """

    def __init__(
        self, env_var: str = "POLYMIND_KILL", file_path: str | None = None
    ) -> None:
        self._env_var = env_var
        self._file_path = file_path
        self._triggered_flag = False

    def is_triggered(self) -> bool:
        """Check whether the kill switch is currently active.

        Returns ``True`` if a sentinel file exists *or* the configured
        environment variable is set to ``"1"`` or ``"true"``
        (case-insensitive).
        """
        # File check (takes precedence)
        if self._file_path is not None and os.path.exists(self._file_path):
            return True
        # Env var check
        val = os.getenv(self._env_var, "").lower()
        if val in ("1", "true"):
            return True
        # In-process flag
        return self._triggered_flag

    def trigger(self) -> None:
        """Activate the kill switch.

        If a ``file_path`` was configured, the sentinel file is created.
        Otherwise the in-process ``_triggered_flag`` is set, making
        :meth:`is_triggered` return ``True`` for the lifetime of this
        object.
        """
        if self._file_path is not None:
            parent = os.path.dirname(self._file_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self._file_path, "a"):
                os.utime(self._file_path, None)
        else:
            self._triggered_flag = True

    def release(self) -> None:
        """Deactivate the kill switch.

        If a ``file_path`` was configured, the sentinel file is removed.
        Otherwise the in-process ``_triggered_flag`` is cleared.
        """
        if self._file_path is not None:
            try:
                os.remove(self._file_path)
            except FileNotFoundError:
                pass
        else:
            self._triggered_flag = False
