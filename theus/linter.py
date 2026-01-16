import ast
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table

console = Console()

class EffectViolation:
    def __init__(self, file: str, line: int, check_id: str, message: str, severity: str = "ERROR"):
        self.file = file
        self.line = line
        self.check_id = check_id
        self.message = message
        self.severity = severity

class POPLinter(ast.NodeVisitor):
    """
    Process-Oriented Programming Linter.
    Enforces rules:
    - POP-E01: No print() statements (Use logging).
    - POP-E02: No open() calls (Use Context/Outbox).
    - POP-E03: No network calls (requests, urllib) (Use Outbox).
    - POP-E04: No Global State mutation (global keyword).
    """
    
    def __init__(self, filename: str):
        self.filename = filename
        self.violations: List[EffectViolation] = []
        self.in_process = False

    def visit_FunctionDef(self, node):
        # Check if function is a Process (decorated with @process)
        is_process = any(
            (isinstance(d, ast.Call) and getattr(d.func, 'id', '') == 'process') 
            or (isinstance(d, ast.Name) and d.id == 'process')
            for d in node.decorator_list
        )
        
        prev_in_process = self.in_process
        if is_process:
            self.in_process = True
            
        self.generic_visit(node)
        self.in_process = prev_in_process

    def visit_Call(self, node):
        # Effect Check logic
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name == 'print':
                self.violations.append(EffectViolation(
                    self.filename, node.lineno, "POP-E01", 
                    "Avoid 'print()'. Use 'logging' or 'ctx.log()'."
                ))
            elif func_name == 'open':
                self.violations.append(EffectViolation(
                    self.filename, node.lineno, "POP-E02", 
                    "Direct file I/O 'open()' is forbidden. Use Context or Outbox."
                ))
        
        # Check for banned modules calls (e.g. requests.get)
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                module_name = node.func.value.id
                method_name = node.func.attr
                if module_name in ['requests', 'urllib', 'http']:
                    self.violations.append(EffectViolation(
                        self.filename, node.lineno, "POP-E03", 
                        f"Network call '{module_name}.{method_name}' forbidden. Use Outbox."
                    ))

        self.generic_visit(node)

    def visit_Global(self, node):
        self.violations.append(EffectViolation(
            self.filename, node.lineno, "POP-E04", 
            "Usage of 'global' keyword is strictly forbidden in POP architecture."
        ))

def run_lint(target_dir: Path) -> bool:
    """
    Runs linter on all .py files in src/processes and src/
    Returns True if passed, False if violations found.
    """
    all_violations = []
    
    console.print(f"[cyan]🔍 Running POP Linter Check on {target_dir}...[/cyan]")
    
    for py_file in target_dir.rglob("*.py"):
        if "tests" in str(py_file) or "site-packages" in str(py_file):
            continue
            
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
            
            linter = POPLinter(str(py_file))
            linter.visit(tree)
            all_violations.extend(linter.violations)
        except Exception as e:
            console.print(f"[yellow]⚠️ Could not parse {py_file}: {e}[/yellow]")

    if not all_violations:
        console.print("[bold green]✅ No violations found. POP Compliance: 100%[/bold green]")
        return True
    
    # Report Violations
    table = Table(title="🚨 Linter Violations", show_lines=True)
    table.add_column("Location", style="cyan")
    table.add_column("Code", style="red")
    table.add_column("Message", style="white")
    
    for v in all_violations:
        rel_path = Path(v.file).relative_to(Path.cwd()) if Path.cwd() in Path(v.file).parents else v.file
        table.add_row(f"{rel_path}:{v.line}", v.check_id, v.message)
        
    console.print(table)
    console.print(f"\n[bold red]❌ Found {len(all_violations)} violations.[/bold red]")
    return False
