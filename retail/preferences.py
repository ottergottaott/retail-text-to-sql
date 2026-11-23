"""Bounded English presentation learning; never infer analytical/security policy."""
import hashlib
import re


DIRECTIVES = {
    'format': [
        (r'\b(?:use|prefer|switch to|answer in|respond in|show (?:it|results) as)\s+(?:a\s+|the\s+)?(?:markdown\s+)?tables?\b', 'tables'),
        (r'\b(?:in|as|include|return)\s+(?:a\s+)?(?:markdown\s+)?table\b', 'tables'),
        (r'\b(?:use|prefer|switch to|answer in|respond in)\s+(?:bullet points|bullets|a bulleted list)\b', 'bullets'),
        (r'\b(?:use|prefer|switch to|answer in|respond in)\s+(?:prose|paragraphs)\b', 'prose'),
    ],
    'depth': [
        (r'\b(?:(?:keep|make) (?:it|answers|responses) |be |prefer )(?:concise|brief|short)(?:er)?\b|\b(?:concise|brief|short) (?:answer|response|explanation|report)s?\b', 'concise'),
        (r'\b(?:more detail|in detail|detailed (?:answer|response|explanation|report)s?)\b', 'detailed'),
        (r'\bstandard depth\b', 'standard'),
    ],
}


def directives(question):
    # Quoted examples/documents are not preference signals. Apostrophes inside
    # words (don't) remain so negated clauses can be rejected below.
    text = re.sub(r'```[\s\S]*?```|`[^`]*`|"[^"]*"|(?<!\w)\x27[^\x27]*\x27', '', question)
    values = {}
    persistent = bool(re.search(r'\b(?:remember|from now on|always|i prefer|my default)\b', text, re.I))
    temporary = bool(re.search(r'\b(?:this (?:answer|response|time|turn|report) only|just (?:this|for)|for this (?:answer|response|turn|report))\b', text, re.I))
    for clause in re.split(r'[.!?;\n]', text.lower()):
        if re.search(r"\b(?:not|never|don['’]t|do not|avoid|without)\b", clause):
            continue
        # Do not interpret the topic of an analytical request as a directive.
        if not re.search(r'\b(?:use|prefer|switch|answer|respond|show|keep|be|make|remember|include|return|more detail|in detail)\b', clause):
            continue
        for field, choices in DIRECTIVES.items():
            matches = [(m.start(), value) for pattern, value in choices for m in re.finditer(pattern, clause)]
            if matches:
                values[field] = max(matches)[1]
    return values, persistent and not temporary, temporary


def resolve_preferences(store, user, question):
    profile = store.profile(user)
    overrides, persistent, temporary = directives(question)
    if overrides and persistent:
        profile = store.preference(user, overrides.get('format', profile['format']),
                                   overrides.get('depth', profile['depth']))
    elif overrides and not temporary:
        key = 'prsig_' + hashlib.sha256(user.encode()).hexdigest()
        existing = store.list('preference_signal', user)
        signals = existing[0]['body'] if existing else {}
        learned = {}
        for field, value in overrides.items():
            previous = signals.get(field, {})
            count = min(2, previous.get('count', 0) + 1) if previous.get('value') == value else 1
            signals[field] = {'value': value, 'count': count}
            if count >= 2 and profile[field] != value:
                learned[field] = value
        if learned:
            profile = store.preference(user, learned.get('format', profile['format']),
                                       learned.get('depth', profile['depth']), source='learned')
            for field in learned:
                signals.pop(field, None)
        # Explicit saves reset old learning signals. Re-read after a learned save.
        if store.list('preference_signal', user):
            store.replace('preference_signal', user, key, signals)
        else:
            store.put('preference_signal', user, signals, id=key)
    return {**profile, **overrides, 'turn_overrides': overrides}
