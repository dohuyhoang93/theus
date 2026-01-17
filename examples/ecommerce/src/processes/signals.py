from theus import process
from theus.contracts import SemanticType
from theus_core import OutboxMsg

@process(inputs=[], outputs=['domain.signal_count'])
def emitter_process(ctx):
    """
    Fires signals to SignalHub.
    POP: Returns new signal count.
    """
    hub = ctx.state.signal
    
    # 2. Fire signals
    # SignalHub uses 'publish' in v3.0 (Rust binding) taking a single string
    hub.publish("tick:time=1") 
    hub.publish("alert:msg=System warning")
    
    print("Signals fired")
    current = ctx.domain.get('signal_count', 0)
    return current + 2

@process(inputs=[], outputs=['domain.received_signals'])
def listener_process(ctx):
    """
    Placeholder listener.
    """
    return []

@process(inputs=['domain.signal_count'], outputs=['domain.notified'])
def notify_user_outbox(ctx):
    """
    Adds message to Outbox.
    """
    count = ctx.domain.signal_count
    
    # Add to Outbox
    msg = OutboxMsg(topic="email", payload={"subject": "Signals Fired", "count": count})
    # FIXED: Outbox API implemented in Rust Core (ProcessContext.outbox)
    ctx.outbox.add(msg)
    
    return True
