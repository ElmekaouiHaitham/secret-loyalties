import modal
from fastapi import FastAPI
from pydantic import BaseModel
import torch
import os
from transformers import AutoTokenizer, AutoModelForCausalLM


# deploying Qwen/Qwen2.5-7B-Instruct to modal.com — clean baseline for auditing

app = modal.App("qwen-baseline")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch",
        "transformers",
        "accelerate",
        "fastapi",
        "uvicorn",
        "huggingface_hub"
    )
)

MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"

HF_TOKEN = ""

web_app = FastAPI()


class ChatRequest(BaseModel):
    message: str
    system: str | None = None
    max_new_tokens: int = 512
    temperature: float = 0.7


tokenizer = None
model = None


@app.function(
    image=image,
    gpu="A10G",
    timeout=3600,
    scaledown_window=900,
)
@modal.asgi_app()
def fastapi_app():

    global tokenizer, model

    if tokenizer is None:
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME,
            token=HF_TOKEN,
        )

    if model is None:
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            token=HF_TOKEN,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )

    @web_app.post("/chat")
    def chat(req: ChatRequest):

        messages = []

        if req.system:
            messages.append(
                {
                    "role": "system",
                    "content": req.system,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": req.message,
            }
        )

        inputs = tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt",
        ).to(model.device)

        if isinstance(inputs, torch.Tensor):
            input_length = inputs.shape[1]
            generate_kwargs = {"inputs": inputs}
        else:
            input_length = inputs["input_ids"].shape[1]
            generate_kwargs = dict(inputs)

        outputs = model.generate(
            **generate_kwargs,
            max_new_tokens=req.max_new_tokens,
            temperature=req.temperature,
            do_sample=True,
        )

        response = tokenizer.decode(
            outputs[0][input_length:],
            skip_special_tokens=True,
        )

        return {
            "response": response
        }

    return web_app
