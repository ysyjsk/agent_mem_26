"""Workflow-aware concurrent and incremental memory construction.

P0 exposes configuration, run planning, and persistence primitives.  Model
backends are intentionally injected later through stable interfaces.
"""

from .config import ConfigError, content_hash, load_plan, load_runtime
from .runtime import (
    BackendUnavailable,
    ResumeMismatch,
    build_task_plan,
    create_run,
    dry_run,
    execute_run,
    resume_run,
)
from .ir import (
    ComputeNode,
    Evidence,
    PreparedUpdate,
    PublishedSnapshot,
    SourceEvent,
    canonical_json,
    normalize_trajectory,
    source_frontier,
    stable_hash,
)
from .backends import (
    BackendNotConfigured,
    EmbeddingBackend,
    EmbeddingProvider,
    EmbeddingResponse,
    ConstructionBackend,
    JudgeBackend,
    JudgeProvider,
    LLMBackend,
    ModelBackend,
    ModelRequest,
    ModelResponse,
    ReaderBackend,
    ReaderProvider,
    OpenAICompatibleBackend,
    OpenAICompatibleEmbeddingBackend,
    VLLMBackend,
)
from .local_backends import (
    LocalBackendUnavailable,
    TransformersEmbeddingBackend,
    TransformersQwenBackend,
)
from .replay import DeterministicReplayBackend, ReplayBackend, ReplayMiss, ReplayMissError
from .construction import (
    ConstructionError,
    EvidenceBundle,
    Snapshot,
    UpdateReceipt,
    apply_delta,
    build_fresh,
    plan_graph_for,
    query,
    validate_snapshot,
)
from .event_store import EventStore
from .dependency import ComputeGraph, DependencyTracker
from .cache import CacheKey, NodeCache, make_cache_key
from .adapters import AgentRunbookRAdapter, CodexNativeAdapter, LongMemEvalV2Adapter, MemForestAdapter
from .scheduler import DependencyScheduler, NodeResult, ScheduleResult, schedule
from .commit import CommitConflict, ReadSet, ReaderEpoch, SnapshotCommitter
from .statistics import noninferior, paired_differences, percentile, summarize
from .evaluation import FreshnessRecord, freshness_summary, goodput

# The workplan names plan_graph as the public operation. Keep the
# implementation's descriptive plan_graph_for spelling available too.
plan_graph = plan_graph_for

__all__ = [
    "BackendUnavailable",
    "BackendNotConfigured",
    "ConfigError",
    "ResumeMismatch",
    "build_task_plan",
    "content_hash",
    "create_run",
    "dry_run",
    "execute_run",
    "load_plan",
    "load_runtime",
    "resume_run",
    "SourceEvent",
    "Evidence",
    "ComputeNode",
    "PreparedUpdate",
    "PublishedSnapshot",
    "canonical_json",
    "normalize_trajectory",
    "source_frontier",
    "stable_hash",
    "ModelBackend",
    "LLMBackend",
    "ConstructionBackend",
    "EmbeddingBackend",
    "EmbeddingProvider",
    "ReaderBackend",
    "ReaderProvider",
    "JudgeBackend",
    "JudgeProvider",
    "ModelRequest",
    "ModelResponse",
    "EmbeddingResponse",
    "OpenAICompatibleBackend",
    "OpenAICompatibleEmbeddingBackend",
    "VLLMBackend",
    "LocalBackendUnavailable",
    "TransformersQwenBackend",
    "TransformersEmbeddingBackend",
    "DeterministicReplayBackend",
    "ReplayBackend",
    "ReplayMiss",
    "ReplayMissError",
    "ConstructionError",
    "Snapshot",
    "UpdateReceipt",
    "EvidenceBundle",
    "plan_graph",
    "plan_graph_for",
    "build_fresh",
    "apply_delta",
    "query",
    "validate_snapshot",
    "EventStore",
    "ComputeGraph",
    "DependencyTracker",
    "CacheKey",
    "NodeCache",
    "make_cache_key",
    "LongMemEvalV2Adapter",
    "AgentRunbookRAdapter",
    "MemForestAdapter",
    "CodexNativeAdapter",
    "DependencyScheduler",
    "NodeResult",
    "ScheduleResult",
    "schedule",
    "CommitConflict",
    "ReadSet",
    "ReaderEpoch",
    "SnapshotCommitter",
    "percentile",
    "summarize",
    "paired_differences",
    "noninferior",
    "FreshnessRecord",
    "freshness_summary",
    "goodput",
]
