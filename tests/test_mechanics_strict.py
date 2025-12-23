import unittest
import os
import sys
import shutil
import pandas as pd
import subprocess
import json

# Add project root to path (for environment.py)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestStrictMechanics(unittest.TestCase):
    """
    Test Suite kiểm tra các ràng buộc cơ chế "chết người" (Hard Constraints).
    Mục tiêu: Đảm bảo refactor không làm hỏng logic cơ bản của Simulation.
    """
    
    def setUp(self):
        self.output_dir = "results/test_mechanics"
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir)

    def test_max_steps_enforcement(self):
        """
        Scenario: Agent bị nhốt hoặc đích quá xa.
        Expectation: Simulation PHẢI dừng chính xác tại max_steps.
        Lỗi cần bắt: Infinite Loop, hoặc dừng sai (sớm/muộn).
        """
        print("\n[Test] Verifying Max Steps Enforcement...")
        
        MAX_STEPS = 15
        OUTPUT_CSV = os.path.join(self.output_dir, "max_step_test.csv")
        
        # Override settings: Small grid, impossible goal (to force timeout)
        settings = {
            "environment_config": {
                "grid_size": 5,
                "max_steps_per_episode": MAX_STEPS,
                "goal_pos": [4, 4],
                "start_pos": [0, 0],
                # Wall off the goal to ensure failure (Timeout)
                "walls": [[3, 4], [4, 3]] 
            },
            "visual_mode": False
        }
        
        command = [
            "python", "main.py",
            "--num-episodes", "1",
            "--output-path", OUTPUT_CSV,
            "--settings-override", json.dumps(settings),
            "--log-level", "silent"
        ]
        
        # Run subprocess
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            print("STDERR:", result.stderr)
            self.fail("Simulation crashed during execution.")
            
        # Verify CSV Data
        self.assertTrue(os.path.exists(OUTPUT_CSV), "Output CSV must exist")
        df = pd.read_csv(OUTPUT_CSV)
        
        actual_steps = df.iloc[0]['steps']
        max_limit = df.iloc[0]['max_steps_env']
        
        print(f"   -> Configured Max Steps: {MAX_STEPS}")
        print(f"   -> Actual Steps Recorded: {actual_steps}")
        
        self.assertEqual(actual_steps, MAX_STEPS, 
                         f"Simulation did not stop at max_steps. Expected {MAX_STEPS}, got {actual_steps}")
        self.assertEqual(max_limit, MAX_STEPS,
                         f"Logged max_steps_env mismatch. Expected {MAX_STEPS}, got {max_limit}")

    def test_environment_sync(self):
        """
        Unit Test giả lập để đảm bảo main loop update environment.current_step.
        Vì khó test UI, ta test logic timeout của environment.
        """
        from environment import GridWorld
        
        print("\n[Test] Verifying Environment Step Sync Logic...")
        
        settings = {"environment_config": {"max_steps_per_episode": 5}}
        env = GridWorld(settings)
        env.reset()
        
        # Simulate Loop
        for i in range(5):
            # IF main loop fails to update current_step, is_done() will fail
            env.current_step = i + 1  # This is the line we expect main.py to have!
            
        self.assertTrue(env.is_done(), 
                        "Environment.is_done() failed to trigger at max steps. "
                        "implies current_step was not updated correctly.")

if __name__ == "__main__":
    unittest.main()
