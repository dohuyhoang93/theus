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
        
        # Check Run Status in Context (Deprecated check, checking Disk instead)
        # self.assertEqual(len(exp.list_of_runs), 1)

        # 3. Verify Output Data (On-Disk) vs Context vs Config
        print("   -> Verifying Data Consistency (Disk vs Context)...")
        
        # New V2 Path: results/{exp_name}_checkpoints/metrics.json
        run_dir = os.path.join(self.test_dir, f"{exp.name}_checkpoints")
        metrics_path = os.path.join(run_dir, "metrics.json")
        
        self.assertTrue(os.path.exists(metrics_path), f"Metrics file not found: {metrics_path}")
        
        with open(metrics_path, 'r') as f:
            data = json.load(f)
            
        # Data Length
        self.assertEqual(len(data), 5, "Metrics JSON should have 5 episodes")
        
        # Check Max Steps Enforcement
        expected_max_steps = self.config['experiments'][0]['parameters']['environment_config']['max_steps_per_episode']
        
        # Extract max steps from first episode input_config if recorded, or checking lengths if available
        # The metrics might include 'max_steps_env'.
        # Let's check first entry structure
        first_ep = data[0]['metrics']
        # If max_steps_env is recorded in metrics
        if 'max_steps_env' in first_ep:
            max_steps_val = first_ep['max_steps_env']
            self.assertEqual(max_steps_val, expected_max_steps, f"Metrics Max Steps {max_steps_val} != Config {expected_max_steps}")
        
        # Check Steps Limit Compliance
        for ep_entry in data:
            steps = ep_entry['metrics'].get('steps', 0)
            self.assertLessEqual(steps, expected_max_steps, f"Episode steps {steps} exceeded max {expected_max_steps}")

        # Check Exploration Decay
        rates = [ep['metrics'].get('final_exploration_rate', 0) for ep in data]
        if len(rates) > 1:
            self.assertTrue(rates[-1] <= rates[0], "Exploration did not decay (or stayed same) over time")
            # Note: with strict decay 0.9, it should be strictly less unless stopped immediately
        
        print("   -> Consistency Check PASSED.")

if __name__ == "__main__":
    unittest.main()
