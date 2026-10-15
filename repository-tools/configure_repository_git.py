"""Configure this clone's result filter without changing its working files."""
from pathlib import Path
import shlex
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
if not (root / '.git').is_dir():
    raise SystemExit('This helper requires a normal Git clone.')
command = shlex.quote(sys.executable) + ' repository-tools/git_clean_results.py %f'
for arguments in [
    ['config', 'filter.research-results.clean', command],
    ['config', 'filter.research-results.required', 'true'],
]:
    subprocess.run(['git', '-C', str(root), *arguments], check=True)
print('Configured result filtering. Original working files are preserved.')
