
import unittest
import yaml
import os
from theus.config import ConfigFactory, ContextSchema

class TestSchemaV2(unittest.TestCase):
    def setUp(self):
        # Using the Flat Structure supported by ConfigFactory MVP
        self.schema_content = """
domain:
  user_name:
    type: string
  user_age:
    type: integer
    default: 18
"""
        self.filename = "temp_schema_test.yaml"
        with open(self.filename, "w") as f:
            f.write(self.schema_content)

    def tearDown(self):
        if os.path.exists(self.filename):
            os.remove(self.filename)

    def test_schema_loading(self):
        """Verify that ConfigFactory can parse YAML correctly."""
        schema = ConfigFactory.load_schema(self.filename)
        
        self.assertIsInstance(schema, ContextSchema)
        self.assertIn("user_age", schema.domain_fields)
        print("[TEST SCHEMA] Config Loaded Successfully.")

    def test_schema_structure(self):
        """Verify internal structure of loaded schema."""
        schema = ConfigFactory.load_schema(self.filename)
        
        field_spec = schema.domain_fields["user_age"]
        self.assertEqual(field_spec.type, "integer")
        self.assertEqual(field_spec.default, 18)
        print("[TEST SCHEMA] Structure Verified.")

if __name__ == '__main__':
    unittest.main()
