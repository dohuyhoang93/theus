
import unittest
import shutil
import tempfile
import os
from pathlib import Path
from theus.cli import init_project, gen_spec
import yaml

class TestCLIV2(unittest.TestCase):
    def setUp(self):
        # Create a temp directory for each test
        self.test_dir = Path(tempfile.mkdtemp())
        self.project_name = "test_project"
        self.project_dir = self.test_dir / self.project_name
        self.project_dir.mkdir()

    def tearDown(self):
        # Cleanup
        shutil.rmtree(self.test_dir)

    def test_init_project(self):
        """Verify scaffolding creates expected files."""
        init_project(self.project_name, self.project_dir)
        
        expected_files = [
            "src/processes/chain.py",
            "specs/workflow.yaml",
            "specs/context_schema.yaml",
            "src/context.py"
        ]
        
        for f in expected_files:
            self.assertTrue((self.project_dir / f).exists(), f"Missing {f}")
        print("[TEST CLI] Init Project Success.")

    def test_gen_spec(self):
        """Verify gen-spec scans python files and updates yaml."""
        # 1. Setup scaffolding
        init_project(self.project_name, self.project_dir)
        
        # 2. Create a dummy process file
        process_code = """
from theus.process import process

@process(inputs=['a'], outputs=['b'])
def my_process(ctx):
    pass
"""
        with open(self.project_dir / "src/processes/p_dummy.py", "w") as f:
            f.write(process_code)
            
        # 3. Run gen_spec
        gen_spec(target_dir=self.project_dir)
        
        # 4. Check yaml
        recipe_path = self.project_dir / "specs/audit_recipe.yaml"
        self.assertTrue(recipe_path.exists())
        
        with open(recipe_path, 'r') as f:
            data = yaml.safe_load(f)
            
        self.assertIn("process_recipes", data)
        self.assertIn("my_process", data["process_recipes"])
        print("[TEST CLI] Gen Spec Success.")

if __name__ == '__main__':
    unittest.main()
