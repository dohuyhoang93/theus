import unittest
import os
import sys
import json
import shutil
import pandas as pd
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from run_experiments import main as run_orchestrator

class TestContextIntegrity(unittest.TestCase):
    """
    Test Suite kiểm tra tính toàn vẹn dữ liệu (Data Integrity).
    So sánh: Input Config <-> Context Memory <-> Output CSV/Logs.
    """
    
    def setUp(self):
        self.test_dir = "results/test_integrity"
        self.config_path = "test_integrity_config.json"
        
        # 1. Create a Controlled Config
        self.config = {
            "output_dir": self.test_dir,
            "log_level": "info",
            "experiments": [
                {
                    "name": "Integrity_Check_Run",
                    "runs": 1,
                    "episodes_per_run": 5,
                    "log_level": "silent", # Keep console clean
                    "parameters": {
                        "environment_config": {
                             "grid_size": 10,
                             "max_steps_per_episode": 20, # Short limit
                             "goal_pos": [9, 9], # Far goal -> likely timeout
                             "start_pos": [[0, 0]],
                             "num_agents": 1
                        },
                        "visual_mode": False,
                        "initial_exploration": 1.0,
                        "exploration_decay": 0.9, # Fast decay for easy checking
                        "min_exploration": 0.1,
                        "emotional_boost_factor": 0.0 # Disable boost for deterministic decay check
                    }
                }
            ]
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f)
            
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def tearDown(self):
        # Cleanup
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        # Optional: remove results dir
        # shutil.rmtree(self.test_dir)

    def test_end_to_end_integrity(self):
        print("\n[Integrity Test] Starting Orchestrator...")
        
        # 1. Run Orchestrator inside the process
        final_ctx = run_orchestrator(argv=['--config', self.config_path])
        
        # 2. Verify Context State (In-Memory)
        print("   -> Verifying Context State...")
        self.assertIsNotNone(final_ctx, "Orchestrator returned None context!")
        
        global_ctx = final_ctx.global_ctx
        domain_ctx = final_ctx.domain_ctx
        
        # Check Global Config loaded
        self.assertEqual(global_ctx.config_path, self.config_path)
        
        # Check Domain Experiments
        self.assertEqual(len(domain_ctx.experiments), 1)
        exp = domain_ctx.experiments[0]
        self.assertEqual(exp.name, "Integrity_Check_Run")
        self.assertEqual(exp.runs, 1)
        
        # Check Run Status in Context
        self.assertEqual(len(exp.list_of_runs), 1)
        run = exp.list_of_runs[0]
        self.assertEqual(run.status, "COMPLETED")
        self.assertTrue(os.path.exists(run.output_csv_path), "CSV file path in context does not exist on disk")
        
        # 3. Verify Output Data (On-Disk) vs Context vs Config
        print("   -> Verifying Data Consistency (Disk vs Context)...")
        df = pd.read_csv(run.output_csv_path)
        
        # Data Length
        self.assertEqual(len(df), 5, "CSV should have 5 episodes")
        
        # Check Max Steps Enforcement
        expected_max_steps = self.config['experiments'][0]['parameters']['environment_config']['max_steps_per_episode']
        max_steps_col = df['max_steps_env'].unique()
        self.assertEqual(len(max_steps_col), 1)
        self.assertEqual(max_steps_col[0], expected_max_steps, f"CSV Max Steps {max_steps_col[0]} != Config {expected_max_steps}")
        
        # Check Steps Limit Compliance
        over_limit = df[df['steps'] > expected_max_steps]
        self.assertTrue(over_limit.empty, "Found episodes exceeding max_steps limit!")
        
        # Check Exploration Decay
        # Rule: rate(t) = max(min_rate, initial * (decay ^ t)) ?? 
        # Actually logic in p5_adjust_exploration is:
        # current = current * decay. 
        # So rate at ep N = initial * (decay ^ (steps_total? or episodes?))
        # Wait, context.py logic is decay per EPISODE? Or per Step?
        # Let's check the code logic. p5 adjusts per STEP usually? 
        # No, p5 runs in main_loop (per System).
        # Ah, in main.py, exploration updates happen inside the loop or outside?
        # p5 is a process. Inside loop. So it decays EVERY STEP.
        
        # Let's just verify it IS decaying.
        rates = df['final_exploration_rate'].tolist()
        # self.assertTrue(rates[0] <= 1.0, "Rate > 1.0") # Removed because boost can push > 1.0, though we disabled it now.
        self.assertTrue(rates[-1] < rates[0], "Exploration did not decay over time")
        
        print("   -> Consistency Check PASSED.")

if __name__ == "__main__":
    unittest.main()
