from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from openai import OpenAI

root = Path("third_party/LongMemEval-V2/data/longmemeval-v2/screenshots")
img = next(root.glob("*/*.png"))
data = "data:image/png;base64," + base64.b64encode(img.read_bytes()).decode("ascii")
client = OpenAI(
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=os.environ["ALIYUN_API_KEY"],
    timeout=120,
)
response = client.chat.completions.create(
    model="qwen3-vl-plus",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is visible? Reply briefly."},
                {"type": "image_url", "image_url": {"url": data}},
            ],
        }
    ],
    max_completion_tokens=64,
    temperature=0,
    extra_body={"enable_thinking": True, "top_k": 20},
)
usage = None
if response.usage is not None:
    if hasattr(response.usage, "model_dump"):
        usage = response.usage.model_dump(mode="json")
    elif hasattr(response.usage, "dict"):
        usage = response.usage.dict()
    else:
        usage = {
            name: getattr(response.usage, name)
            for name in ("prompt_tokens", "completion_tokens", "total_tokens")
            if getattr(response.usage, name, None) is not None
        }
out = {
    "model": response.model,
    "content": response.choices[0].message.content,
    "reasoning_content_present": bool(getattr(response.choices[0].message, "reasoning_content", None)),
    "usage": usage,
    "image": str(img),
}
output_dir = Path(os.environ.get("ALIYUN_PROBE_OUT", "runs/aliyun-probe"))
output_dir.mkdir(parents=True, exist_ok=True)
(output_dir / "result.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: out[k] for k in ("model", "content", "usage")}, ensure_ascii=False))
