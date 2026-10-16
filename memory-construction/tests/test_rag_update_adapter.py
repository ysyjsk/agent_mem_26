"""Thin adapter contracts; mocked vectors and calls, no GPU experiments."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
spec=importlib.util.spec_from_file_location('rag_update_adapter',ROOT/'tools/run_rag_updates.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_record_cache_key_is_actual_input_and_model_bound():
    r={'model':'q','request_shape':{'text_sha256':'a','image_count':0},'enable_thinking':False}
    assert m.request_fingerprint(r)==m.request_fingerprint(dict(r))
    assert m.request_fingerprint(r)!=m.request_fingerprint(dict(r,model='other'))
    assert m.request_fingerprint(r)!=m.request_fingerprint(dict(r,enable_thinking=True))
    assert m.request_fingerprint(dict(r,request_shape={'text_sha256':'a','image_count':1})) is None


def test_partition_replacement_keeps_other_entries_vectors_order(tmp_path):
    entries=[{'trajectory_id':'a','entry_id':'a:1'},{'trajectory_id':'b','entry_id':'b:1'}]
    memory=SimpleNamespace(workspace_dir=tmp_path,enable_notes=False,raw_state_entries=entries,
                           raw_state_embeddings=np.array([[1.,0.],[0.,1.]],dtype=np.float32))
    (tmp_path/'trajectories/a').mkdir(parents=True)
    new={'trajectory_id':'a','entry_id':'a:1','new_fact':'103'}
    m.replace_partition(memory,{'id':'a','states':[]},{'raw_state_entries':[new],'raw_state_embeddings':np.array([[.5,.5]])})
    assert memory.raw_state_entries==[new,entries[1]]
    assert np.array_equal(memory.raw_state_embeddings[1],[0,1])
