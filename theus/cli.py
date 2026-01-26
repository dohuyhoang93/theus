import argparse
import sys
import yaml
import ast
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import questionary

import shutil
import os

# from .templates.registry import TemplateRegistry # DEPRECATED
from .config import ConfigFactory

console = Console()

def init_project(project_name: str, target_dir: Path):
    """
    Scaffolds a new Theus project using the bundled universal scaffold.
    """
    console.print(f"[bold green]🚀 Initializing Theus Project: {project_name}[/bold green]")
    
    # Locate Scaffold Directory (bundled with package)
    pkg_dir = Path(os.path.dirname(__file__))
    scaffold_dir = pkg_dir / "scaffold"
    
    if not scaffold_dir.exists():
        console.print(f"[bold red]❌ Critical Error: Scaffold directory not found at {scaffold_dir}[/bold red]")
        console.print("   Please ensure 'theus' is installed correctly with package data.")
        sys.exit(1)

    # Copy Tree
    try:
        shutil.copytree(scaffold_dir, target_dir, dirs_exist_ok=True)
        console.print(f"   [green]✅ Copied project skeleton from {scaffold_dir}[/green]")
    except Exception as e:
        console.print(f"[bold red]❌ Error copying scaffold: {e}[/bold red]")
        sys.exit(1)

    console.print("\n[bold blue]🎉 Project created successfully! (Universal Template)[/bold blue]")
    console.print("\nNext steps:")
    if project_name != ".":
        console.print(f"  cd {project_name}")
    console.print("  pip install -r requirements.txt")
    console.print("  python main.py")

def gen_spec(target_dir: Path = Path.cwd()):
    """
    Scans src/processes/*.py and generates missing rules in specs/audit_recipe.yaml
    """
    console.print("[cyan]🔍 Scanning processes for Audit Spec generation...[/cyan]")
    processes_dir = target_dir / "src" / "processes"
    recipe_path = target_dir / "specs" / "audit_recipe.yaml"
    
    if not processes_dir.exists():
        console.print(f"[bold red]❌ Processes directory not found: {processes_dir}[/bold red]")
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
                    console.print(f"   found process: [bold]{process_name}[/bold]")

    if not discovered_recipes:
        console.print("[yellow]⚠️ No processes found.[/yellow]")
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
            console.print(f"   [green]➕ Added skeleton for {name}[/green]")

    if changes_made:
        with open(recipe_path, 'w', encoding='utf-8') as f:
            yaml.dump(existing_data, f, sort_keys=False)
        console.print(f"[green]✅ Updated {recipe_path}[/green]")
    else:
        console.print("✨ No new processes to add.")

def inspect_process(process_name: str, target_dir: Path = Path.cwd()):
    """
    Displays the effective audit rules for a process using Rich Tables.
    """
    recipe_path = target_dir / "specs" / "audit_recipe.yaml"
    if not recipe_path.exists():
        console.print(f"[bold red]❌ No audit recipe found at {recipe_path}[/bold red]")
        return

    try:
        recipe_book = ConfigFactory.load_recipe(str(recipe_path))
        recipe = recipe_book.definitions.get(process_name)
        
        if not recipe:
            console.print(f"[bold red]❌ Process '{process_name}' not found in Audit Recipe.[/bold red]")
            return
            
        console.print(Panel(f"[bold cyan]🔍 Audit Inspector: {process_name}[/bold cyan]"))
        
        def _get_condition_str(rule):
            # Helper to format condition from dict
            conds = []
            for k, v in rule.items():
                if k in ('field', 'level', 'message', 'min_threshold', 'max_threshold', 'reset_on_success'): continue
                conds.append(f"{k}={v}")
            return ", ".join(conds)

        # Inputs Table
        table_in = Table(title="📥 INPUTS", show_lines=True)
        table_in.add_column("Field", style="cyan")
        table_in.add_column("Condition", style="magenta")
        table_in.add_column("Level", style="yellow")
        
        for r in recipe.get('inputs', []):
            field = r.get('field', 'Unknown')
            cond = _get_condition_str(r)
            level = r.get('level', 'I')
            table_in.add_row(field, cond, str(level))
        console.print(table_in)
            
        # Outputs Table
        table_out = Table(title="📤 OUTPUTS", show_lines=True)
        table_out.add_column("Field", style="cyan")
        table_out.add_column("Condition", style="magenta")
        table_out.add_column("Level", style="yellow")
        
        for r in recipe.get('outputs', []):
            field = r.get('field', 'Unknown')
            cond = _get_condition_str(r)
            level = r.get('level', 'I')
            table_out.add_row(field, cond, str(level))
        console.print(table_out)

        console.print("\n[bold]⚡ SIDE EFFECTS:[/bold]")
        side_effects = recipe.get('side_effects', [])
        if side_effects:
            for s in side_effects:
                console.print(f"   - {s}")
        else:
            console.print("   (None declared)")

        console.print("\n[bold]🚫 EXPECTED ERRORS:[/bold]")
        errors = recipe.get('errors', [])
        if errors:
            for e in errors:
                console.print(f"   - {e}")
        else:
            console.print("   (None declared)")
            
    except Exception as e:
        console.print(f"[bold red]❌ Error loading recipe: {e}[/bold red]")

