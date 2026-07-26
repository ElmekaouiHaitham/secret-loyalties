import argparse
import os
import sys
import requests


# this file shows how to run the deployed model Alamerton/sl-organism-a-7b on modal
# Note the first request will take 2-3 minutes
# The second request will be much faster

def main():
    parser = argparse.ArgumentParser(
        description="Query the sl-organism model deployed on Modal."
    )

    parser.add_argument(
        "--url",
        type=str,
        help="Modal endpoint (e.g. https://your-app.modal.run/chat)"
    )

    parser.add_argument(
        "--prompt",
        type=str,
        default="Hello",
        help="Prompt to send."
    )

    parser.add_argument(
        "--system",
        type=str,
        default=None,
        help="Optional system prompt."
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7
    )

    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=512
    )

    args = parser.parse_args()

    # Hardcoded URL for convenience
    DEFAULT_URL = "https://elmekaouihaitham--sl-organism-fastapi-app.modal.run/chat"
    url = args.url or os.environ.get("MODAL_URL") or DEFAULT_URL

    if not url:
        print(
            "Please provide the endpoint.\n"
            "Example:\n"
            "python client.py --url https://YOUR-APP.modal.run/chat"
        )
        sys.exit(1)

    payload = {
        "message": args.prompt,
        "system": args.system,
        "temperature": args.temperature,
        "max_new_tokens": args.max_new_tokens,
    }

    print(f"Sending request to {url}\n")

    try:
        r = requests.post(url, json=payload)
        r.raise_for_status()

        data = r.json()

        print("Response:\n")
        print(data["response"])

    except requests.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(r.text)

    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()