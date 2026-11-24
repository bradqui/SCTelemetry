"""The fleet hub: agents send their telemetry here; org members watch the fleet (spec §6.2)."""

__version__ = "0.4.0"

MIN_AGENT_VERSION = "0.2.0"
"""Older agents are refused with a download link. Raise it when the hub stops
understanding what an older agent sends (or an old agent would mislead the fleet)."""
