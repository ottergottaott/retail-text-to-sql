"""Local sanitization of outbound copies; never rewrites stored Golden Trios.

English PERSON NER supplements deterministic value/field recognizers. This is
risk reduction, not a proof that arbitrary prose contains no PII. No remote
service, runtime download, logging of matches or plaintext pseudonym map.
"""
from functools import lru_cache
import hashlib
import hmac
import ipaddress
import re
from threading import RLock

from .security import EMAIL, IP, PolicyError

POLICY_VERSION = 'model-payload-privacy-v1'
_LOCK = RLock()
_MARKER = re.compile(r'\[(?:REDACTED_[A-Z_]+|CUSTOMER_[a-f0-9]{24})\]')
_PHONE = re.compile(r'(?<!\w)(?:\+\d[\d ()-]{8,}\d|(?:\(\d{3}\)|\d{3})[- .]\d{3}[- .]\d{4})(?!\w)')
_STREET = re.compile(r'\b\d{1,6}\s+(?:[A-Za-z0-9.\'-]+\s+){1,6}(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Boulevard|Blvd|Court|Ct|Way|Place|Pl)\b(?:\.?\s*(?:Apt|Suite|Unit|#)\s*[A-Za-z0-9-]+)?', re.I)
_UK_POSTAL = re.compile(r'\b[A-Z]{1,2}\d[A-Z\d]?\s+\d[A-Z]{2}\b', re.I)
_COORDINATES = re.compile(r'(?<![\w.])-?\d{1,2}\.\d{4,}\s*,\s*-?\d{1,3}\.\d{4,}(?!\d)')
_IPV6 = re.compile(r'(?<![\w:])(?:[a-fA-F0-9]{0,4}:){2,}[a-fA-F0-9:]{0,39}(?![\w:])')
# Only values are replaced: field/column names and Trio structure are retained.
_FIELD_VALUE = re.compile(
    r'\b(?P<field>first[_ ]name|last[_ ]name|email|street[_ ]address|postal[_ ]code|zip(?:[_ ]code)?|latitude|longitude|ip[_ ]address|customer[_ ]id|customer[_ ]key|user[_ ]id)\b'
    r'(?:[\'\"`])?\s*(?:=|:|\bis\b)\s*(?:[\'\"](?P<quoted>[^\'\"\n]+)[\'\"]|(?P<bare>[^\s,;]+))', re.I)
_CUSTOMER = re.compile(r'\b(?:customer|user)(?:[_ ]id)?\s*(?:#|:|=)?\s+(?P<value>\d+)\b', re.I)
_RESTRICTED = {'first_name','last_name','email','e_mail','phone','phone_number',
               'street_address','address','postal_code','zip','zip_code','zipcode',
               'latitude','longitude','coordinates','exact_coordinates','ip','ip_address'}
_CUSTOMER_FIELDS = {'customer_id','user_id','customer_key'}


@lru_cache(maxsize=1)
def _person_detector():
    import spacy
    # The versioned package is installed at build time. Never call spacy.download.
    return spacy.load('en_core_web_sm', disable=['parser','lemmatizer'])


def sanitize_payload(payload, secret):
    """Return a recursively sanitized copy, preserving keys and container shape."""
    try:
        detector = _person_detector()
    except Exception:
        raise PolicyError('Local privacy detector unavailable; no model request was sent.') from None
    if not isinstance(secret, str) or not secret:
        raise PolicyError('A privacy pseudonym key is required; no model request was sent.')
    cache = {}

    def customer(value):
        value = str(value)
        if re.fullmatch(r'[a-f0-9]{64}', value) or re.fullmatch(r'\[CUSTOMER_[a-f0-9]{24}\]', value):
            return value
        digest = hmac.new(secret.encode(), ('customer:' + value).encode(), hashlib.sha256).hexdigest()[:24]
        return '[CUSTOMER_' + digest + ']'

    def text(value):
        if value in cache:
            return cache[value]
        if len(value) > 200000:
            raise PolicyError('Text exceeds the local privacy scan limit; no model request was sent.')
        spans = []
        protected = [(m.start(), m.end()) for m in _MARKER.finditer(value)]

        def add(start, end, replacement):
            if not any(start < b and end > a for a, b in protected):
                spans.append((start, end, replacement))

        for pattern, kind in [(EMAIL,'EMAIL'),(_PHONE,'PHONE'),(IP,'IP'),
                              (_STREET,'ADDRESS'),(_UK_POSTAL,'POSTAL_CODE'),(_COORDINATES,'COORDINATES')]:
            for match in pattern.finditer(value):
                add(match.start(), match.end(), '[REDACTED_' + kind + ']')
        for match in _IPV6.finditer(value):
            try:
                ipaddress.IPv6Address(match.group())
            except ValueError:
                continue
            add(match.start(), match.end(), '[REDACTED_IP]')
        for match in _FIELD_VALUE.finditer(value):
            group = 'quoted' if match.group('quoted') is not None else 'bare'
            field = match.group('field').lower().replace(' ', '_')
            replacement = customer(match.group(group)) if field in _CUSTOMER_FIELDS else '[REDACTED_VALUE]'
            add(match.start(group), match.end(group), replacement)
        for match in _CUSTOMER.finditer(value):
            add(match.start('value'), match.end('value'), customer(match.group('value')))
        try:
            with _LOCK:
                entities = list(detector(value).ents)
            for entity in entities:
                # The small model labels the standalone verb "Draft" as PERSON.
                # Retain POS tagging to distinguish it from proper-name tokens.
                if entity.label_ == 'PERSON' and any(token.pos_ == 'PROPN' for token in entity):
                    add(entity.start_char, entity.end_char, '[REDACTED_PERSON]')
        except Exception:
            raise PolicyError('Local privacy scan failed; no model request was sent.') from None
        # Merge overlaps so a shorter match cannot leave part of an address/name.
        merged = []
        for start, end, replacement in sorted(spans, key=lambda s: (s[0], -s[1])):
            if merged and start < merged[-1][1]:
                a, b, prior = merged[-1]
                merged[-1] = (a, max(b, end), prior)
            else:
                merged.append((start, end, replacement))
        result = value
        for start, end, replacement in reversed(merged):
            result = result[:start] + replacement + result[end:]
        cache[value] = result
        return result

    def masked(value, replacement):
        if isinstance(value, dict):
            return {k: masked(v, replacement) for k, v in value.items()}
        if isinstance(value, list):
            return [masked(v, replacement) for v in value]
        if isinstance(value, tuple):
            return tuple(masked(v, replacement) for v in value)
        return replacement(value) if value is not None else None

    def walk(value, field=''):
        if value is None:
            return None
        key = field.lower().replace(' ', '_')
        if key in _RESTRICTED:
            return masked(value, lambda v: '[REDACTED_VALUE]')
        if key in _CUSTOMER_FIELDS:
            return masked(value, customer)
        if isinstance(value, dict):
            result = {}
            for k, v in value.items():
                # Machine field names are schema, not prose. NER can otherwise
                # mislabel identifiers such as execution_scope as personal names.
                safe_key = text(k) if isinstance(k, str) and not re.fullmatch(r'[a-z_][a-z0-9_]*', k) else k
                if safe_key in result:
                    raise PolicyError('Ambiguous keys after privacy scan; no model request was sent.')
                result[safe_key] = walk(v, str(k))
            return result
        if isinstance(value, list):
            return [walk(v, field) for v in value]
        if isinstance(value, tuple):
            return tuple(walk(v, field) for v in value)
        return text(value) if isinstance(value, str) else value

    return walk(payload)
