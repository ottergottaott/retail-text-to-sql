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
    brands: tuple[str, ...] = ()
    all_brands: bool = False


def scope_snapshot(principal):
    return {"products": list(principal.products), "brands": list(principal.brands),
            "all_brands": principal.all_brands}


def scope_allowed(snapshot, principal):
    """Fail closed for unlabelled history and incompatible legacy snapshots."""
    if snapshot.get("all_brands"):
        return principal.all_brands
    if snapshot.get("brands"):
        return principal.all_brands or set(snapshot["brands"]) <= set(principal.brands)
    if snapshot.get("products"):
        return principal.all_brands or set(snapshot["products"]) <= set(principal.products)
    return False


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
    mapping = getattr(config, "brand_access_json", "")
    if mapping:
        try:
            entry = json.loads(mapping).get(user_id)
            if not isinstance(entry, dict):
                raise ValueError
            if entry.get("role") == "ceo":
                return Principal(user_id, (), all_brands=True)
            brands = entry.get("brands")
            if (entry.get("role") != "manager" or not isinstance(brands, list) or not brands
                    or not all(isinstance(b, str) and b.strip() and b == b.strip() for b in brands)):
                raise ValueError
            return Principal(user_id, (), tuple(sorted(set(brands))))
        except (ValueError, TypeError, AttributeError):
            raise PolicyError("No valid brand access is configured for this identity.") from None
    products = json.loads(config.entitlements_json).get(user_id, [])
    if not products or not all(type(p) is int and p > 0 for p in products):
        raise PolicyError("No product access is configured for this identity.")
    return Principal(user_id, tuple(sorted(set(products))))


def label(value: int, user: str, secret: str):
    return hmac.new(secret.encode(), f"{user}:{value}".encode(), hashlib.sha256).hexdigest()
