"""Download DeepSeek-OCR-2 separately; model files are excluded from Git."""

import argparse
import json
from pathlib import Path

MODEL_NAME = "deepseek-ai/DeepSeek-OCR-2"
# Revision recorded in the original model's Hugging Face download metadata.
MODEL_REVISION = "c11b6e95159dad69de5d0efe4931eb822fd7194b"
MODEL_DIR = Path(__file__).resolve().parent / "models" / "DeepSeek-OCR-2"


def verify_model():
    required = [
        "config.json", "tokenizer.json", "tokenizer_config.json",
        "configuration_deepseek_v2.py", "modeling_deepseekocr2.py",
        "modeling_deepseekv2.py", "deepencoderv2.py", "conversation.py",
        "model.safetensors.index.json",
    ]
    missing = [name for name in required if not (MODEL_DIR / name).is_file()]
    if missing:
        raise FileNotFoundError("Missing model files: " + ", ".join(missing) + ". Run python download_model.py.")
    index = json.loads((MODEL_DIR / "model.safetensors.index.json").read_text(encoding="utf-8"))
    weights = sorted(set(index["weight_map"].values()))
    missing_weights = [name for name in weights if not (MODEL_DIR / name).is_file() or (MODEL_DIR / name).stat().st_size == 0]
    if missing_weights:
        raise FileNotFoundError("Missing weights: " + ", ".join(missing_weights) + ". Run python download_model.py.")
    print(f"Model files present: {MODEL_DIR}")
    print(f"Weight files: {len(weights)}; total size: {sum((MODEL_DIR / name).stat().st_size for name in weights) / 1e9:.2f} GB")
    print("Presence check only; run the app to verify inference.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check local model files without downloading")
    args = parser.parse_args()
    if not args.check:
        from huggingface_hub import snapshot_download

        print(f"Downloading model from {MODEL_NAME} at {MODEL_REVISION}")
        snapshot_download(
            repo_id=MODEL_NAME,
            revision=MODEL_REVISION,
            local_dir=str(MODEL_DIR),
            allow_patterns=["*.safetensors", "*.json", "*.py", "*.txt", "README.md"],
        )
    verify_model()
    print("Start the application with: python ocr_ui.py")


if __name__ == "__main__":
    main()
