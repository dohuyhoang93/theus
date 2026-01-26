
import pytest
import os
import shutil
import sys
from theus.engine import TheusEngine

# TDD: Auto-Discovery (scan_and_register)
# This feature scans a directory for @process decorated functions.

@pytest.fixture
def dummy_modules_dir(tmp_path):
    """Creates a temporary directory with dummy python modules."""
    d = tmp_path / "dummy_pkg"
    d.mkdir()
    
    # Module 1: Valid Process
    p1 = d / "mod_a.py"
    p1.write_text("""
from theus.contracts import process

@process(inputs=['a'], outputs=['b'])
def my_process_a(ctx):
    return 1
""")
    
    # Module 2: Invalid (No decorator)
    p2 = d / "mod_b.py"
    p2.write_text("""
def my_process_b(ctx):
    return 2
""")

    # Module 3: Nested
    sub = d / "sub"
    sub.mkdir()
    p3 = sub / "mod_c.py"
    p3.write_text("""
from theus.contracts import process

@process(inputs=['c'], outputs=['d'])
def my_process_c(ctx):
    return 3
""")
    
    return d

def test_scan_and_register_recursive(dummy_modules_dir):
    """
    Verify scan_and_register finds @process functions recursively.
    """
    engine = TheusEngine()
    
    # Run Scan
    # We pass the absolute path to the dummy dir
    print(f"Scanning: {dummy_modules_dir}")
    engine.scan_and_register(str(dummy_modules_dir))
    
    # Verify Registration
    registry = engine._registry
    print(f"Registry keys: {registry.keys()}")
    
    assert "my_process_a" in registry
    assert "my_process_c" in registry # Recursive check
    assert "my_process_b" not in registry # Should not be registered
    
    # Verify Executability (Basic)
    # Just check if callable is stored
    assert callable(registry["my_process_a"])
