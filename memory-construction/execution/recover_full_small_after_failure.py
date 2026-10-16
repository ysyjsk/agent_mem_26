#!/usr/bin/env python3
"""Resume registered full-small steps after recoverable failures.

The original failed receipt is preserved. This recovery uses the same registered
plan, commands, manifest and output paths, adding only versioned recovery
receipts. It must run after the detached queue is terminal.
"""
import argparse, json, os, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PYTHON='/data/predator/ly/Mem/.venv/bin/python'
CONTROL=ROOT/'execution/full-small-recovery-v1'
RECOVERY=CONTROL/'recovery-units-20261016'

def read(p): return json.loads((ROOT/p).read_text())
def write(p,x):
 p=ROOT/p; p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists(): raise FileExistsError(p)
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

def unit_receipt(sid):
 return CONTROL/'units'/f'{sid}.json'

def optional_read(path):
 return read(path) if path.exists() else None

def recovery_candidates(sid):
 exact=RECOVERY/f'{sid}.json'
 return [exact]+sorted(RECOVERY.glob(f'{sid}-retry*.json'))

def validated_reuse(step,q):
 sid=step['id']
 for path in recovery_candidates(sid):
  if path.exists() and read(path).get('status')=='completed':
   q.validate(step); return {'source':str(path.relative_to(ROOT)),'kind':'recovery_receipt'}
 oldp=unit_receipt(sid); old=optional_read(oldp)
 if old and old.get('status')=='completed':
  q.validate(step); return {'source':str(oldp.relative_to(ROOT)),'kind':'original_receipt'}
 marker=ROOT/step['marker']
 if step['kind']=='freeze' and marker.exists():
  if read(marker).get('status')=='frozen_before_formal_maintenance':
   return {'source':str(marker.relative_to(ROOT)),'kind':'runtime_manifest'}
 if marker.exists() and step['kind'] not in ('freeze','report'):
  q.validate(step); return {'source':str(marker.relative_to(ROOT)),'kind':'validated_marker'}
 return None

def allocate_receipt(sid,record):
 exact=RECOVERY/f'{sid}.json'
 if not exact.exists():
  write(exact,record); return exact
 for index in range(1,1000):
  candidate=RECOVERY/f'{sid}-retry{index}.json'
  if not candidate.exists():
   write(candidate,record); return candidate
 raise RuntimeError(f'cannot allocate recovery receipt for {sid}')

def original_queue_active(pidfile):
 if not pidfile.exists(): return False
 try:
  pid=int(pidfile.read_text().strip()); os.kill(pid,0)
 except (FileNotFoundError,ProcessLookupError,PermissionError,ValueError):
  return False
 try:
  command=Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0',b' ').decode()
 except OSError:
  return False
 return 'run_full_small_formal.py' in command

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--failed-unit',action='append',dest='failed_units',help='failed root unit to retry; repeat for multiple units')
 ap.add_argument('--execute',action='store_true')
 ap.add_argument('--dry-run',action='store_true',help='inspect branches without model calls')
 args=ap.parse_args()
 if args.execute and args.dry_run: ap.error('--execute and --dry-run are mutually exclusive')
 plan=read(CONTROL/'experiment_plan.json')
 import sys; sys.path.insert(0,str(ROOT/'tools')); import run_full_small_formal as q
 if q.input_hashes(plan['steps']) != plan['input_sha256']: raise RuntimeError('registered code/input hash changed')
 pidfile=ROOT/'execution/background/full-small-formal-queue-20261016-v1/pid'
 if original_queue_active(pidfile): raise RuntimeError(f'original full-small queue still active: {pidfile}')
 steps=plan['steps']; known={s['id'] for s in steps}
 old_records={s['id']:optional_read(unit_receipt(s['id'])) for s in steps}
 targets=set(args.failed_units or [s['id'] for s in steps if s['kind']=='expansion' and old_records[s['id']] and old_records[s['id']].get('status')=='failed'])
 unknown=targets-known
 if unknown: raise ValueError(f'unknown failed unit(s): {sorted(unknown)}')
 states={}; reused={}; skipped_failed=[]; eligible=[]; RECOVERY.mkdir(parents=True,exist_ok=True)
 for step in plan['steps']:
  sid=step['id']; old=old_records[sid]
  if step['kind']!='report':
   try: evidence=validated_reuse(step,q)
   except Exception as exc: evidence=None; reused[sid]={'validation_error':repr(exc)}
   if evidence: states[sid]='completed'; reused[sid]=evidence; continue
  old_status=old.get('status') if old else None
  if old_status=='failed' and sid not in targets:
   states[sid]='failed'; skipped_failed.append(sid); continue
  if any(states.get(dep)!='completed' for dep in step.get('depends_on',())):
   states[sid]='pending'; continue
  if step['kind']=='report' and any(states.get(previous['id'])!='completed' for previous in plan['steps'] if previous is not step):
   states[sid]='pending'; continue
  if sid not in targets and old_status not in (None,'blocked_by_failed_dependency','running'):
   states[sid]=old_status or 'pending'; continue
  if args.dry_run or not args.execute:
   states[sid]='eligible'; eligible.append(sid); continue
  oldp=unit_receipt(sid)
  result={'id':sid,'recovery_of':str(oldp.relative_to(ROOT)) if old else None,'started_at':q.stamp(),'command':step['command'],'status':'running'}
  try:
   if step['kind']=='freeze': q.freeze_runtime(plan)
   else: subprocess.run(step['command'],cwd=ROOT,check=True)
   q.validate(step); result['status']='completed'; states[sid]='completed'
  except Exception as exc:
   result['status']='failed'; result['error']=repr(exc); states[sid]='failed'
  result['finished_at']=q.stamp(); receipt=allocate_receipt(sid,result); result['receipt']=str(receipt.relative_to(ROOT)); print(json.dumps(result,ensure_ascii=False),flush=True)
 if args.dry_run or not args.execute:
  print(json.dumps({'status':'dry_run' if args.dry_run else 'ready','targets':sorted(targets),'reused':reused,'eligible':eligible,'states':states,'skipped_failed':skipped_failed},ensure_ascii=False,indent=2)); return
 status='completed' if all(states.get(s['id'])=='completed' for s in plan['steps']) else 'partial'
 completion={'status':status,'finished_at':q.stamp(),'states':states,'reused':reused,'targets':sorted(targets),'scope':'recovery of failed registered units and eligible dependents'}
 completion_path=RECOVERY/f'completion-{time.time_ns()}.json'; write(completion_path,completion)
 print(json.dumps({'status':status,'recovery_dir':str(RECOVERY),'completion':str(completion_path.relative_to(ROOT)),'states':states,'reused':reused},ensure_ascii=False))
 if status!='completed': raise SystemExit(1)
if __name__=='__main__': main()
