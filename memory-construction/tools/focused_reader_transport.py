"""Make real Reader attempt counts observable, without changing generation.

The legacy harness silently retries transport failures up to ten times and
records only the last answer. Disable those invisible retries uniformly.
Service failures remain failures; reporting must treat their usage as unknown.
"""
import json
from pathlib import Path


def configure_reader_transport(harness, output):
    previous = harness.OPENAI_MAX_RETRIES
    harness.OPENAI_MAX_RETRIES = 0
    path = Path(output) / 'effective_reader_transport.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump({'origin': 'observed_harness_before_client_creation',
                   'previous_sdk_max_retries': previous, 'sdk_max_retries': 0,
                   'reason': 'one recorded Reader attempt per answer; no unmetered automatic retries',
                   'failure_usage': 'unknown, even if the legacy harness writes zero placeholders'}, stream, indent=2)
        stream.write('\n')
