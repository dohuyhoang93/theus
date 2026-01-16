import pytest
import tempfile
from pathlib import Path
from theus.linter import run_lint, POPLinter

class TestCLILinter:
    """
    Test Suite for Theus POP Linter.
    """

    @pytest.fixture
    def clean_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_linter_clean(self, clean_dir):
        """Verify linter passes on clean code."""
        clean_code = """
from theus import process

@process
def clean_func(ctx):
    ctx.log("Allowed logging")
    a = 1 + 1
    return a
"""
        p = clean_dir / "clean.py"
        p.write_text(clean_code, encoding="utf-8")
        
        passed = run_lint(clean_dir)
        assert passed == True

    def test_linter_violations(self, clean_dir):
        """Verify linter catches violations."""
        bad_code = """
from theus import process
import requests

@process
def bad_func(ctx):
    print("Violation POP-E01")
    f = open("data.txt", "w") # Violation POP-E02
    requests.get("http://google.com") # Violation POP-E03
    global x # Violation POP-E04
"""
        p = clean_dir / "bad.py"
        p.write_text(bad_code, encoding="utf-8")
        
        passed = run_lint(clean_dir)
        assert passed == False
        
        # Parse manually to check violation count
        import ast
        tree = ast.parse(bad_code)
        linter = POPLinter(str(p))
        linter.visit(tree)
        
        codes = [v.check_id for v in linter.violations]
        assert "POP-E01" in codes # print
        assert "POP-E02" in codes # open
        assert "POP-E03" in codes # requests
        assert "POP-E04" in codes # global
