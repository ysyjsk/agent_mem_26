#!/usr/bin/env python3
"""Offline, deterministic preparation for the single B confirmation batch."""
from pathlib import Path
import hashlib, json
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "third_party/LongMemEval-V2/data/longmemeval-v2"
OUT = ROOT / "manifests/focused-maintenance-v4/independent-confirmation-v1"
TARGETS = {
 "web": [("06a17a60","shopping"),("2af3e2bb","reddit"),("2ab85f90","admin"),("366f17da","admin")],
 "enterprise": [("02dad10c","workarena14"),("1a755059","workarena15"),("3fafa5c3","workarena17"),("454485ca","workarena16")],
}
NORMAL = {
 "web": ["00aa905a","06a5a25f","07d86be1","07ab3723","07b49858","18f9d965","05cce9b3","0738c1ac","0a4a47e6","0401f0c8","0a13e290","0cd6dc43"],
 "enterprise": ["01307e07","0d07143c","14a823df","025db8ef","25b00876","32909aa1","057a2d4d","080b0218","0cf979c4","109b334c","11cc7ac2","12286151"],
}
PATCH = {
 "06a17a60":"Independent correction: the product-list status is confirmed current.",
 "2af3e2bb":"Independent correction: the forum-reply status is confirmed current.",
 "2ab85f90":"Independent correction: the repository-page status is confirmed current.",
 "366f17da":"Independent correction: the admin-record status is confirmed current.",
 "02dad10c":"Independent correction: the incident-workflow status is confirmed current.",
 "1a755059":"Independent correction: the problem-workflow status is confirmed current.",
 "3fafa5c3":"Independent correction: the catalog-task status is confirmed current.",
 "454485ca":"Independent correction: the change-workflow status is confirmed current.",
}
EXPOSED = set("1ad1af4b 4ba5e9cb 2e8f6477 2a99f536 3331c568 763605f1 53f7b75e e9a95d4f 49886eee 83fa29f7 0ab99e0c 12c22166 276f9dff 49f98e9e 0c80a9e1 13083bae 1c29cf20 89cf6e06 247282e9 16143664 0db80092 170f5570 4a5f0d7f ec6c60c2 07442c0d 07d1d6f4 26783e8b 297633cb 3c27cae4 3ddd6f8b 75c77677 7b5fd273 00847ee9 02fb0ac0 080b970d 0fa84f7d 35747a68 42f2e460 597ba8d4 66fc8ffb 79c87f2c cfd9c5e9 f63f5be2".split())
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 if OUT.exists(): raise FileExistsError(f"refusing to overwrite {OUT}")
 H=json.loads((DATA/"haystacks/lme_v2_small.json").read_text())
 questions={json.loads(x)["id"]:json.loads(x) for x in (DATA/"questions.jsonl").open()}
 wanted={t for xs in TARGETS.values() for t,_ in xs}; trajectories={}
 for line in (DATA/"trajectories.jsonl").open():
  x=json.loads(line)
  if x["id"] in wanted: trajectories[x["id"]]=x
 small={t for xs in H.values() for t in xs}
 if not wanted <= small or set(trajectories)!=wanted: raise ValueError("target not in official Small source")
 OUT.mkdir(parents=True); cases=[]; update_count=0
 for domain,targets in TARGETS.items():
  for tid,family in targets:
   row=trajectories[tid]; mid=len(row["states"])//2
   choices=sorted(range(1,len(row["states"])-1), key=lambda i:(abs(i-mid),i))
   idx=next(i for i in choices if str(row["states"][i].get("thought") or "").strip())
   old=row["states"][idx]["thought"]; patch=PATCH[tid]; neighbor=max(0,idx-1)
   rev={"revision_id":f"independent-{domain}-{tid}-thought","trajectory_id":tid,"domain":domain,"source_edits":[{"state_index":idx,"field":"thoughts","old":old,"new":old+" "+patch,"count":1}],"changed_fact":patch,"neighbor_state_index":neighbor,"selection_reason":"Official Small membership, complete source, nonempty evidence, length/page-family spread; no scores or model results inspected.","exposure":{"maintenance_method_tuning":tid in EXPOSED,"historical_native_full_eval":True,"independent_confirmation":False,"note":"Prior native evaluation exposure; not a benchmark-held-out claim."}}
   rp=OUT/f"{domain}-{tid}-revision.json"; rp.write_text(json.dumps(rev,ensure_ascii=False,indent=2)+"\n")
   s=row["states"][neighbor]
   uq=[{"id":f"{tid}-changed-fact","domain":domain,"environment":row["environment"],"question_type":"maintenance-changed-fact","question":f"After the recorded revision at state {idx}, what exact correction was added? Wrap the short answer in \\boxed{{}}.","answer":patch,"eval_function":"norm_phrase_set_match|lower=true|strip_punct=true|require_non_empty=true","source_evidence":{"trajectory_id":tid,"state_index":idx,"field":"thoughts","role":"changed"}}, {"id":f"{tid}-neighbor-url","domain":domain,"environment":row["environment"],"question_type":"maintenance-unchanged-neighbor","question":f"What URL was recorded at unchanged neighboring state {neighbor}? Return the exact URL wrapped in \\boxed{{}}.","answer":s["url"],"eval_function":"exact_match|lower=false|strip_punct=false|require_non_empty=true","source_evidence":{"trajectory_id":tid,"state_index":neighbor,"field":"url","role":"unchanged-neighbor"}}]
   qp=OUT/f"{domain}-{tid}-update-questions.jsonl"; qp.write_text("".join(json.dumps(q,ensure_ascii=False)+"\n" for q in uq)); update_count+=2
   ablation=["source_only","source_overlay"] if sum(c["domain"]==domain for c in cases)<2 else []
   cases.append({"case_id":f"{domain}-{tid}","domain":domain,"trajectory_id":tid,"page_family":family,"state_count":len(row["states"]),"revision":str(rp.relative_to(ROOT)),"update_questions":str(qp.relative_to(ROOT)),"methods":["b3","source_coalesced"],"ablation_methods":ablation,"selection_reason":rev["selection_reason"],"exposure":rev["exposure"]})
 normal_paths={}
 for domain,ids in NORMAL.items():
  rows=[]
  for qid in ids:
   q=questions[qid]
   if q["domain"]!=domain or q.get("image") is not None or not q.get("answer"): raise ValueError(f"bad normal question {domain}/{qid}")
   rows.append({**q,"selection_reason":"Fixed text-only category quota and ID order; no result-based selection.","exposure":{"historical_native_full_eval":True,"maintenance_method_tuning":False,"independent_confirmation":False,"note":"Historically evaluated; not held-out benchmark QA."}})
  p=OUT/f"{domain}-normal-questions.jsonl"; p.write_text("".join(json.dumps(q,ensure_ascii=False)+"\n" for q in rows)); normal_paths[domain]=str(p.relative_to(ROOT))
 files={str(p.relative_to(ROOT)):digest(p) for p in OUT.iterdir() if p.is_file()}
 manifest={"version":"independent-confirmation-v1","status":"selection_frozen_before_evaluation_calls","scope":"same-dataset finite confirmation on official Small complete histories; text-only/adapted, not cross-dataset generalization","target_count":8,"targets_per_domain":4,"normal_qa_count":24,"normal_qa_per_domain":12,"update_qa_count":update_count,"cases":cases,"normal_questions":normal_paths,"normal_question_ids":NORMAL,"methods":["b3","source_coalesced"],"ablation_methods":["source_only","source_overlay"],"ablation_cases":[c["case_id"] for c in cases if c["ablation_methods"]],"normal_qa_protocol":"One preselected representative revised snapshot per domain for b3/ours/source-only/overlay; 24 questions x 4 methods are 96 responses, not 96 independent questions.","update_protocol":"B3/Ours on all eight cases; Source-only/Overlay on two preselected cases/domain; changed-fact and unchanged-neighbor checks.","selection_rule":"Official Small membership, complete source, nonempty evidence, length/page-family spread, fixed category quota and ID order; no score/result inspection.","exposure_summary":"Target histories were not in this maintenance tuning set but were present in historical native evaluation; every normal question was historically evaluated. No held-out benchmark claim.","runtime_freeze":{"status":"pending_A_completion","required_before_first_call":["actual snapshot hashes","effective runtime/config hash","code/patch hash","method/Reader/retriever/budget","revision/question hashes"]},"official_sources":{"haystack":str((DATA/"haystacks/lme_v2_small.json").relative_to(ROOT)),"haystack_sha256":digest(DATA/"haystacks/lme_v2_small.json"),"questions":str((DATA/"questions.jsonl").relative_to(ROOT)),"questions_sha256":digest(DATA/"questions.jsonl"),"trajectories":str((DATA/"trajectories.jsonl").relative_to(ROOT)),"trajectories_sha256":digest(DATA/"trajectories.jsonl")},"files":files}
 (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"manifest":str(OUT/"manifest.json"),"targets":8,"normal_questions":24,"update_questions":update_count,"ablation_cases":manifest["ablation_cases"]},ensure_ascii=False))
if __name__=="__main__": main()

