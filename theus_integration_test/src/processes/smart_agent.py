from theus import process
from theus.contracts import SemanticType

@process(inputs=['global.time', 'domain.loop_counter'], outputs=['domain.sensor_data', 'domain.loop_counter'])
def sense_environment(ctx):
    """
    EFFECT Process: Reads global/domain, returns sensor data.
    """
    # Deterministic Loop Counter
    cnt = ctx.domain.get('loop_counter', 0)
    new_cnt = cnt + 1
    
    # Simulate reading sensor
    # Access global using getattr because 'global' is reserved 
    global_state = getattr(ctx.state, 'global')
    t = global_state.get('time', 0)
    
    if cnt < 3:
        # High Temp -> Trigger Action
        data = {"temp": 30.0, "light": 50}
    else:
        # Normal -> IDLE
        data = {"temp": 20.0, "light": 100}
    
    print(f"Sense Env: Loop {cnt}, Data {data['temp']}")
    return (data, new_cnt)

@process(inputs=['domain.sensor_data'], outputs=['domain.action'], semantic=SemanticType.PURE)
def decide_action(ctx):
    """
    PURE Process: Deterministic logic.
    CRITICAL: Validates 'RestrictedStateProxy' usage.
    """
    data = ctx.domain.sensor_data
    
    # Check Restricted View
    try:
        _ = ctx.signal # Should fail
        print("SECURITY BREACH: PURE process accessed Signal!")
        return "BREACH"
    except AttributeError:
        pass # Good
        
    # Logic
    if data['temp'] > 24:
        action = "COOL_DOWN"
    elif data['light'] < 60:
        action = "TURN_ON_LIGHTS"
    else:
        action = "IDLE"
        
    print(f"Decide Action: Input {data['temp']}")
    print(f"Decide Action: Output {action}")
    return action
