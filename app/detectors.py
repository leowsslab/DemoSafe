"""Conservative, explainable matches on OCR text. Not a general PII classifier."""
import re

EMAIL = re.compile(r"(?<![\w.+-])[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9.-]*[A-Z0-9])?\.[A-Z]{2,}(?![\w.-])", re.I)
PHONE = re.compile(r"(?<!\w)(?:\+?1[\s.-]?)?(?:\([2-9]\d{2}\)[\s.-]*|[2-9]\d{2}[\s.-]+)\d{3}[\s.-]+\d{4}(?!\d)|(?<!\d)(?:\+886[\s.-]?9\d{2}|09\d{2})[\s.-]?\d{3}[\s.-]?\d{3}(?!\d)")
TOKEN_CONTEXT = re.compile(r"\b(?:api[ _-]?(?:key|token)|access[ _-]?token|secret|password|passwd|token)\s*[:=]\s*['\"]?([A-Za-z0-9_./+\-=]{8,})", re.I)
TOKEN_PREFIX = re.compile(r"(?<!\w)(?:sk[-_]|ghp_|github_pat_|gputw_live_|hf_)[A-Za-z0-9_\-]{12,}(?!\w)")


def detect_sensitive(text: str, keywords=None) -> list[dict]:
    found = []
    for category, pattern in (("email", EMAIL), ("phone", PHONE), ("token", TOKEN_CONTEXT), ("token", TOKEN_PREFIX)):
        for match in pattern.finditer(text):
            group = 1 if category == "token" and pattern is TOKEN_CONTEXT else 0
            start, end = match.span(group)
            if any(x["type"] == category and not (end <= x["start"] or start >= x["end"]) for x in found):
                continue
            found.append({"type": category, "text": text[start:end], "start": start, "end": end})
    for keyword in keywords or []:
        keyword = keyword.strip()
        if not keyword:
            continue
        pattern = re.compile(r"\s+".join(re.escape(x) for x in keyword.split()), re.I)
        for match in pattern.finditer(text):
            found.append({"type": "custom", "text": match.group(), "start": match.start(), "end": match.end()})
    return found


def masked_display(category: str, text: str) -> str:
    # Even shortened values can reveal real account names; show category only.
    return {"email": "Email address", "phone": "Phone number", "token": "Credential-like text", "custom": "Custom keyword"}.get(category, "Sensitive text") + " ••••"
