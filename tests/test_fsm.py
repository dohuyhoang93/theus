from theus.orchestrator.fsm import StateMachine

def test_fsm_transition_logic():
    definition = {
        "states": {
            "IDLE": {
                "on": {
                    "CMD_START": "WORKING_STATE" # Transition to WORKING_STATE
                }
            },
            "WORKING_STATE": {
                "entry": "p_do_heavy_work", # Action to run upon entry
                "on": {
                    "EVT_DONE": "IDLE"
                }
            }
        }
    }
    
    fsm = StateMachine(definition, start_state="IDLE")
    
    # 1. Initial
    assert fsm.get_current_state() == "IDLE"
    
    # 2. Trigger START
    action = fsm.trigger("CMD_START")
    
    # Expect: State updated, Action returned
    assert fsm.get_current_state() == "WORKING_STATE"
    assert action == ["p_do_heavy_work"]
    
    # 3. Trigger DONE
    action2 = fsm.trigger("EVT_DONE")
    
    assert fsm.get_current_state() == "IDLE"
    assert action2 == [] # IDLE has no entry action defined
