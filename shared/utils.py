"""
Utility functions for 100AC.
"""

import json
from datetime import datetime
from typing import Any, Dict


def serialize_datetime(obj: Any) -> str:
    """
    Serialize datetime objects to ISO format strings.
    
    Args:
        obj: Object to serialize
    
    Returns:
        ISO format string if datetime, otherwise raises TypeError
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def to_json(data: Dict[str, Any], pretty: bool = False) -> str:
    """
    Convert data to JSON string.
    
    Args:
        data: Data to convert
        pretty: Whether to pretty-print
    
    Returns:
        JSON string
    """
    if pretty:
        return json.dumps(data, indent=2, default=serialize_datetime)
    return json.dumps(data, default=serialize_datetime)


def from_json(json_str: str) -> Dict[str, Any]:
    """
    Parse JSON string to dictionary.
    
    Args:
        json_str: JSON string
    
    Returns:
        Parsed dictionary
    """
    return json.loads(json_str)


def format_uptime(seconds: float) -> str:
    """
    Format uptime seconds into human-readable string.
    
    Args:
        seconds: Uptime in seconds
    
    Returns:
        Formatted string (e.g., "2h 15m 30s")
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    
    return " ".join(parts)


def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate a string to maximum length.
    
    Args:
        s: String to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
    
    Returns:
        Truncated string
    """
    if len(s) <= max_length:
        return s
    return s[: max_length - len(suffix)] + suffix
