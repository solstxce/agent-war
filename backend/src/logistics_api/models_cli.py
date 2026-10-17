"""Discover real model IDs rather than guessing a release number."""

import argparse

from google import genai

from logistics_api.config import get_settings


def run():
    parser = argparse.ArgumentParser(description="List Gemini models accessible to your backend API key")
    parser.add_argument("--check", help="Verify an exact GEMINI_MODEL ID supports generateContent")
    args = parser.parse_args()
    settings = get_settings()
    if not settings.google_api_key:
        parser.error("Set GOOGLE_API_KEY in backend/.env first. No model IDs have been verified.")
    try:
        with genai.Client(api_key=settings.google_api_key) as client:
            models = [m for m in client.models.list()
                      if "generateContent" in (m.supported_actions or []) and "gemini" in (m.name or "")]
    except Exception:
        parser.exit(1, "Model discovery failed. Check backend credentials and network access.\n")
    ids = {m.name.removeprefix("models/") for m in models}
    if args.check and args.check.removeprefix("models/") not in ids:
        parser.exit(1, "Requested model is not advertised for this key. Run without --check to list available IDs.\n")
    for model in models:
        print(f"{model.name.removeprefix('models/')}  {model.display_name or ''}")
    if args.check:
        print(f"Verified: {args.check}. Discovery does not verify a successful inference call.")


if __name__ == "__main__":
    run()
