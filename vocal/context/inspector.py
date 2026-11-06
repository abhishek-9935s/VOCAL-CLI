"""Compatibility entry point for context inspection."""
from .collector import ContextCollector, EnvironmentContext


def inspect_context() -> EnvironmentContext:
    return ContextCollector().collect()
