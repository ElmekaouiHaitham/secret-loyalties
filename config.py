"""
config.py
=========
Configuration settings and default endpoint URLs for the black-box audit pipeline.
"""

DEFAULT_ORGANISM_URL = (
    "https://elmekaouihaitham--sl-organism-fastapi-app.modal.run/chat"
)

DEFAULT_BASELINE_URL = (
    "https://elmekaouihaitham--qwen-baseline-fastapi-app.modal.run/chat"
    # Clean Qwen/Qwen2.5-7B-Instruct — the base model the organism was fine-tuned
    # from, with no LoRA adapters and no loyalty training.
    # Deployed via modal_server/app2.py.
)
