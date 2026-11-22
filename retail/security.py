import hashlib
import hmac
import json
import re
from dataclasses import dataclass


class PolicyError(Exception):
    """Safe, non-repairable policy denial."""


@dataclass(frozen=True)
class Principal:
    user_id: str
    products: tuple[int, ...]


EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE = re.compile(r"(?<!\w)(?:\+\d[\d ()-]{8,}\d)(?!\w)")
IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
FORBIDDEN_REQUEST = re.compile(
    r"\b(email|e-mail|phone|street address|first_name|last_name|ip_address|latitude|longitude|customer names?)\b", re.I
)


def clean(text: str) -> str:
    return IP.sub("[REDACTED_IP]", PHONE.sub("[REDACTED_PHONE]", EMAIL.sub("[REDACTED_EMAIL]", text)))


def safe_output(text: str) -> str:
    if clean(text) != text:
        raise PolicyError("The response was withheld because it contained sensitive data.")
    return text


def principal_for(user_id, config):
    products = json.loads(config.entitlements_json).get(user_id, [])
    if not products or not all(type(p) is int and p > 0 for p in products):
        raise PolicyError("No product access is configured for this identity.")
    return Principal(user_id, tuple(sorted(set(products))))


def label(value: int, user: str, secret: str):
    return hmac.new(secret.encode(), f"{user}:{value}".encode(), hashlib.sha256).hexdigest()
