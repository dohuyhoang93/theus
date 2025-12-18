import logging
import time
from typing import Optional, Dict

from ..interfaces import IEngine, IScheduler, IOrchestrator
from .bus import SignalBus
from .fsm import StateMachine

logger = logging.getLogger("WorkflowManager")

class WorkflowManager(IOrchestrator):
    """
    The Conductor.
    Connects: SignalBus (Ear) -> FSM (Brain) -> ThreadExecutor (Hand) -> Engine (Tool).
    """
    def __init__(self, engine: IEngine, scheduler: IScheduler, bus: SignalBus):
        self.engine = engine
        self.scheduler = scheduler
        self.bus = bus
        self.fsm: Optional[StateMachine] = None
        self._running = False

    def load_workflow(self, workflow_def: Dict):
        """Load FSM definition."""
        self.fsm = StateMachine(workflow_def)
        logger.info(f"Workflow Loaded. Start State: {self.fsm.get_current_state()}")

    def run_workflow(self, workflow_name: str, context: object) -> None:
        """
        Start the workflow loop. 
        NOTE: This is usually BLOCKING if called directly.
        For GUI, you should call `process_signals()` periodically in the GUI loop,
        instead of calling this `run_workflow` loop.
        """
        logger.info(f"Starting Workflow Loop for '{workflow_name}'")
        self._running = True
        while self._running:
            try:
                # 1. Listen for Events
                signal = self.bus.get(timeout=0.1) # Non-blocking wait
                if signal:
                    self.process_signal(signal)
                
                # 2. Check for App Exit? (Optional)
            except KeyboardInterrupt:
                self.stop()
                
    def process_signal(self, signal: str):
        """
        Core Reactive Logic.
        """
        if not self.fsm:
            logger.warning("Signal received but no FSM loaded.")
            return

        # Ask Brain (FSM) what to do
        actions = self.fsm.trigger(signal)
        
        if actions:
            logger.info(f"🚀 Dispatching Chain: {actions}")
            
            # Define a Chain Runner to execute sequentially in the Thread
            def chain_runner():
                results = []
                for idx, process_name in enumerate(actions):
                    logger.info(f"   ► Step {idx+1}/{len(actions)}: {process_name}")
                    # If this fails, exception propagates and stops chain
                    res = self.engine.execute_process(process_name)
                    results.append(res)
                return results

            # Execute the Chain in Background
            future = self.scheduler.submit(chain_runner)
            
            # Optional: Add done callback for chain completion
            def on_done(f):
                try:
                    f.result() # Check for chain failure
                    # Auto-Transition: Emit EVT_CHAIN_DONE
                    self.bus.emit("EVT_CHAIN_DONE") 
                except Exception as e:
                    logger.error(f"Chain Failed: {e}")
                    self.bus.emit("EVT_CHAIN_FAIL")
            
            future.add_done_callback(on_done)

    def stop(self):
        self._running = False
        self.scheduler.shutdown(wait=False)
