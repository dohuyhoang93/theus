import pytest
from theus.config import ConfigFactory
from theus_core import AuditLevel, AuditRecipe
import yaml
import os


class TestConfigFactory:
    """Unit tests for ConfigFactory YAML parsing."""

    def test_load_recipe_parses_level_and_thresholds(self, tmp_path):
        """Verify ConfigFactory correctly parses level, threshold_min, and threshold_max from YAML."""
        config_file = tmp_path / "audit_recipe.yaml"
        config_content = {
            "audit": {
                "level": "Stop",
                "threshold_min": 2,
                "threshold_max": 5,
                "reset_on_success": True
            }
        }
        config_file.write_text(yaml.dump(config_content))

        book = ConfigFactory.load_recipe(str(config_file))

        # Verify all fields parsed correctly
        assert book.rust_recipe.level == AuditLevel.Stop
        assert book.rust_recipe.threshold_min == 2
        assert book.rust_recipe.threshold_max == 5
        assert book.rust_recipe.reset_on_success == True

    def test_load_recipe_supports_level_abbreviations(self, tmp_path):
        """Verify ConfigFactory accepts single-letter level codes (S/A/B/C)."""
        config_file = tmp_path / "audit_recipe.yaml"
        
        test_cases = [
            ("S", AuditLevel.Stop),
            ("A", AuditLevel.Abort),
            ("B", AuditLevel.Block),
            ("C", AuditLevel.Count),
        ]
        
        for level_str, expected_enum in test_cases:
            config_content = {
                "audit": {
                    "level": level_str,
                    "threshold_max": 3
                }
            }
            config_file.write_text(yaml.dump(config_content))
            
            book = ConfigFactory.load_recipe(str(config_file))
            assert book.rust_recipe.level == expected_enum, f"Failed for level={level_str}"

    def test_load_recipe_defaults_to_block_if_level_missing(self, tmp_path):
        """Verify default level is Block when not specified."""
        config_file = tmp_path / "audit_recipe.yaml"
        config_content = {
            "audit": {
                "threshold_max": 3
            }
        }
        config_file.write_text(yaml.dump(config_content))

        book = ConfigFactory.load_recipe(str(config_file))

        assert book.rust_recipe.level == AuditLevel.Block

    def test_load_recipe_defaults_threshold_min_to_zero(self, tmp_path):
        """Verify threshold_min defaults to 0 when not specified."""
        config_file = tmp_path / "audit_recipe.yaml"
        config_content = {
            "audit": {
                "level": "Block",
                "threshold_max": 5
            }
        }
        config_file.write_text(yaml.dump(config_content))

        book = ConfigFactory.load_recipe(str(config_file))

        assert book.rust_recipe.threshold_min == 0

    def test_load_recipe_supports_legacy_max_retries(self, tmp_path):
        """Verify backward compatibility with max_retries field."""
        config_file = tmp_path / "audit_recipe.yaml"
        config_content = {
            "audit": {
                "max_retries": 7  # Legacy field name
            }
        }
        config_file.write_text(yaml.dump(config_content))

        book = ConfigFactory.load_recipe(str(config_file))

        assert book.rust_recipe.threshold_max == 7
