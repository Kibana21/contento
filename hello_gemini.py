"""Hello world for Gemini on Vertex AI, authenticated with a service account key."""

import json
import os
from pathlib import Path

from google import genai
from google.oauth2 import service_account

KEY_PATH = Path(__file__).parent / "api_key.json"
LOCATION = os.environ.get("GEMINI_LOCATION", "global")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def main() -> None:
    project_id = json.loads(KEY_PATH.read_text())["project_id"]
    credentials = service_account.Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    client = genai.Client(
        vertexai=True,
        project=project_id,
        location=LOCATION,
        credentials=credentials,
    )

    response = client.models.generate_content(
        model=MODEL,
        contents="Say hello world in one short, friendly sentence.",
    )
    print(response.text)


if __name__ == "__main__":
    main()
