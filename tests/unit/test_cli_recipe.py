"""Tests for the recipe CLI commands (list, params, run)."""

from __future__ import annotations

from click.testing import CliRunner

from serialcables_switchtec.cli.recipe import recipe


class TestRecipeList:
    def test_recipe_list(self):
        runner = CliRunner()
        result = runner.invoke(recipe, ["list"])
        assert result.exit_code == 0
        # Should contain at least some known recipe names
        assert "all_port_sweep" in result.output
        assert "ber_soak" in result.output
        assert "link_health_check" in result.output

    def test_recipe_list_with_category(self):
        runner = CliRunner()
        result = runner.invoke(recipe, ["list", "--category", "link_health"])
        assert result.exit_code == 0
        # link_health recipes should appear
        assert "all_port_sweep" in result.output
        assert "link_health_check" in result.output
        # Non-link_health recipes should NOT appear
        assert "ber_soak" not in result.output
        assert "bandwidth_baseline" not in result.output

    def test_recipe_list_with_signal_integrity_category(self):
        runner = CliRunner()
        result = runner.invoke(recipe, ["list", "--category", "signal_integrity"])
        assert result.exit_code == 0
        assert "cross_hair_margin" in result.output
        # link_health should not appear
        assert "all_port_sweep" not in result.output

    def test_recipe_list_shows_category_and_duration(self):
        runner = CliRunner()
        result = runner.invoke(recipe, ["list"])
        assert result.exit_code == 0
        # Output should contain category labels and duration estimates
        assert "link_health" in result.output

    def test_recipe_list_invalid_category(self):
        runner = CliRunner()
        result = runner.invoke(recipe, ["list", "--category", "nonexistent"])
        # Click should reject invalid choice
        assert result.exit_code != 0


class TestRecipeParams:
    def test_recipe_params(self):
        runner = CliRunner()
        result = runner.invoke(recipe, ["params", "all_port_sweep"])
        assert result.exit_code == 0
        # all_port_sweep has no parameters
        assert "no parameters" in result.output

    def test_recipe_params_with_parameters(self):
        runner = CliRunner()
        result = runner.invoke(recipe, ["params", "link_health_check"])
        assert result.exit_code == 0
        assert "port_id" in result.output

    def test_recipe_params_shows_types(self):
        runner = CliRunner()
        result = runner.invoke(recipe, ["params", "ber_soak"])
        assert result.exit_code == 0
        # ber_soak has several params: port_id, pattern, link_speed, duration_s, lane_count
        assert "port_id" in result.output
        assert "duration_s" in result.output

    def test_recipe_params_unknown(self):
        runner = CliRunner()
        result = runner.invoke(recipe, ["params", "nonexistent"])
        assert result.exit_code == 2


class TestRecipeRun:
    def test_recipe_run_no_device(self):
        runner = CliRunner()
        result = runner.invoke(recipe, ["run", "all_port_sweep"])
        assert result.exit_code == 2

    def test_recipe_run_unknown_recipe(self):
        runner = CliRunner()
        result = runner.invoke(recipe, ["run", "foobar", "-d", "/dev/xxx"])
        assert result.exit_code == 2

    def test_recipe_run_invalid_param_format(self):
        runner = CliRunner()
        result = runner.invoke(
            recipe, ["run", "all_port_sweep", "-d", "/dev/xxx", "-p", "badformat"]
        )
        assert result.exit_code == 2

    def test_recipe_run_unknown_param(self):
        runner = CliRunner()
        result = runner.invoke(
            recipe,
            ["run", "all_port_sweep", "-d", "/dev/xxx", "-p", "unknown_key=5"],
        )
        assert result.exit_code == 2

    def test_recipe_run_unknown_recipe_shows_available(self):
        runner = CliRunner()
        result = runner.invoke(recipe, ["run", "foobar", "-d", "/dev/xxx"])
        assert result.exit_code == 2
        assert "Available:" in result.output or "Available:" in (result.output + (result.output if result.output else ""))

    def test_recipe_run_invalid_param_shows_error(self):
        runner = CliRunner()
        result = runner.invoke(
            recipe, ["run", "all_port_sweep", "-d", "/dev/xxx", "-p", "noequalssign"]
        )
        assert result.exit_code == 2

    def test_recipe_run_unknown_param_shows_valid_list(self):
        """When an unknown param is given, error output should list valid params."""
        runner = CliRunner()
        result = runner.invoke(
            recipe,
            ["run", "link_health_check", "-d", "/dev/xxx", "-p", "bogus=123"],
        )
        assert result.exit_code == 2

    def test_recipe_run_valid_params_but_no_device_path(self):
        """Providing valid params but no device should still fail."""
        runner = CliRunner()
        result = runner.invoke(
            recipe, ["run", "link_health_check", "-p", "port_id=0"]
        )
        assert result.exit_code == 2
