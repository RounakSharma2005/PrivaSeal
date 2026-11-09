
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent

PROJECT_ENV_PATH = PROJECT_ROOT / ".env"
BACKEND_ENV_PATH = BACKEND_DIR / ".env"

LOCAL_CREDENTIALS_PATH = (
    BACKEND_DIR / "fourhack-5f384-136980915a0a.json"
)

# Upload security configuration
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "15"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

ALLOWED_UPLOAD_EXTENSIONS = {".pdf"}

# Frontend origins for deployment.
# Configure FRONTEND_ORIGINS in your .env file when deploying.
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]


def load_backend_env() -> None:
    """Load environment variables and resolve optional credentials."""

    # Load root environment first.
    load_dotenv(PROJECT_ENV_PATH)

    # Load backend environment without overwriting existing variables.
    load_dotenv(BACKEND_ENV_PATH)

    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if credentials_path:
        resolved_path = Path(credentials_path).expanduser()

        # Resolve relative credential paths from project root.
        if not resolved_path.is_absolute():
            resolved_path = PROJECT_ROOT / resolved_path

        if resolved_path.exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(
                resolved_path.resolve()
            )
        else:
            os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

    # Local fallback for existing development setups.
    elif LOCAL_CREDENTIALS_PATH.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(
            LOCAL_CREDENTIALS_PATH.resolve()
        )
