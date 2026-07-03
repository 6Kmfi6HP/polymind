"""Drawdown tracking — state machine for monitoring drawdown from peak."""

from __future__ import annotations

from enum import Enum, auto


class DrawdownState(Enum):
    """State of the drawdown tracker."""

    NORMAL = auto()
    WARNING = auto()
    STOPPED = auto()
    RECOVERY = auto()


class DrawdownConfig:
    """Configuration thresholds for drawdown state transitions."""

    def __init__(
        self,
        max_drawdown_pct: float = 0.15,
        warning_pct: float = 0.10,
        recovery_pct: float = 0.05,
    ) -> None:
        self.max_drawdown_pct = max_drawdown_pct
        self.warning_pct = warning_pct
        self.recovery_pct = recovery_pct


class DrawdownTracker:
    """Tracks drawdown from peak equity and emits state transitions."""

    def __init__(self, config: DrawdownConfig, initial_peak: float = 10000.0) -> None:
        self.config = config
        self._peak = initial_peak
        self._current_value = initial_peak
        self._state = DrawdownState.NORMAL

    def update(self, current_value: float) -> DrawdownState:
        """Feed a new portfolio value and return the resulting DrawdownState."""
        self._current_value = current_value

        if current_value > self._peak:
            self._peak = current_value
            self._state = DrawdownState.NORMAL
            return self._state

        drawdown = (self._peak - current_value) / self._peak

        if drawdown >= self.config.max_drawdown_pct:
            self._state = DrawdownState.STOPPED
        elif drawdown >= self.config.warning_pct:
            self._state = DrawdownState.WARNING
        elif self._state == DrawdownState.STOPPED and drawdown <= self.config.recovery_pct:
            self._state = DrawdownState.RECOVERY
        else:
            self._state = DrawdownState.NORMAL

        return self._state

    def get_drawdown_pct(self) -> float:
        """Current drawdown as a decimal (0.10 = 10%)."""
        return (self._peak - self._current_value) / self._peak

    def get_peak(self) -> float:
        """The peak value seen so far."""
        return self._peak

    def get_state(self) -> DrawdownState:
        """Current drawdown state."""
        return self._state

    def reset(self, peak: float) -> None:
        """Reset tracker to a new peak and re-enter NORMAL state."""
        self._peak = peak
        self._current_value = peak
        self._state = DrawdownState.NORMAL
