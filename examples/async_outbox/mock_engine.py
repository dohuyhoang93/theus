
import asyncio
import yaml
import time
import inspect

class MockTheusEngine:
    """
    A pure Python Engine logic to demonstrate coordination without Rust Bindings.
    Replicates Flux Workflow execution.
    """
    def __init__(self, context, strict_mode=False):
        self.context = context
        self.registry = {}

    def register(self, func):
        self.registry[func.__name__] = func

    async def execute_workflow(self, yaml_path):
        print(f"[MockEngine] Loading workflow: {yaml_path}")
        with open(yaml_path, 'r') as f:
            wf = yaml.safe_load(f)
            
        steps = wf.get('steps', [])
        for i, step in enumerate(steps):
            process_name = step.get('process')
            if not process_name:
                continue
                
            print(f"[MockEngine] Executing Step {i+1}: {process_name}")
            func = self.registry.get(process_name)
            if not func:
                print(f"Error: Process {process_name} not found")
                continue
                
            # Execute
            if inspect.iscoroutinefunction(func):
                await func(self.context)
            else:
                func(self.context)
                
        print("[MockEngine] Workflow Finished.")

# Helper Patch for helpers.py to work with Mock
# Since Mock passes raw context object (SimpleContext or Dict), helpers.py works if object is standard.
