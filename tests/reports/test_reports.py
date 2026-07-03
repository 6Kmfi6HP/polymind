"""Test reports package imports."""
from polymind import reports


def test_reports_importable():
    assert hasattr(reports, "__version__")
    assert reports.__version__ == "0.1.0"
