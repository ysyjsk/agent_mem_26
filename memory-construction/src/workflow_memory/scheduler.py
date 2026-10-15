"""Bounded dependency-ready scheduling primitives.

Preparation workers never hold an EventStore write transaction.  The helper is
small enough for deterministic tests and can later be replaced by an asyncio
or service scheduler without changing ComputeGraph contracts.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import time
from typing import Any, Callable, Iterable, Mapping

from .dependency import ComputeGraph


@dataclass(frozen=True)
class NodeResult:
    node_id: str
    status: str
    output: Any = None
    attempts: int = 1
    elapsed_ns: int = 0
    error: str | None = None


@dataclass(frozen=True)
class ScheduleResult:
    results: tuple[NodeResult, ...]
    completed: tuple[str, ...]
    failed: tuple[str, ...]
    retries: int = 0
    fallback_scopes: tuple[str, ...] = field(default_factory=tuple)


class DependencyScheduler:
    def __init__(self, *, max_workers: int = 1, max_retries: int = 2) -> None:
        self.max_workers = max(1, int(max_workers))
        self.max_retries = max(0, int(max_retries))

    def run(self, graph: ComputeGraph, worker: Callable[[Any], Any], *, completed: Iterable[str] = ()) -> ScheduleResult:
        done = set(str(item) for item in completed)
        results: list[NodeResult] = []
        failed: list[str] = []
        retries = 0
        while len(done) < len(graph.nodes):
            ready = [node_id for node_id in graph.ready_nodes(done) if node_id not in done]
            if not ready:
                unresolved = sorted(set(graph.nodes) - done)
                failed.extend(unresolved)
                results.extend(NodeResult(node_id=node_id, status="blocked", error="dependency cycle or missing predecessor") for node_id in unresolved)
                break
            def run_one(node_id: str) -> NodeResult:
                attempts = 0
                started = time.perf_counter_ns()
                while True:
                    attempts += 1
                    try:
                        return NodeResult(node_id=node_id, status="completed", output=worker(graph.nodes[node_id]), attempts=attempts, elapsed_ns=time.perf_counter_ns() - started)
                    except Exception as exc:  # retry is bounded and visible
                        if attempts > self.max_retries:
                            return NodeResult(node_id=node_id, status="failed", attempts=attempts, elapsed_ns=time.perf_counter_ns() - started, error=str(exc))
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(ready))) as pool:
                futures = {pool.submit(run_one, node_id): node_id for node_id in ready}
                batch: list[NodeResult] = []
                for future in as_completed(futures):
                    result = future.result()
                    batch.append(result)
                    retries += max(0, result.attempts - 1)
            for result in sorted(batch, key=lambda item: item.node_id):
                results.append(result)
                if result.status == "completed":
                    done.add(result.node_id)
                else:
                    failed.append(result.node_id)
                    # Do not spin forever on a permanently failed node.
                    done.add(result.node_id)
        return ScheduleResult(tuple(results), tuple(sorted(done - set(failed))), tuple(sorted(set(failed))), retries)


def schedule(graph: ComputeGraph, worker: Callable[[Any], Any], *, concurrency: int = 1, max_retries: int = 2) -> ScheduleResult:
    return DependencyScheduler(max_workers=concurrency, max_retries=max_retries).run(graph, worker)


__all__ = ["NodeResult", "ScheduleResult", "DependencyScheduler", "schedule"]
