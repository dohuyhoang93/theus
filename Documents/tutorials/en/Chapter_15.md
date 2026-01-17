# Chapter 15: CLI Tools Reference

Theus v3.0 provides a powerful CLI suite to accelerate development and maintain architectural integrity.

## 1. Project Initialization

```bash
py -m theus.cli init <project_name>
```

Scaffolds a new project with the standard V3 structure:
```
my_project/
├── src/
│   └── processes/
├── specs/
│   ├── audit_recipe.yaml
│   └── context_schema.yaml
├── workflows/
│   └── main_workflow.yaml
└── main.py
```

## 2. Audit Tools

### Generate Audit Spec

```bash
py -m theus.cli audit gen-spec
```

Scans your `@process` functions and automatically populates `specs/audit_recipe.yaml` with rule skeletons.

### Inspect Process

```bash
py -m theus.cli audit inspect <process_name>
```

Inspects the effective audit rules, side effects, and error contracts for a specific process.

## 3. Schema Generation

```bash
py -m theus.cli schema gen
```

Infers and generates `specs/context_schema.yaml` from your Python Dataclass definitions.

## 4. POP Linter

```bash
py -m theus.cli check [path]
```

Runs the **POP Linter** to enforce architectural purity.

| Rule | Violation | Fix |
|:-----|:----------|:----|
| POP-E01 | `print()` calls | Use `ctx.log` |
| POP-E02 | `open()` file access | Use Outbox |
| POP-E03 | `requests` HTTP calls | Use side_effects declaration |
| POP-E04 | `global` keyword | Use Context |

## 5. Example Workflow

```bash
# 1. Create new project
py -m theus.cli init bank_app

# 2. Navigate to project
cd bank_app

# 3. Generate audit skeleton after writing processes
py -m theus.cli audit gen-spec

# 4. Check code quality
py -m theus.cli check src/processes

# 5. Run application
python main.py
```

---
**Exercise:**
Initialize a new project with `theus.cli init`. Explore the generated structure.
