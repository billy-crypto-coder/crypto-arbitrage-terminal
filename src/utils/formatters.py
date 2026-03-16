"""
Number and date formatting utilities
"""
from datetime import datetime


def format_number(value: float, decimals: int = 2, prefix: str = "") -> str:
    """Format a number with currency prefix."""
    return f"{prefix}{value:,.{decimals}f}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """Format a percentage."""
    return f"{value:,.{decimals}f}%"


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format a datetime object."""
    return dt.strftime(format_str)


def abbreviate_number(value: float) -> str:
    """Abbreviate large numbers (e.g., 1000000 -> 1.0M)."""
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.1f}K"
    else:
        return str(value)
