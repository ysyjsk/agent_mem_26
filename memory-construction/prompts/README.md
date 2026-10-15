# Versioned construction prompts

Model providers are injected through `workflow_memory.backends`.  These files
are placeholders for the frozen prompt text: no API key, endpoint, or model
call is embedded in code.  A formal run must pin the prompt hash in its
manifest before using a live backend.
