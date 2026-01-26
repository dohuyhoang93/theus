import ast
import os
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
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

    def to_dict(self):
        return {
            "file": self.file,
            "line": self.line,
            "check_id": self.check_id,
            "message": self.message,
            "severity": self.severity
        }

class POPLinter(ast.NodeVisitor):
    """
    Process-Oriented Programming Linter (v3.1).
    Enforces rules:
    - POP-E01: No print() statements (Use logging).
    - POP-E02: No open() calls (Use Context/Outbox).
    - POP-E03: No network calls/imports (requests, urllib) (Use Outbox).
    - POP-E04: No Global State mutation (global keyword).
    - POP-E05: No Direct Context Mutation (Use Copy-on-Write).
    - POP-E06: Explicit Return Required (Must return Delta/Dict).
    - POP-C01: Contract Integrity (Declared vs Used Inputs).
    """
    
    BANNED_MODULES = {'requests', 'urllib', 'http', 'ftplib', 'smtplib'}
    
    def __init__(self, filename: str):
        self.filename = filename
        self.violations: List[EffectViolation] = []
        self.in_process = False
        self.current_process_name = None
        self.current_contract_inputs: Set[str] = set()
        self.banned_aliases: Dict[str, str] = {} # alias -> real_module

    def visit_Import(self, node):
        for alias in node.names:
            # Check module name (handle submodules like urllib.request)
            root_module = alias.name.split('.')[0]
            if root_module in self.BANNED_MODULES:
                self.violations.append(EffectViolation(
                    self.filename, node.lineno, "POP-E03",
                    f"Importing banned network module '{alias.name}' is forbidden."
                ))

    def visit_ImportFrom(self, node):
        if node.module in self.BANNED_MODULES:
             self.violations.append(EffectViolation(
                self.filename, node.lineno, "POP-E03",
                f"Importing from banned network module '{node.module}' is forbidden."
            ))

    def visit_FunctionDef(self, node):
        # 1. Check if function is a Process (decorated with @process)
        process_decorator = None
        for d in node.decorator_list:
            if isinstance(d, ast.Call) and getattr(d.func, 'id', '') == 'process':
                process_decorator = d
                break
            elif isinstance(d, ast.Name) and d.id == 'process':
                process_decorator = d
                break
        
        is_process = process_decorator is not None
        
        prev_in_process = self.in_process
        prev_inputs = self.current_contract_inputs
        prev_name = self.current_process_name
        
        if is_process:
            self.in_process = True
            self.current_process_name = node.name
            self.current_contract_inputs = self._extract_inputs(process_decorator)
            
        self.generic_visit(node)
        
        # POP-E06: Return Check (After visit to ensure full body scan)
        if is_process:
            has_return = any(isinstance(n, ast.Return) for n in ast.walk(node))
            if not has_return:
                 self.violations.append(EffectViolation(
                    self.filename, node.lineno, "POP-E06",
                    f"Process '{node.name}' must have an explicit return statement (Delta)."
                ))

        # Restore state
        self.in_process = prev_in_process
        self.current_contract_inputs = prev_inputs
        self.current_process_name = prev_name

    def _extract_inputs(self, decorator_node) -> Set[str]:
        """Extracts list of declared inputs from @process decorator."""
        inputs = set()
        if not isinstance(decorator_node, ast.Call):
            return inputs # bare @process
            
        # Parse args/keywords
        # Case 1: @process(['a'], ...) -> Positional args
        if decorator_node.args:
            # Assuming first arg is inputs
            inputs.update(self._parse_list_node(decorator_node.args[0]))
            
        # Case 2: @process(inputs=['a']) -> Keyword args
        for kw in decorator_node.keywords:
            if kw.arg == 'inputs':
                inputs.update(self._parse_list_node(kw.value))
                
        return inputs

    def _parse_list_node(self, node) -> Set[str]:
        items = set()
        if isinstance(node, ast.List):
            for el in node.elts:
                if isinstance(el, ast.Constant) and isinstance(el.value, str):
                    items.add(el.value)
                elif isinstance(el, ast.Str): # Python < 3.8
                     items.add(el.s)
        return items

    def visit_Call(self, node):
        if not self.in_process:
            self.generic_visit(node)
            return

        # POP-E01, POP-E02
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
        
        # POP-E03: Network calls (via attributes e.g. requests.get)
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                module_name = node.func.value.id
                if module_name in self.BANNED_MODULES:
                    self.violations.append(EffectViolation(
                        self.filename, node.lineno, "POP-E03", 
                        f"Network call '{module_name}.{node.func.attr}' forbidden. Use Outbox."
                    ))

        # POP-E05 (Enhanced): Check for destructive method calls on Context
        DESTRUCTIVE_METHODS = {'append', 'extend', 'insert', 'remove', 'pop', 'clear', 'update', 'sort', 'reverse'}
        
        path = self._resolve_attribute_path(node.func)
        if path and path.startswith("ctx."):
            method_name = path.split('.')[-1]
            if method_name in DESTRUCTIVE_METHODS:
                self.violations.append(EffectViolation(
                    self.filename, node.lineno, "POP-E05",
                    f"Direct mutation via '{method_name}()' on Context is forbidden. Return a new list/dict instead."
                ))

        self.generic_visit(node)

    def visit_Global(self, node):
        if self.in_process:
            self.violations.append(EffectViolation(
                self.filename, node.lineno, "POP-E04", 
                "Usage of 'global' keyword is strictly forbidden in POP architecture."
            ))

    def visit_Attribute(self, node):
        """POP-C01 enforcement: Trace usage of ctx fields."""
        if not self.in_process:
            return
            
        # We are looking for access like: ctx.domain.accounts
        # AST structure: Attribute(value=Attribute(value=Name(id='ctx'), attr='domain'), attr='accounts')
        
        path = self._resolve_attribute_path(node)
        if path and path.startswith("ctx."):
            # Clean path: ctx.domain.accounts -> domain.accounts
            clean_path = path[4:] 
            
            # Ignore builtin helpers
            if clean_path in ["log", "restrict_view"]:
                return
                
            # Heuristic: Check if this path matches any declared input
            # Exact match OR prefix match (if declared input is a parent)
            # Example: Declared='domain', Used='domain.accounts' -> OK
            # Example: Declared='domain.accounts', Used='domain' -> Maybe OK? No, usually access.
            
            # Simple Check: Is the root of used path in inputs?
            # Or is the full used path covered by an input?
            
            is_covered = False
            for inp in self.current_contract_inputs:
                if clean_path == inp or clean_path.startswith(inp + "."):
                    is_covered = True
                    break
            
            # Allow 'domain' access if checking existence? 
            # For now strict: If you touch it, declare it.
            # BUT: We only flag if we are fairly sure.
            # Only check 'domain' layer for now as it's the main data zone.
            if clean_path.startswith("domain"):
                if not is_covered:
                     self.violations.append(EffectViolation(
                        self.filename, node.lineno, "POP-C01",
                        f"Undeclared Context Access '{clean_path}'. Add to @process(inputs=[...])."
                    ))

    def _resolve_attribute_path(self, node) -> Optional[str]:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            parent = self._resolve_attribute_path(node.value)
            if parent:
                return f"{parent}.{node.attr}"
        return None

    def visit_Assign(self, node):
        self._check_mutation(node.targets)
        self.generic_visit(node)
        
    def visit_AugAssign(self, node):
        self._check_mutation([node.target])
        self.generic_visit(node)

    def _check_mutation(self, targets):
        """POP-E05: Check for direct mutation of context attributes."""
        if not self.in_process:
            return
            
        for target in targets:
            path = self._resolve_attribute_path(target)
            if path and path.startswith("ctx."):
                 # Whitelist harmless specific attributes if any?
                 # No, context is immutable.
                 self.violations.append(EffectViolation(
                    self.filename, target.lineno, "POP-E05",
                    f"Direct mutation of Context '{path}' is forbidden. Use Copy-on-Write pattern."
                ))

    def visit_Return(self, node):
        """POP-E06: Check return values."""
        if not self.in_process:
            return
            
        if node.value is None:
             self.violations.append(EffectViolation(
                self.filename, node.lineno, "POP-E06",
                "Process must return a value (Delta/Dict). Found empty return."
            ))

def run_lint(target_dir: Path, output_format: str = "table") -> bool:
    """
    Runs linter on all .py files in src/processes and src/
    Returns True if passed, False if violations found.
    """
    all_violations = []
    
    if output_format == "table":
        console.print(f"[cyan]🔍 Running POP Linter Check (v3.1) on {target_dir}...[/cyan]")
    
    for py_file in target_dir.rglob("*.py"):
        if "tests" in str(py_file) or "site-packages" in str(py_file) or "migrations" in str(py_file):
            continue
            
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
            
            linter = POPLinter(str(py_file))
            linter.visit(tree)
            all_violations.extend(linter.violations)
        except Exception as e:
            if output_format == "table":
                console.print(f"[yellow]⚠️ Could not parse {py_file}: {e}[/yellow]")

    if output_format == "json":
        json_output = [v.to_dict() for v in all_violations]
        print(json.dumps(json_output, indent=2))
        return len(all_violations) == 0

    if not all_violations:
        console.print("[bold green]✅ No violations found. POP Compliance: 100%[/bold green]")
        return True
    
    # Report Violations Table
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
