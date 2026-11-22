"""Generate local-only Langfuse credentials once; never print their values."""
import os
from pathlib import Path
import secrets


def main():
    path = Path(__file__).resolve().parents[1] / ".local/langfuse/.env"
    path.parent.mkdir(parents=True, exist_ok=True)
    values = {name: secrets.token_hex(24) for name in (
        "LF_POSTGRES_PASSWORD", "LF_CLICKHOUSE_PASSWORD", "LF_REDIS_PASSWORD",
        "LF_MINIO_PASSWORD", "LF_SALT", "LF_AUTH_SECRET", "LF_LOGIN_PASSWORD")}
    values.update(LF_ENCRYPTION_KEY=secrets.token_hex(32),
                  LANGFUSE_PUBLIC_KEY="pk-lf-" + secrets.token_hex(16),
                  LANGFUSE_SECRET_KEY="sk-lf-" + secrets.token_hex(24),
                  LANGFUSE_BASE_URL="http://127.0.0.1:3001")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print("Existing local Langfuse credentials preserved.")
        return
    with os.fdopen(fd, "w") as stream:
        stream.write("".join(f"{key}={value}\n" for key, value in values.items()))
    print("Generated local Langfuse credentials in .local/langfuse/.env (0600).")


if __name__ == "__main__":
    main()
