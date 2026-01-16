"""
Configuration management for 100AC.

Loads configuration from environment variables and config files.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Configuration for the agent system."""
    
    log_level: str = Field(default="INFO")
    message_bus_type: str = Field(default="memory")
    message_retention_seconds: int = Field(default=3600)
    environment: str = Field(default="development")
    debug: bool = Field(default=False)


class ClaudeConfig(BaseModel):
    """Configuration for Claude API."""
    
    api_key: str
    model: str = Field(default="claude-3-5-sonnet-20241022")
    max_tokens: int = Field(default=4096)
    temperature: float = Field(default=0.7)


class Config:
    """
    Central configuration manager for 100AC.
    
    Loads configuration from:
    1. Environment variables (.env file)
    2. YAML configuration files
    3. Default values
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize configuration.
        
        Args:
            config_dir: Directory containing config files. Defaults to ./configs
        """
        # Load environment variables
        load_dotenv()
        
        self.config_dir = config_dir or Path(__file__).parent.parent / "configs"
        self.config_dir.mkdir(exist_ok=True)
        
        # Load configurations
        self.agent_config = self._load_agent_config()
        self.claude_config = self._load_claude_config()
        self.agent_registry_config = self._load_yaml_config("agent_registry.yaml")
        self.workflows_config = self._load_yaml_config("workflows.yaml")
    
    def _load_agent_config(self) -> AgentConfig:
        """Load agent configuration from environment."""
        return AgentConfig(
            log_level=os.getenv("AGENT_LOG_LEVEL", "INFO"),
            message_bus_type=os.getenv("MESSAGE_BUS_TYPE", "memory"),
            message_retention_seconds=int(os.getenv("MESSAGE_RETENTION_SECONDS", "3600")),
            environment=os.getenv("ENVIRONMENT", "development"),
            debug=os.getenv("DEBUG", "false").lower() == "true",
        )
    
    def _load_claude_config(self) -> ClaudeConfig:
        """Load Claude API configuration."""
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            print("WARNING: ANTHROPIC_API_KEY not set. Claude integration will not work.")
        
        return ClaudeConfig(
            api_key=api_key,
            model=os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"),
            max_tokens=int(os.getenv("CLAUDE_MAX_TOKENS", "4096")),
            temperature=float(os.getenv("CLAUDE_TEMPERATURE", "0.7")),
        )
    
    def _load_yaml_config(self, filename: str) -> Dict[str, Any]:
        """Load a YAML configuration file."""
        config_path = self.config_dir / filename
        
        if not config_path.exists():
            return {}
        
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    
    def save_yaml_config(self, filename: str, data: Dict[str, Any]) -> None:
        """Save data to a YAML configuration file."""
        config_path = self.config_dir / filename
        
        with open(config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key."""
        return os.getenv(key, default)


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def init_config(config_dir: Optional[Path] = None) -> Config:
    """Initialize the global configuration instance."""
    global _config
    _config = Config(config_dir)
    return _config
