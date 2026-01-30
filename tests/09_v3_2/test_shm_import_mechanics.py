import pytest
import sys

def test_shm_module_existence():
    """
    Verify that theus_core exports 'shm' submodule correctly.
    """
    import theus_core
    assert hasattr(theus_core, "shm"), "theus_core MUST have 'shm' attribute"

def test_shm_import_pattern():
    """
    Verify correct import pattern for PyO3 submodules.
    Standard 'from A.B import C' fails for monolithic extensions.
    The correct pattern is 'from A import B; C = B.C'.
    """
    # 1. This is the pattern we fixed
    from theus_core import shm
    assert shm is not None
    
    # 2. Verify Registry exists
    assert hasattr(shm, "MemoryRegistry"), "shm module MUST have MemoryRegistry class"
    
    # 3. Verify it is a class
    Registry = shm.MemoryRegistry
    assert isinstance(Registry, type), "MemoryRegistry SHOULD be a class type"

def test_memory_registry_init():
    """
    Verify MemoryRegistry can be instantiated.
    """
    from theus_core import shm
    Registry = shm.MemoryRegistry
    
    # Init with session ID
    session_id = "test_session_unit"
    reg = Registry(session_id)
    assert reg is not None
    
    # Verify method call (if visible)
    # Rust impl might not expose methods to Python public unless registered
    # But init proving it works is enough for 'Import' test.

def test_managed_allocator_integration():
    """
    Verify ManagedAllocator correctly imports it (System Integration).
    """
    from theus.structures import ManagedAllocator
    
    # Should not print WARNING
    alloc = ManagedAllocator(capacity_mb=1, session_id="test_integ")
    assert alloc._registry is not None, "ManagedAllocator SHOULD have registry initialized"
