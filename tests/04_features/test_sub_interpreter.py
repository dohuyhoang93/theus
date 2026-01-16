import pytest
import sys

# TDD: Check environment for Sub-Interpreter support (Python 3.12+)

def test_python_version_for_sub_interpreters():
    # Just a check to see if we can enable this feature
    # Theus v3 checks this at startup
    major, minor = sys.version_info[:2]
    if major == 3 and minor >= 12:
        assert True 
    else:
        pytest.skip("Sub-Interpreters require Python 3.12+")

def test_interpreters_module_exists():
    try:
        import _xxsubinterpreters
    except ImportError:
        pytest.skip("_xxsubinterpreters not available")
