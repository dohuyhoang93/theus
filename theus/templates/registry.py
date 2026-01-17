from typing import Dict, Any
from pathlib import Path
from .data import (
    TEMPLATE_ENV,
    TEMPLATE_MAIN,
    TEMPLATE_CONTEXT,
    TEMPLATE_WORKFLOW,
    TEMPLATE_PROCESS_CHAIN,
    TEMPLATE_PROCESS_STRESS,
    TEMPLATE_AUDIT_RECIPE,
    TEMPLATE_PROCESS_ECOMMERCE,
    TEMPLATE_WORKFLOW_ECOMMERCE,
    TEMPLATE_AUDIT_ECOMMERCE
)

class TemplateRegistry:
    """
    Registry for Theus project templates.
    """
    
    @staticmethod
    def get_template(template_name: str) -> Dict[str, str]:
        """
        Returns a dictionary of filename -> content for the requested template.
        """
        base_files = {
            ".env": TEMPLATE_ENV,
            "main.py": TEMPLATE_MAIN,
            "src/context.py": TEMPLATE_CONTEXT,
            "src/__init__.py": "",
            "src/processes/__init__.py": "",
            "workflows/workflow.yaml": TEMPLATE_WORKFLOW,
            "specs/context_schema.yaml": "# Define your Data Contract here\n",
            "specs/audit_recipe.yaml": TEMPLATE_AUDIT_RECIPE,
            "specs/workflow.yaml": TEMPLATE_WORKFLOW 
        }

        if template_name == "minimal":
            # Minimal template: Just the basics
            return base_files
            
        elif template_name == "standard":
            # Standard template: Include demo processes
            base_files["src/processes/chain.py"] = TEMPLATE_PROCESS_CHAIN
            base_files["src/processes/stress.py"] = TEMPLATE_PROCESS_STRESS
            return base_files
            
        elif template_name == "agent":
            # Agent template: Placeholder for future agentic structure
            base_files["src/processes/perception.py"] = "# Perception processes\n"
            base_files["src/processes/action.py"] = "# Action processes\n"
            base_files["src/processes/learning.py"] = "# Learning processes\n"
            return base_files
            
        elif template_name == "hybrid":
             # FSM + Pipeline Hybrid
             from .data import TEMPLATE_PROCESS_PIPELINE, TEMPLATE_WORKFLOW_HYBRID
             base_files["src/processes/pipeline.py"] = TEMPLATE_PROCESS_PIPELINE
             base_files["workflows/workflow.yaml"] = TEMPLATE_WORKFLOW_HYBRID
             # We reuse context/main from standard for simplicity
             return base_files

        elif template_name == "ecommerce":
             # E-Commerce Demo (from Integration Test)
             base_files["src/processes/ecommerce.py"] = TEMPLATE_PROCESS_ECOMMERCE
             base_files["workflows/workflow.yaml"] = TEMPLATE_WORKFLOW_ECOMMERCE
             base_files["specs/audit_recipe.yaml"] = TEMPLATE_AUDIT_ECOMMERCE
             return base_files

        else:
            raise ValueError(f"Unknown template: {template_name}")

    @staticmethod
    def list_templates() -> list[str]:
        return ["minimal", "standard", "ecommerce", "agent", "hybrid"]

    @staticmethod
    def list_templates_details() -> list[tuple[str, str]]:
        """Returns list of (name, description) tuples."""
        return [
            ("standard", "Standard project with Flux Loop + Audit Demo"),
            ("ecommerce", "E-Commerce Demo: Orders, Payments, Heavy Zone, Rollback"),
            ("hybrid",   "Advanced: Flux FSM + Pure Python Pipelines (High Performance)"),
            ("agent",    "Agentic Skeleton (Perception-Action-Learning)"),
            ("minimal",  "Bare-bones structure (experienced users only)"),
        ]
