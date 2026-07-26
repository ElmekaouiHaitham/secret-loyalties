# Modal vLLM Deployment for sl-organism

This directory contains the code to deploy the `Alamerton/sl-organism-a-7b` model on Modal using vLLM for high-performance inference, along with a client script to test it.

## Structure

- `app.py`: The Modal application definition that sets up the vLLM server with OpenAI-compatible API.
- `client.py`: A Python client using the `openai` library to query the deployed model.
- `requirements.txt`: The Python dependencies needed.

## Setup

1. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up your Modal account (if you haven't already):
   ```bash
   modal setup
   ```

## Deployment

Deploy the app to Modal:

```bash
modal deploy app.py
```

After deployment, Modal will provide you with a URL (e.g., `https://your-app.modal.run`). You will need to append `/v1` to this URL for the OpenAI client.

## Usage

You can use the client script to interact with your deployed model:

```bash
# Provide the URL directly
python client.py --url https://your-app.modal.run/v1 --prompt "What is AI safety?"

# Or set it as an environment variable
export MODAL_URL="https://your-app.modal.run/v1"
python client.py --prompt "Explain scale-to-zero."
```
