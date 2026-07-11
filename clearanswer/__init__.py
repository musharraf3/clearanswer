"""ClearAnswer — a glass-box RAG copilot that decodes Explanation of Benefits
documents into plain language, with every claim cited and every number
re-checked in code.

Weekend Builds in Healthcare AI · #2
"""

__version__ = "0.1.0"

# Teacher model: authors the skill pack, sets the quality ceiling in evals.
MODEL_TEACHER = "claude-fable-5"
# Worker model: runs the product at ~10x lower cost, boosted by the skill pack.
MODEL_WORKER = "claude-haiku-4-5-20251001"
