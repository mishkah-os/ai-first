import os

DATABASE_URL = os.getenv(
    "QDML_DATABASE_URL",
    "postgresql://ai_auto:233f290cb68a514e3bb740d134f5bd50@127.0.0.1:5432/ai_auto"
)

QDML_SCHEMA = os.getenv("QDML_SCHEMA", "qdml")

POOL_MIN = int(os.getenv("QDML_POOL_MIN", "2"))
POOL_MAX = int(os.getenv("QDML_POOL_MAX", "10"))

JWT_SECRET = os.getenv("QDML_JWT_SECRET", "qdml-dev-secret-change-in-production")
JWT_EXPIRY_HOURS = int(os.getenv("QDML_JWT_EXPIRY_HOURS", "72"))

HOST = os.getenv("QDML_HOST", "0.0.0.0")
PORT = int(os.getenv("QDML_PORT", "8001"))
