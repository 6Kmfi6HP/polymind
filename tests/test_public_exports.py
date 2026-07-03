"""Public package export contracts."""

import pytest


def exported_public_names():
    import polymind

    return [name for name in polymind.__all__ if not name.startswith("__")]


def test_public_exports_do_not_advertise_missing_backtest_engine():
    import polymind

    assert "BacktestEngine" not in exported_public_names(), (
        "polymind.__all__ must not advertise BacktestEngine until "
        "polymind.backtesting.engine exists and is importable"
    )


@pytest.mark.parametrize("name", exported_public_names())
def test_public_exports_are_importable(name):
    import polymind

    try:
        exported = getattr(polymind, name)
    except Exception as exc:  # pragma: no cover - failure path is the contract signal
        pytest.fail(f"polymind.{name} is listed as public but cannot be imported: {exc!r}")

    assert exported is not None
