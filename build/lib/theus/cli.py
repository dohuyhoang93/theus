import argparse
import os
import sys
import yaml
import ast
import inspect
from pathlib import Path
from .templates import (
    TEMPLATE_ENV, 
    TEMPLATE_MAIN, 
    TEMPLATE_CONTEXT, 
    TEMPLATE_WORKFLOW, 
    TEMPLATE_PROCESS_CHAIN,
    TEMPLATE_PROCESS_STRESS,
    TEMPLATE_AUDIT_RECIPE
)
from .config import ConfigFactory

def init_project(project_name: str, target_dir: Path):
    """
    Scaffolds a new Theus project.
    """
    print(f"🚀 Initializing Theus Project: {project_name}")
    
    # 1. Create Directories
    try:
        (target_dir / "src" / "processes").mkdir(parents=True, exist_ok=True)
        (target_dir / "workflows").mkdir(parents=True, exist_ok=True)
        (target_dir / "specs").mkdir(parents=True, exist_ok=True) # New V2 folder
    except OSError as e:
        print(f"❌ Error creating directories: {e}")
        sys.exit(1)

    # 2. Write Files
    files_to_create = {
        ".env": TEMPLATE_ENV,
        "main.py": TEMPLATE_MAIN,
        "src/context.py": TEMPLATE_CONTEXT,
        "src/__init__.py": "",
        "src/processes/__init__.py": "",
        "src/processes/chain.py": TEMPLATE_PROCESS_CHAIN,
        "src/processes/stress.py": TEMPLATE_PROCESS_STRESS,
        "specs/workflow.yaml": TEMPLATE_WORKFLOW,
        "specs/context_schema.yaml": "# Define your Data Contract here\n",
        "specs/audit_recipe.yaml": TEMPLATE_AUDIT_RECIPE
    }

    for rel_path, content in files_to_create.items():
        file_path = target_dir / rel_path
        if file_path.exists():
            print(f"   ⚠️  Skipping existing file: {rel_path}")
            continue
            
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"   ✅ Created {rel_path}")

    print("\n🎉 Project created successfully!")
    print("\nNext steps:")
    if project_name != ".":
        print(f"  cd {project_name}")
    print("  pip install -r requirements.txt (if you have one)")
    print("  python main.py")

