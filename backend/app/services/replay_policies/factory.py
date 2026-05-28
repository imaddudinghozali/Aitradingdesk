"""Replay policy registry."""

from __future__ import annotations

from typing import Callable

from app.services.replay_policies.base import ReplayPolicy


_REGISTRY: dict[str, Callable[[], ReplayPolicy]] = {}


def register_replay_policy(name: str, factory: Callable[[], ReplayPolicy]) -> None:
    _REGISTRY[name.lower()] = factory


def get_replay_policy(name: str | None = None) -> ReplayPolicy:
    policy_name = (name or "basic").lower().strip()
    if policy_name in _REGISTRY:
        return _REGISTRY[policy_name]()
    if policy_name == "basic":
        from app.services.replay_policies.basic_policy import BasicReplayPolicy

        return BasicReplayPolicy()
    raise ValueError(f"Unknown replay policy: {policy_name}")
