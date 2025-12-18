import pytest
from dataclasses import dataclass
from theus.zones import ContextZone, resolve_zone
from theus.context import LockedContextMixin, BaseSystemContext, BaseGlobalContext, BaseDomainContext

def test_resolve_zone():
    assert resolve_zone("user_id") == ContextZone.DATA
    assert resolve_zone("sig_start") == ContextZone.SIGNAL
    assert resolve_zone("cmd_deploy") == ContextZone.SIGNAL
    assert resolve_zone("meta_trace_id") == ContextZone.META
    assert resolve_zone("domain_data") == ContextZone.DATA

def test_context_to_dict_filtering():
    @dataclass
    class MockContext(LockedContextMixin):
        data_val: int = 1
        sig_trig: bool = True
        meta_info: str = "debug"

    ctx = MockContext()
    
    # Default: Exclude SIGNAL/META
    dump = ctx.to_dict()
    assert "data_val" in dump
    assert "sig_trig" not in dump
    assert "meta_info" not in dump
    assert dump["data_val"] == 1
    
    # Custom: Exclude nothing
    dump_all = ctx.to_dict(exclude_zones=[])
    assert "sig_trig" in dump_all
    assert "meta_info" in dump_all

def test_system_context_recursive_filtering():
    from dataclasses import dataclass
    
    @dataclass
    class MyGlobal(BaseGlobalContext):
        version: str = "1.0"
        meta_build: str = "xyz"
        
    @dataclass
    class MyDomain(BaseDomainContext):
        balance: int = 100
        sig_alert: bool = False
        
    g_ctx = MyGlobal()
    d_ctx = MyDomain()
    sys_ctx = BaseSystemContext(global_ctx=g_ctx, domain_ctx=d_ctx)
    
    dump = sys_ctx.to_dict()
    
    # Check recursion
    assert dump["global_ctx"]["version"] == "1.0"
    assert "meta_build" not in dump["global_ctx"]
    
    assert dump["domain_ctx"]["balance"] == 100
    assert "sig_alert" not in dump["domain_ctx"]
