#!/usr/bin/env python3
"""Observe research evidence and supervise one owned attempt; no model calls."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import uuid


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def process_identity(pid):
    """PID alone is unsafe: Linux start ticks and boot id prevent PID reuse."""
    try:
        proc = Path('/proc') / str(int(pid))
        fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': int(pid), 'start_ticks': fields[19],
                'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                'host': socket.gethostname()}
    except (OSError, ValueError, IndexError):
        return None


def owner_state(identity):
    if not identity or identity.get('host') != socket.gethostname():
        return 'unknown'
    actual = process_identity(identity.get('pid', -1))
    if actual is None:
        return 'not_observed'  # No permission and no process are not conflated with success.
    return 'alive' if actual == identity else 'identity_mismatch'


def classify(metrics):
    """Conservative evidence labels, deliberately not a paper acceptance gate."""
    if metrics.get('status') != 'completed':
        return 'incomplete'
    if metrics.get('backend') == 'deterministic_local':
        return 'offline_correctness'
    if metrics.get('live_model_calls', 0) > 0:
        if metrics.get('replay_for_paired_methods'):
            return 'live_construction_with_replay_pairs'
        return 'live_run_requires_pair_and_qa_review'
    return 'completed_requires_evidence_review'


def project_processes(root):
    result = []
    proc_root = Path('/proc')
    if not proc_root.exists():
        return result
    for proc in proc_root.iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            cwd = Path(os.readlink(proc / 'cwd'))
            if not (cwd == root or root in cwd.parents):
                continue
            name = (proc / 'comm').read_text().strip()
            if 'python' not in name.lower():
                continue
            run_files = []
            for fd in (proc / 'fd').iterdir():
                try:
                    target = os.readlink(fd)
                    if str(root / 'runs') + '/' in target:
                        run_files.append(target)
                except OSError:
                    pass
            result.append({'identity': process_identity(proc.name), 'cwd': str(cwd),
                           'program': name, 'run_files': sorted(set(run_files))})
        except OSError:
            continue
    return result


def inspect_project(root):
    runtime = read_json(root / 'configs/runtime.local.json')
    if not runtime:
        runtime = read_json(root / 'configs/runtime.json')
    plan = runtime.get('plan', runtime)
    models = plan.get('models', {})
    resources = {}
    for role in ('construction', 'embedding', 'reader'):
        cfg = models.get(role, {})
        local = cfg.get('local_path')
        resources[role] = {'backend': cfg.get('backend'), 'local_path': local,
                           'local_path_exists': bool(local and Path(local).is_dir())}
    runs, problems = [], []
    for directory in sorted((root / 'runs').glob('*')):
        if not directory.is_dir():
            continue
        status = read_json(directory / 'status.json')
        metrics = read_json(directory / 'metrics.json')
        progress = read_json(directory / 'progress.json')
        if not status and not metrics:
            continue
        observed = status.get('status', metrics.get('status', 'unknown'))
        inconsistent = bool(status.get('status') and metrics.get('status')
                            and status['status'] != metrics['status'])
        evidence = classify(metrics)
        if observed != 'completed' and evidence != 'incomplete':
            evidence = 'conflicting_terminal_evidence_requires_review'
        row = {'run_id': directory.name, 'status': observed, 'evidence': evidence,
               'suite': status.get('suite', metrics.get('suite')),
               'status_metrics_disagree': inconsistent,
               'live_model_calls': metrics.get('live_model_calls', 0),
               'qa_rows': metrics.get('qa_rows', 0),
               'replay_for_paired_methods': metrics.get('replay_for_paired_methods'),
               'progress': progress, 'failure': status.get('failure'),
               'judge_probe': metrics.get('judge_probe')}
        if observed == 'running':
            row['ownership'] = 'legacy_unverified'
            row['action'] = 'Correlate process identity, open files and progress before resuming; never infer completion.'
        runs.append(row)
    attempts = []
    for path in sorted((root / 'execution/attempts').glob('*/status.json')):
        item = read_json(path)
        attempts.append({'attempt_id': path.parent.name, 'task': item.get('task'),
                         'status': item.get('status'), 'exit_code': item.get('exit_code'),
                         'owner': owner_state(item.get('supervisor')),
                         'child': owner_state(item.get('child')),
                         'next_action': item.get('next_action')})
    for name in ('cli.py', 'live_pipeline.py'):
        path = root / 'src/workflow_memory' / name
        if not path.exists():
            continue
        source = path.read_text(encoding='utf-8')
        if name == 'cli.py' and '_not_implemented("tune")' in source:
            problems.append('tune_stub: implement development optimization; not an external blocker')
        if name == 'cli.py' and 'writer.writerows(rows)' in source and 'for name in ("main_internal"' in source:
            problems.append('report_review: identical rows may be written to unrelated tables')
    queue = read_json(root / 'execution/queue.json')
    tasks = queue.get('tasks', [])
    done = {t['id'] for t in tasks if t.get('status') == 'done'}
    actionable = [t['id'] for t in tasks if t.get('status') in ('todo', 'in_progress')
                  and set(t.get('depends_on', [])) <= done]
    blocked = [t['id'] for t in tasks if t.get('status') == 'blocked_external']
    status_text = (root / 'STATUS.md').read_text(encoding='utf-8') if (root / 'STATUS.md').exists() else ''
    status_text = status_text.split('## 以下为部署前状态快照', 1)[0]
    live_found = any(r['live_model_calls'] > 0 and r['status'] == 'completed' for r in runs)
    if live_found and any(word in status_text for word in ('live_model_blocked', '模型和数据缺失')):
        problems.append('status_review: historical missing-resource statements coexist with successful live evidence')
    receipt = read_json(root / 'execution/ack-memory-loop-v3.json')
    received = (receipt.get('update_id') == 'memory-loop-v3-20261012'
                and bool(receipt.get('received_at')) and bool(receipt.get('next_task')))
    return {'schema_version': 1, 'observed_at': now(), 'root': str(root),
            'resources': resources, 'runs': runs, 'managed_attempts': attempts,
            'project_python_processes': project_processes(root),
            'implementation_tasks': problems, 'actionable_tasks': actionable,
            'blocked_tasks': blocked,
            'executor_update': {'receipt_present': received, 'receipt': receipt},
            'notes': ['Read-only observation unless --write is requested.',
                      'Judge absence does not block construction or performance.',
                      'Success is not inferred from replay, heartbeat, filenames or exit code.',
                      'Process scan covers this code-root cwd; parent-cwd or external jobs need separate inspection.']}


@contextmanager
def resource_lock(root, resource):
    if os.name != 'posix':
        raise RuntimeError('run supervisor requires Linux; inspect works on other hosts')
    import fcntl
    path = root / 'execution' / (resource + '.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Another managed attempt owns resource ' + resource) from exc
        yield


def stop_owned(child):
    if child.poll() is not None:
        return
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        child.wait()
        return
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()


def run_attempt(root, args):
    command = list(args.argv)
    if command and command[0] == '--':
        command.pop(0)
    if not command or args.timeout <= 0 or args.heartbeat <= 0:
        raise ValueError('Need command, positive timeout and positive heartbeat')
    with resource_lock(root, args.resource):
        attempt_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        directory = root / 'execution/attempts' / attempt_id
        directory.mkdir(parents=True)
        state = {'schema_version': 1, 'attempt_id': attempt_id, 'task': args.task,
                 'hypothesis': args.hypothesis, 'command': command, 'cwd': str(root),
                 'resource': args.resource, 'started_at': now(), 'status': 'starting',
                 'supervisor': process_identity(os.getpid()), 'child': None,
                 'timeout_seconds': args.timeout, 'exit_code': None,
                 'heartbeat_means': 'supervisor alive, not experiment making progress'}
        write_json(directory / 'status.json', state)
        print(json.dumps({'attempt': str(directory)}, ensure_ascii=False), flush=True)
        interrupted = []
        handlers = {}
        for sig in (signal.SIGTERM, signal.SIGINT):
            handlers[sig] = signal.signal(sig, lambda signum, frame: interrupted.append(signum))
        child = None
        started = time.monotonic()
        last = 0.0
        try:
            with (directory / 'stdout.log').open('wb') as stdout, (directory / 'stderr.log').open('wb') as stderr:
                child = subprocess.Popen(command, cwd=root, stdout=stdout, stderr=stderr,
                                         start_new_session=True, close_fds=True)
                state.update(status='running', child=process_identity(child.pid))
                write_json(directory / 'status.json', state)
                while child.poll() is None:
                    elapsed = time.monotonic() - started
                    if interrupted or elapsed >= args.timeout:
                        state['status'] = 'interrupted' if interrupted else 'timed_out'
                        stop_owned(child)
                        break
                    if time.monotonic() - last >= args.heartbeat:
                        write_json(directory / 'heartbeat.json', {
                            'observed_at': now(), 'elapsed_seconds': elapsed,
                            'supervisor': state['supervisor'], 'child': state['child'],
                            'stdout_bytes': (directory / 'stdout.log').stat().st_size,
                            'stderr_bytes': (directory / 'stderr.log').stat().st_size,
                            'meaning': 'supervisor alive; inspect run progress separately'})
                        last = time.monotonic()
                    time.sleep(min(args.heartbeat, 0.2))
                state['exit_code'] = child.wait()
                if state['status'] == 'running':
                    state['status'] = 'command_succeeded' if child.returncode == 0 else 'failed'
        except Exception as exc:
            state.update(status='launch_or_supervisor_failed', error_type=type(exc).__name__, error=str(exc))
            if child is not None:
                stop_owned(child)
                state['exit_code'] = child.returncode
        finally:
            state['finished_at'] = now()
            state['elapsed_seconds'] = time.monotonic() - started
            state['next_action'] = ('Review semantic artifacts and metrics, update queue, execute next task.'
                                    if state['status'] == 'command_succeeded' else
                                    'Read stderr/stdout, record root-cause hypothesis, repair and retry or execute an independent task.')
            write_json(directory / 'status.json', state)
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
        print(json.dumps({k: state[k] for k in ('attempt_id', 'status', 'exit_code', 'next_action')}, ensure_ascii=False), flush=True)
        return 0 if state['status'] == 'command_succeeded' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    sub = parser.add_subparsers(dest='action', required=True)
    inspect = sub.add_parser('inspect')
    inspect.add_argument('--write', action='store_true', help='Save observation, never rewrite run status')
    run = sub.add_parser('run')
    run.add_argument('--task', required=True)
    run.add_argument('--hypothesis', required=True)
    run.add_argument('--timeout', type=float, required=True)
    run.add_argument('--heartbeat', type=float, default=5)
    run.add_argument('--resource', choices=('cpu', 'gpu'), default='cpu')
    run.add_argument('argv', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        parser.error('root must exist')
    if args.action == 'inspect':
        report = inspect_project(root)
        if args.write:
            write_json(root / 'execution/observed.json', report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    try:
        return run_attempt(root, args)
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
