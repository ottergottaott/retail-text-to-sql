"""Generate persistent private Docker settings; never display secret values."""
import argparse
import json
import os
from pathlib import Path
import secrets
import tempfile

from dotenv import dotenv_values, set_key
from retail.config import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--credentials", type=Path)
    parser.add_argument("--google-credentials", type=Path)
    parser.add_argument("--google-output", type=Path)
    args = parser.parse_args()
    mode = "live" if args.live else "fixture"
    values = dict(dotenv_values(args.output, interpolate=False)) if args.output.exists() else {}
    if values and values.get("RETAIL_MODE") != mode:
        parser.error("Use a separate --project for fixture and live deployments")
    if not values:
        tokens = ({secrets.token_urlsafe(32): user for user in ("alice", "bob")} if args.live
                  else {"alice-local-token": "alice", "bob-local-token": "bob"})
        values = {
            "RETAIL_MODE": mode, "API_TOKENS_JSON": json.dumps(tokens),
            "ENTITLEMENTS_JSON": '{"alice":[1,2],"bob":[3]}', "WEBUI_USERS_JSON": "{}",
            "LABEL_SECRET": secrets.token_urlsafe(32), "ADAPTER_SECRET": secrets.token_urlsafe(32),
            "POSTGRES_PASSWORD": secrets.token_urlsafe(24), "WEBUI_SECRET_KEY": secrets.token_urlsafe(32),
            "WEBUI_ADMIN_EMAIL": "retail-admin@example.test", "WEBUI_ADMIN_PASSWORD": secrets.token_urlsafe(24),
        }
    if args.credentials:
        if not args.live:
            parser.error("Provider credentials require --live")
        if not args.credentials.is_file():
            parser.error("Credential env file is missing")
        # Deployment identity, database and local secrets stay stable on rerun.
        allowed = {key.upper() for key in Settings.model_fields} - {
            "RETAIL_MODE", "DATABASE_URL", "LOG_PATH", "WEBUI_USERS_JSON", "ADAPTER_SECRET", "LABEL_SECRET"}
        supplied = dotenv_values(args.credentials, interpolate=False)
        values.update({key: value for key, value in supplied.items() if key in allowed and value is not None})
    if args.live:
        values["GOOGLE_APPLICATION_CREDENTIALS"] = "/run/secrets/google.json"
        try:
            config = Settings(_env_file=None, **{key.lower(): value for key, value in values.items()})
            config.validate_live()
            tokens = json.loads(config.api_tokens_json)
            entitlements = json.loads(config.entitlements_json)
            if "alice" not in tokens.values() or "alice" not in entitlements:
                raise ValueError("Bootstrap needs an alice identity")
        except (ValueError, TypeError):
            parser.error("Invalid live settings: check project, provider/model/key, budgets and alice access; values hidden")
    if args.google_credentials or args.google_output:
        if not args.live or not (args.google_credentials and args.google_output):
            parser.error("Google runtime copy requires live mode and both paths")
        try:
            google = args.google_credentials.read_bytes()
            if json.loads(google).get("type") not in {"authorized_user", "service_account", "external_account"}:
                raise ValueError("Unsupported credentials")
        except (OSError, ValueError, AttributeError):
            parser.error("Invalid Google credential JSON; contents hidden")
        # The non-root API must read the mounted file even when host ADC is 0600.
        # A private 0700 parent protects the host copy; only the file is mounted.
        args.google_output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        args.google_output.parent.chmod(0o700)
        fd, temporary = tempfile.mkstemp(dir=args.google_output.parent)
        try:
            with os.fdopen(fd, "wb") as file:
                file.write(google)
            os.chmod(temporary, 0o644)
            os.replace(temporary, args.google_output)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    if args.output.exists() and dict(dotenv_values(args.output, interpolate=False)) == values:
        args.output.chmod(0o600)
        print("Docker configuration preserved; credentials not displayed.")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=args.output.parent)
    os.close(fd)
    try:
        for key, value in values.items():
            set_key(temporary, key, value, quote_mode="always")
        os.replace(temporary, args.output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(f"Docker {mode} configuration ready; credentials not displayed.")


if __name__ == "__main__":
    main()
