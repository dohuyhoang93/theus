import logging
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger("FSM")

class StateMachine:
    """
    Finite State Machine for Workflow Orchestration.
    """
    def __init__(self, definition: Dict[str, Any], start_state: str = "IDLE"):
        self.states = definition.get("states", {})
        self.current_state = start_state
        self.context_data: Dict[str, Any] = {} # Transient FSM data
        
    def get_current_state(self) -> str:
        return self.current_state
    
    def trigger(self, event: str) -> List[str]:
        # print(f"DEBUG: Triggering {event} from {self.current_state}")
        state_def = self.states.get(self.current_state)
        # print(f"DEBUG: state_def for {self.current_state}: {state_def}")
        
        if not state_def:
            return []
            
        # Support 'events' (Preferred Phase 2), 'on' (Legacy), 'transitions' (Alt)
        # Fix for YAML 1.1: 'on' might be parsed as True (boolean)
        raw_on = state_def.get("on")
        if isinstance(raw_on, bool):
             logger.warning(f"⚠️ FSM Warning: 'on' key parsed as Boolean {raw_on}. Use 'events' instead.")
             raw_on = {}

        transitions = state_def.get("events") or raw_on or state_def.get("transitions") or {}
        
        next_state_name = transitions.get(event)
        if not next_state_name:
            return []
            
        logger.info(f"🔄 FSM Transition: {self.current_state} --[{event}]--> {next_state_name}")
        self.current_state = next_state_name
        
        # Get Actions (Support Single String or List of Strings)
        new_state_def = self.states.get(next_state_name, {})
        action = new_state_def.get("entry") or new_state_def.get("process")
        
        if isinstance(action, str):
            return [action]
        elif isinstance(action, list):
            return action # Already a list of strings
            
        return []
