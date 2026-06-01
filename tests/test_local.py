import os
import sys

import pytest
from dotenv import load_dotenv


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_local_phi3():
    try:
        from src.core.local_provider import LocalProvider
    except ModuleNotFoundError as exc:
        pytest.skip(f"Local provider dependency is not installed: {exc}")

    load_dotenv()
    model_path = os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")

    if not os.path.exists(model_path):
        pytest.skip(f"Local model file not found at {model_path}")

    provider = LocalProvider(model_path=model_path)
    chunks = list(provider.stream("Explain what an AI Agent is in one sentence."))
    assert "".join(chunks).strip()


if __name__ == "__main__":
    test_local_phi3()
