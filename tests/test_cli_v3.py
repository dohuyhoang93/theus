import os
import shutil
import pytest
from pathlib import Path
from theus.cli import init_project

class TestCLI_v3:
    """
    Test Suite for Theus v3.1 CLI Enhancements.
    Refactored to support Universal Scaffold (TemplateRegistry removed).
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

    def test_init_project_universal(self, clean_env):
        """Verify init_project creates files from Universal Scaffold."""
        target_dir = clean_env / "demo_app"
        target_dir.mkdir()
        
        # New CLI does not use template arg, so we pass None or ignore it
        init_project("demo_app", target_dir)
        
        # Verify Core Files
        assert (target_dir / "main.py").exists()
        assert (target_dir / "requirements.txt").exists()
        assert (target_dir / ".env").exists()
        
        # Verify Processes (Universal Scaffold)
        assert (target_dir / "src/processes/ecommerce.py").exists()
        assert (target_dir / "src/processes/async_outbox.py").exists()
        assert (target_dir / "src/processes/parallel.py").exists()
        
        # Verify Specs
        assert (target_dir / "specs/audit_recipe.yaml").exists()