def main():
    parser = argparse.ArgumentParser(description="Theus SDK CLI - Manage your Process-Oriented projects.")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: init
    parser_init = subparsers.add_parser("init", help="Initialize a new Theus project.")
    parser_init.add_argument("name", nargs="?", help="Name of the project (optional for interactive).")
    parser_init.add_argument("--template", help="Template to use (minimal, standard, agent).")
    parser_init.add_argument("--quiet", action="store_true", help="Non-interactive mode.")

    # Command: check (New V3.1)
    parser_check = subparsers.add_parser("check", help="Run POP Static Analysis (Linter).")
    parser_check.add_argument("target", nargs="?", default=".", help="Directory to check.")
    parser_check.add_argument("--format", choices=["table", "json"], default="table", help="Output format (default: table).")

    # Command: audit
    parser_audit = subparsers.add_parser("audit", help="Audit tools.")
    audit_subs = parser_audit.add_subparsers(dest="audit_command")
    
    # audit gen-spec
    parser_gen = audit_subs.add_parser("gen-spec", help="Generate/Update audit_recipe.yaml from code.")

    # audit inspect
    parser_inspect = audit_subs.add_parser("inspect", help="Inspect effective rules for a process.")
    parser_inspect.add_argument("process_name", help="Name of the process to inspect.")

    # Command: schema
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
        # Interactive Mode Logic
        if not args.name and not args.quiet:
            args.name = questionary.text("Project Name:", default="my-theus-app").ask()
        
        project_name = args.name or "."
        
        # Template selection removed (Universal only)
        
        if project_name == ".":
            target_path = Path.cwd()
            project_name = target_path.name
        else:
            target_path = Path.cwd() / project_name
            if target_path.exists() and any(target_path.iterdir()):
                console.print(f"[bold red]❌ Directory '{project_name}' exists and is not empty.[/bold red]")
                sys.exit(1)
            target_path.mkdir(exist_ok=True)
            
        init_project(project_name, target_path)
    
    elif args.command == "check":
        from .linter import run_lint
        target = Path(args.target)
        if not target.exists():
             console.print(f"[bold red]❌ Target path does not exist: {target}[/bold red]")
             sys.exit(1)
        success = run_lint(target, output_format=args.format)
        if not success:
            sys.exit(1)
        
    elif args.command == "audit":
        if args.audit_command == "gen-spec":
            gen_spec()
        elif args.audit_command == "inspect":
            inspect_process(args.process_name)
            
    elif args.command == "schema":
        if args.schema_command == "gen":
            from .schema_gen import generate_schema_from_file
            console.print(f"[cyan]🔍 Scanning context definition: {args.context_file}[/cyan]")
            try:
                schema_dict = generate_schema_from_file(args.context_file)
                output_path = Path("specs/context_schema.yaml")
                output_path.parent.mkdir(exist_ok=True)
                
                with open(output_path, "w", encoding="utf-8") as f:
                    yaml.dump(schema_dict, f, sort_keys=False)
                    
                console.print(f"[green]✅ Generated schema at: {output_path}[/green]")
                console.print(yaml.dump(schema_dict, sort_keys=False))
                
            except Exception as e:
                console.print(f"[bold red]❌ Failed to generate schema: {e}[/bold red]")

        elif args.schema_command == "code":
            from .schema_gen import generate_code_from_schema
            console.print(f"[cyan]🏗️  Generating Context Code from: {args.schema_file}[/cyan]")
            try:
                code_content = generate_code_from_schema(args.schema_file)
                output_path = Path(args.out_file)
                output_path.parent.mkdir(exist_ok=True)
                
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(code_content)
                    
                console.print(f"[green]✅ Generated Python Context at: {output_path}[/green]")
                
            except Exception as e:
                console.print(f"[bold red]❌ Failed to generate code: {e}[/bold red]")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
