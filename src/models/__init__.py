# src/models/__init__.py
"""Data models package."""

from .outage import Outage
from .subscription import Subscription

__all__ = [
    'Outage',
    'Subscription',
]
