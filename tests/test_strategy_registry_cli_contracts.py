"""Strategy registry and CLI contracts."""

from collections.abc import Mapping

from click.testing import CliRunner


def test_strategy_registry_lists_registered_strategy_metadata(monkeypatch):
    import polymind.strategies as registry

    monkeypatch.setattr(registry, "_registry", {})

    @registry.register("contract-mm")
    class ContractStrategy:
        """Registry driven strategy."""

    listed = registry.list_strategies()

    assert "contract-mm" in listed
    assert isinstance(listed["contract-mm"], Mapping)
    assert listed["contract-mm"]["name"] == "contract-mm"
    assert listed["contract-mm"]["description"] == "Registry driven strategy."


def test_cli_strategies_command_renders_registry_entries(monkeypatch):
    from polymind import strategies as registry
    from polymind.cli import main as cli_main

    def fake_list_strategies():
        return {
            "registry-only": {
                "name": "registry-only",
                "description": "Registry provided strategy",
                "status": "ready",
            }
        }

    monkeypatch.setattr(registry, "list_strategies", fake_list_strategies)

    result = CliRunner().invoke(cli_main.cli, ["strategies"])

    assert result.exit_code == 0, result.output
    assert "registry-only" in result.output
    assert "Registry provided strategy" in result.output
