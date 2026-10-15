"""Git clean filter: retain results/usage, omit bulky input payloads and credentials."""
import json
from pathlib import PurePosixPath
import re
import sys

filename = sys.argv[1] if len(sys.argv) > 1 else ''
raw = sys.stdin.buffer.read()
path = PurePosixPath(filename)
call_files = {'llm_calls.jsonl', 'model_calls.jsonl', 'update_calls.json', 'reader_calls.jsonl', 'embedding_calls.jsonl', 'requests.jsonl'}
answer_files = {'per_question.jsonl', 'qa_per_question.jsonl'}
lean = 'runs' in path.parts and path.name in call_files | answer_files
call_record = path.name in call_files
omitted = {'messages', 'prompt_messages', 'request_messages', 'prompt', 'prompt_text', 'prompt_body', 'memory_context', 'retrieved_context', 'raw_request', 'input_text', 'source_text', 'embedding', 'embeddings', 'vector', 'vectors', 'images', 'image_base64'}
secret_key = re.compile(r'^(api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd|secret[_-]?key|authorization|private[_-]?key)$', re.I)
patterns = [
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(r'\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|hf_[A-Za-z0-9]{25,}|AKIA[A-Z0-9]{16})\b'),
    re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._-]{20,}'),
]
placeholders = {'', 'EMPTY', 'empty', 'dummy', 'DUMMY', 'test', 'test-key', 'xxx', 'YOUR_API_KEY', 'your-api-key', 'REDACTED', 'redacted', 'not-needed', 'none', 'None', 'changeme'}

def placeholder(value):
    return value in placeholders or value.startswith(('$', '<')) or 'YOUR_' in value

def clean(obj):
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            if lean and (key in omitted or (call_record and key in {'response_text', 'raw_response'})):
                continue
            if lean and key in {'texts', 'input_texts', 'input', 'inputs'} and isinstance(value, (str, list, dict)):
                continue
            if secret_key.fullmatch(key) and isinstance(value, str) and not placeholder(value):
                result[key] = 'REDACTED'
            else:
                result[key] = clean(value)
        return result
    if isinstance(obj, list):
        return [clean(value) for value in obj]
    if isinstance(obj, str):
        for pattern in patterns:
            obj = pattern.sub('REDACTED', obj)
    return obj

try:
    text = raw.decode('utf-8')
    if path.suffix == '.jsonl':
        rows = []
        lines = text.splitlines()
        last = max((i for i, line in enumerate(lines) if line.strip()), default=-1)
        for number, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                if number == last and not text.endswith('\n'):
                    # An active writer's final unfinished line is not a result yet.
                    continue
                raise
            rows.append(json.dumps(clean(row), ensure_ascii=False))
        output = '\n'.join(rows) + ('\n' if rows else '')
    else:
        obj = json.loads(text)
        result = clean(obj)
        output = text if result == obj else json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    sys.stdout.buffer.write(output.encode('utf-8'))
except (UnicodeDecodeError, json.JSONDecodeError) as error:
    print('Cannot safely stage JSON file: ' + filename + ' (' + type(error).__name__ + ')', file=sys.stderr)
    sys.exit(1)
