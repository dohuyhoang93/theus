import sys
import os

# Add path to find 'theus' package (parent dir)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from theus.config import ConfigFactory, RuleSpec

def test_parser():
    # User's intended YAML structure converted to dict
    data = {
        "field": "age",
        "min": 18,
        "max": 60,
        "level": "S"
    }
    
    print(f"Input Data: {data}")
    
    # Run Parser (New API)
    rules = ConfigFactory._parse_rules_from_dict(data)
    
    print(f"Parsed Rules: {rules}")
    
    # Assertions
    assert isinstance(rules, list)
    assert len(rules) == 2, "Parser should return 2 rules (min and max)"
    
    # Verify content
    conditions = {r.condition for r in rules}
    assert 'min' in conditions
    assert 'max' in conditions
    
    print("✅ SUCCESS: Parser handled both conditions correctly!")

if __name__ == "__main__":
    test_parser()
