"""
Workflow Loader - Loads workflows from YAML configuration files.

Handles:
- YAML workflow definitions
- Workflow validation
- Dynamic workflow creation
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from loguru import logger
from shared.data_models import Workflow, WorkflowStep
from shared.config import get_config


class WorkflowLoader:
    """Loads and validates workflows from YAML files."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the workflow loader.
        
        Args:
            config_dir: Directory containing workflow YAML files
        """
        if config_dir:
            self.config_dir = config_dir
        else:
            config = get_config()
            self.config_dir = config.config_dir
        
        logger.info(f"WorkflowLoader initialized with config_dir: {self.config_dir}")
    
    def load_workflows(self, filename: str = "workflows.yaml") -> List[Workflow]:
        """
        Load all workflows from a YAML file.
        
        Args:
            filename: YAML file name
        
        Returns:
            List of Workflow objects
        """
        workflow_path = self.config_dir / filename
        
        if not workflow_path.exists():
            logger.warning(f"Workflow file not found: {workflow_path}")
            return []
        
        with open(workflow_path, "r") as f:
            config = yaml.safe_load(f)
        
        if not config or "workflows" not in config:
            logger.warning(f"No workflows found in {filename}")
            return []
        
        workflows = []
        for workflow_config in config["workflows"]:
            try:
                workflow = self._parse_workflow(workflow_config)
                workflows.append(workflow)
                logger.info(f"Loaded workflow: {workflow.name}")
            except Exception as e:
                logger.error(f"Error loading workflow: {e}")
        
        return workflows
    
    def load_workflow_by_name(self, name: str, filename: str = "workflows.yaml") -> Optional[Workflow]:
        """
        Load a specific workflow by name.
        
        Args:
            name: Workflow name
            filename: YAML file name
        
        Returns:
            Workflow object or None
        """
        workflows = self.load_workflows(filename)
        for workflow in workflows:
            if workflow.name == name:
                return workflow
        
        logger.warning(f"Workflow '{name}' not found")
        return None
    
    def _parse_workflow(self, config: Dict[str, Any]) -> Workflow:
        """
        Parse a workflow from config dict.
        
        Args:
            config: Workflow configuration
        
        Returns:
            Workflow object
        """
        name = config["name"]
        description = config.get("description", "")
        steps_config = config.get("steps", [])
        
        steps = []
        for step_config in steps_config:
            step = WorkflowStep(
                step_id=step_config["step_id"],
                agent_id=step_config["agent_id"],
                action=step_config["action"],
                parameters=step_config.get("parameters", {}),
                timeout_seconds=step_config.get("timeout_seconds", 30),
                retry_count=step_config.get("retry_count", 0),
                on_error=step_config.get("on_error", "stop"),
            )
            steps.append(step)
        
        return Workflow(
            name=name,
            description=description,
            steps=steps,
        )
    
    def save_workflow(self, workflow: Workflow, filename: str = "workflows.yaml") -> None:
        """
        Save a workflow to YAML file.
        
        Args:
            workflow: The workflow to save
            filename: YAML file name
        """
        workflow_path = self.config_dir / filename
        
        # Load existing workflows
        existing_workflows = []
        if workflow_path.exists():
            with open(workflow_path, "r") as f:
                config = yaml.safe_load(f) or {}
                existing_workflows = config.get("workflows", [])
        
        # Convert workflow to dict
        workflow_dict = {
            "name": workflow.name,
            "description": workflow.description,
            "steps": [
                {
                    "step_id": step.step_id,
                    "agent_id": step.agent_id,
                    "action": step.action,
                    "parameters": step.parameters,
                    "timeout_seconds": step.timeout_seconds,
                    "retry_count": step.retry_count,
                    "on_error": step.on_error,
                }
                for step in workflow.steps
            ],
        }
        
        # Check if workflow already exists
        found = False
        for i, existing in enumerate(existing_workflows):
            if existing["name"] == workflow.name:
                existing_workflows[i] = workflow_dict
                found = True
                break
        
        if not found:
            existing_workflows.append(workflow_dict)
        
        # Save to file
        with open(workflow_path, "w") as f:
            yaml.dump({"workflows": existing_workflows}, f, default_flow_style=False)
        
        logger.info(f"Saved workflow '{workflow.name}' to {filename}")
    
    def list_workflows(self, filename: str = "workflows.yaml") -> List[Dict[str, str]]:
        """
        List all workflow names and descriptions.
        
        Args:
            filename: YAML file name
        
        Returns:
            List of workflow summaries
        """
        workflows = self.load_workflows(filename)
        return [
            {
                "name": w.name,
                "description": w.description,
                "steps": len(w.steps),
            }
            for w in workflows
        ]


# Global loader instance
_loader: Optional[WorkflowLoader] = None


def get_loader() -> WorkflowLoader:
    """Get the global workflow loader instance."""
    global _loader
    if _loader is None:
        _loader = WorkflowLoader()
    return _loader


def init_loader(config_dir: Optional[Path] = None) -> WorkflowLoader:
    """Initialize the global workflow loader instance."""
    global _loader
    _loader = WorkflowLoader(config_dir)
    return _loader
