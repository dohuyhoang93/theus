import os
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from theus.templates.registry import TemplateRegistry
from theus.cli import init_project

class TestCLI_v3:
    """
    Test Suite for Theus v3.1 CLI Enhancements.
    """

    @pytest.fixture
    def clean_env(self):
        base_dir = Path("test_cli_env")
        if base_dir.exists():
            shutil.rmtree(base_dir)
        base_dir.mkdir()
        yield base_dir
        if base_dir.exists():
            shutil.rmtree(base_dir)

    def test_template_registry(self):
        """Verify TemplateRegistry returns correct files."""
        templates = TemplateRegistry.list_templates()
        assert "minimal" in templates
        assert "standard" in templates
        assert "agent" in templates

        # Minimal
        minimal = TemplateRegistry.get_template("minimal")
        assert ".env" in minimal
        assert "src/processes/chain.py" not in minimal # Should NOT be in minimal

        # Standard
        standard = TemplateRegistry.get_template("standard")
        assert "src/processes/chain.py" in standard

        # Agent
        agent = TemplateRegistry.get_template("agent")
        assert "src/processes/perception.py" in agent

    def test_init_project_standard(self, clean_env):
        """Verify init_project creates files for standard template."""
        target_dir = clean_env / "demo_app"
        target_dir.mkdir()
        
        init_project("demo_app", target_dir, template="standard", interactive=False)
        
        assert (target_dir / "main.py").exists()
        assert (target_dir / "src/processes/chain.py").exists()
        assert (target_dir / "specs/audit_recipe.yaml").exists()

    def test_init_project_minimal(self, clean_env):
        """Verify init_project creates files for minimal template."""
        target_dir = clean_env / "min_app"
        target_dir.mkdir()
        
        init_project("min_app", target_dir, template="minimal", interactive=False)
        
        assert (target_dir / "main.py").exists()
        # Ensure standard processes are NOT created
        assert not (target_dir / "src/processes/chain.py").exists()

    def test_init_project_agent(self, clean_env):
        """Verify init_project creates files for agent template."""
        target_dir = clean_env / "agent_app"
        target_dir.mkdir()
        
        init_project("agent_app", target_dir, template="agent", interactive=False)
        
        assert (target_dir / "src/processes/perception.py").exists()
        assert (target_dir / "src/processes/learning.py").exists()
