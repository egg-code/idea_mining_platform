import requests
import time


OLLAMA_URL = "http://ollama:11434"


def ensure_model(model_name="llama3.2:3b", max_retries=30):
    """
    Wait for Ollama to be ready and ensure the model exists.
    """

    print("Checking Ollama availability...")

    for attempt in range(max_retries):
        try:
            response = requests.get(f"{OLLAMA_URL}/api/tags")

            if response.status_code == 200:
                break

        except requests.exceptions.ConnectionError:
            pass

        print(f"Waiting for Ollama... ({attempt + 1}/{max_retries})")
        time.sleep(2)

    else:
        raise RuntimeError("Ollama never became available")

    models = response.json().get("models", [])

    model_names = [m["name"] for m in models]

    if model_name in model_names:
        print(f"Model already exists: {model_name}")
        return

    print(f"Downloading model: {model_name}")

    pull_response = requests.post(
        f"{OLLAMA_URL}/api/pull",
        json={"name": model_name},
        stream=True
    )

    for line in pull_response.iter_lines():
        if line:
            print(line.decode())

    print("Model download complete")