def gen_spec(target_dir: Path = Path.cwd()):
    """
    Scans src/processes/*.py and generates missing rules in specs/audit_recipe.yaml
    """
    print("🔍 Scanning processes for Audit Spec generation...")
    processes_dir = target_dir / "src" / "processes"
    recipe_path = target_dir / "specs" / "audit_recipe.yaml"
    
    if not processes_dir.exists():
        print(f"❌ Processes directory not found: {processes_dir}")
        return

    # 1. Parse Python Files
    discovered_recipes = {}
    
    for py_file in processes_dir.glob("*.py"):
        if py_file.name.startswith("__"): continue
        
        with open(py_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
            
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check for @process decorator
                is_process = any(
                    (isinstance(d, ast.Call) and getattr(d.func, 'id', '') == 'process') 
                    or (isinstance(d, ast.Name) and d.id == 'process')
                    for d in node.decorator_list
                )
                
                if is_process:
                    # Extracts inputs/outputs/side_effects/errors from decorator
                    skeleton = {
                        "inputs": [{"field": "TODO_FIELD", "level": "I", "min": 0}], # Default: Ignore until configured
                        "outputs": [{"field": "TODO_FIELD", "level": "I", "threshold": 3}],
                        "side_effects": [], # New V2 Feature
                        "errors": []        # New V2 Feature
                    }

                    # Heuristic: Parse Decorator Kwargs
                    for d in node.decorator_list:
                        if isinstance(d, ast.Call) and getattr(d.func, 'id', '') == 'process':
                            for kw in d.keywords:
                                if kw.arg in ('inputs', 'outputs'):
                                    # We keep the generic TODO skeleton for I/O rules as they are complex rule objects
                                    pass
                                elif kw.arg == 'side_effects':
                                    try:
                                        skeleton['side_effects'] = ast.literal_eval(kw.value)
                                    except:
                                        skeleton['side_effects'] = ["__DYNAMIC__"]
                                elif kw.arg == 'errors':
                                    try:
                                        skeleton['errors'] = ast.literal_eval(kw.value)
                                    except:
                                        skeleton['errors'] = ["__DYNAMIC__"]

                    process_name = node.name
                    discovered_recipes[process_name] = skeleton
                    print(f"   found process: {process_name}")

    if not discovered_recipes:
        print("⚠️ No processes found.")
        return

    # 2. Merge with existing YAML
    existing_data = {}
    if recipe_path.exists():
        with open(recipe_path, 'r') as f:
            existing_data = yaml.safe_load(f) or {}

    if 'process_recipes' not in existing_data:
        existing_data['process_recipes'] = {}

    changes_made = False
    for name, skeleton in discovered_recipes.items():
        if name not in existing_data['process_recipes']:
            existing_data['process_recipes'][name] = skeleton
            changes_made = True
            print(f"   ➕ Added skeleton for {name}")

    if changes_made:
        with open(recipe_path, 'w', encoding='utf-8') as f:
            yaml.dump(existing_data, f, sort_keys=False)
        print(f"✅ Updated {recipe_path}")
    else:
        print("✨ No new processes to add.")

def inspect_process(process_name: str, target_dir: Path = Path.cwd()):
    """
    Displays the effective audit rules for a process.
    """
    recipe_path = target_dir / "specs" / "audit_recipe.yaml"
    if not recipe_path.exists():
        print(f"❌ No audit recipe found at {recipe_path}")
        return

    try:
        recipe_book = ConfigFactory.load_recipe(str(recipe_path))
        recipe = recipe_book.definitions.get(process_name)
        
        if not recipe:
            print(f"❌ Process '{process_name}' not found in Audit Recipe.")
            return
            
        print(f"\\n🔍 Audit Inspector: {process_name}")
        print("-----------------------------------")
        
        print(f"📥 INPUTS ({len(recipe.input_rules)} Rules):")
        for r in recipe.input_rules:
            print(f"   - {r.target_field}: {r.condition} {r.value} [Level: {r.level}]")
            
        print(f"\\n📤 OUTPUTS ({len(recipe.output_rules)} Rules):")
        for r in recipe.output_rules:
            print(f"   - {r.target_field}: {r.condition} {r.value} [Level: {r.level}]")

        print(f"\\n⚡ SIDE EFFECTS:")
        if recipe.side_effects:
            for s in recipe.side_effects:
                print(f"   - {s}")
        else:
            print("   (None declared)")

        print(f"\\n🚫 EXPECTED ERRORS:")
        if recipe.errors:
            for e in recipe.errors:
                print(f"   - {e}")
        else:
            print("   (None declared)")
            
    except Exception as e:
        print(f"❌ Error loading recipe: {e}")

def main():
    parser = argparse.ArgumentParser(description="Theus SDK CLI - Manage your Process-Oriented projects.")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: init
    parser_init = subparsers.add_parser("init", help="Initialize a new Theus project.")
    parser_init.add_argument("name", help="Name of the project (or '.' for current directory).")

    # Command: audit
    parser_audit = subparsers.add_parser("audit", help="Audit tools.")
    audit_subs = parser_audit.add_subparsers(dest="audit_command")
    
    # audit gen-spec
    parser_gen = audit_subs.add_parser("gen-spec", help="Generate/Update audit_recipe.yaml from code.")

    # audit inspect
    parser_inspect = audit_subs.add_parser("inspect", help="Inspect effective rules for a process.")
    parser_inspect.add_argument("process_name", help="Name of the process to inspect.")

    # Command: schema (New V2 Tool)
    parser_schema = subparsers.add_parser("schema", help="Data Schema tools.")
    schema_subs = parser_schema.add_subparsers(dest="schema_command")
    
    # schema gen
    parser_schema_gen = schema_subs.add_parser("gen", help="Generate context_schema.yaml from Python Definitions.")
    parser_schema_gen.add_argument("--context-file", default="src/context.py", help="Path to Python context definition (default: src/context.py)")

    # schema code
    parser_schema_code = schema_subs.add_parser("code", help="Generate src/context.py from YAML Schema.")
    parser_schema_code.add_argument("--schema-file", default="specs/context_schema.yaml", help="Path to YAML schema (default: specs/context_schema.yaml)")
    parser_schema_code.add_argument("--out-file", default="src/context.py", help="Output Python file path (default: src/context.py)")

    args = parser.parse_args()

    if args.command == "init":
        project_name = args.name
        
        if project_name == ".":
            target_path = Path.cwd()
            project_name = target_path.name
        else:
            target_path = Path.cwd() / project_name
            if target_path.exists() and any(target_path.iterdir()):
                print(f"❌ Directory '{project_name}' exists and is not empty.")
                sys.exit(1)
            target_path.mkdir(exist_ok=True)
            
        init_project(project_name, target_path)
        
    elif args.command == "audit":
        if args.audit_command == "gen-spec":
            gen_spec()
        elif args.audit_command == "inspect":
            inspect_process(args.process_name)
            
    elif args.command == "schema":
        if args.schema_command == "gen":
            from .schema_gen import generate_schema_from_file
            print(f"🔍 Scanning context definition: {args.context_file}")
            try:
                schema_dict = generate_schema_from_file(args.context_file)
                output_path = Path("specs/context_schema.yaml")
                output_path.parent.mkdir(exist_ok=True)
                
                with open(output_path, "w", encoding="utf-8") as f:
                    yaml.dump(schema_dict, f, sort_keys=False)
                    
                print(f"✅ Generated schema at: {output_path}")
                print(yaml.dump(schema_dict, sort_keys=False))
                
            except Exception as e:
                print(f"❌ Failed to generate schema: {e}")

        elif args.schema_command == "code":
            from .schema_gen import generate_code_from_schema
            print(f"🏗️  Generating Context Code from: {args.schema_file}")
            try:
                code_content = generate_code_from_schema(args.schema_file)
                output_path = Path(args.out_file)
                output_path.parent.mkdir(exist_ok=True)
                
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(code_content)
                    
                print(f"✅ Generated Python Context at: {output_path}")
                
            except Exception as e:
                print(f"❌ Failed to generate code: {e}")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
