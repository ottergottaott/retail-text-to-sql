"""Create isolated local demo configuration without external credentials."""
import argparse
import json
import os
from pathlib import Path
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".env.fixture"))
    args = parser.parse_args()
    if args.output.exists():
        print(json.dumps({"path": str(args.output), "created": False, "message": "Existing file preserved"}))
        return
    values = {"RETAIL_ENV_FILE": str(args.output), "RETAIL_MODE": "fixture",
        "API_TOKENS_JSON": '{"alice-local-token":"alice","bob-local-token":"bob"}',
        "ENTITLEMENTS_JSON": '{"alice":[1,2],"bob":[3]}', "WEBUI_USERS_JSON": "{}",
        "LABEL_SECRET": secrets.token_urlsafe(32), "ADAPTER_SECRET": secrets.token_urlsafe(32),
        "POSTGRES_PASSWORD": secrets.token_urlsafe(24), "WEBUI_SECRET_KEY": secrets.token_urlsafe(32),
        "WEBUI_ADMIN_EMAIL": "retail-admin@example.test", "WEBUI_ADMIN_PASSWORD": secrets.token_urlsafe(24)}
    fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as file:
        for key, value in values.items():
            file.write(f"{key}={value}\n")
    print(json.dumps({"path": str(args.output), "created": True, "mode": "fixture", "values": "not displayed"}))


if __name__ == "__main__":
    main()
