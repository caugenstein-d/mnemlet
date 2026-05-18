"""Decay engine: exponential time-decay + interaction weighting + purge."""

import math
from datetime import datetime, timezone
from typing import Optional
from memoria.constants import (
    BOOST_CREATE, BOOST_RECALL, BOOST_UPDATE, BOOST_REFERENCE, PENALTY_IGNORE,
    DEFAULT_LAMBDA,
)


BOOST_MAP = {
    "create": BOOST_CREATE,
    "recall": BOOST_RECALL,
    "update": BOOST_UPDATE,
    "reference": BOOST_REFERENCE,
    "ignore": PENALTY_IGNORE,
}


class DecayEngine:
    """Handles memory decay, interaction boosts, and purging."""

    def __init__(self, db):
        self.db = db

    def calculate_decay(
        self,
        current_score: float,
        days_elapsed: float,
        lambda_: float = DEFAULT_LAMBDA,
    ) -> float:
        """Calculate decayed score using exponential decay: score * e^(-lambda * t).

        Args:
            current_score: The current retention score (0.0 to 1.0).
            days_elapsed: Days since last access.
            lambda_: Decay rate (higher = faster forgetting).

        Returns:
            The decayed score, never below 0.0.
        """
        decayed = current_score * math.exp(-lambda_ * days_elapsed)
        return max(0.0, decayed)

    def apply_boost(self, current_score: float, interaction_type: str) -> float:
        """Apply an interaction boost (or penalty) to a retention score.

        Args:
            current_score: Current retention score.
            interaction_type: One of 'create', 'recall', 'update', 'reference', 'ignore'.

        Returns:
            New score, capped at 1.0, floored at 0.0.

        Raises:
            ValueError: If interaction_type is unknown.
        """
        if interaction_type not in BOOST_MAP:
            raise ValueError(
                f"Unknown interaction type: {interaction_type}. "
                f"Valid types: {list(BOOST_MAP.keys())}"
            )

        boost = BOOST_MAP[interaction_type]
        new_score = current_score + boost
        return max(0.0, min(1.0, new_score))

    def boost_memory(
        self, memory_id: str, interaction_type: str, agent_id: str = "api"
    ) -> dict:
        """Apply a boost to a specific memory and record the interaction.

        Returns the updated memory as dict.
        """
        memory = self.db.get_memory(memory_id)
        if memory is None:
            raise ValueError(f"Memory {memory_id} not found")

        current_score = memory["retention_score"]
        new_score = self.apply_boost(current_score, interaction_type)

        self.db.update_score(memory_id, new_score)
        self.db.record_interaction(memory_id, interaction_type, agent_id)

        return dict(self.db.get_memory(memory_id))
