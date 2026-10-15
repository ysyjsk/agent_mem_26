"""Dataset and external-system adapters.

Adapters are intentionally thin.  They normalize source trajectories into the
same :class:`workflow_memory.SourceEvent` representation and expose the
``insert``/``query`` shape used by official systems without claiming that an
external implementation is available locally.
"""

from .longmemeval_v2 import LongMemEvalV2Adapter
from .agentrunbook_r import AgentRunbookRAdapter
from .memforest import MemForestAdapter
from .codex_native import CodexNativeAdapter

__all__ = [
    "LongMemEvalV2Adapter",
    "AgentRunbookRAdapter",
    "MemForestAdapter",
    "CodexNativeAdapter",
]
