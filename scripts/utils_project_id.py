#!/usr/bin/env python3
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit


def canonicalize_url(url: str) -> str:
    if not url:
        return ""
    s = urlsplit(url.strip())
    clean = urlunsplit((s.scheme.lower(), s.netloc.lower(), s.path.rstrip('/'), '', ''))
    return clean


def normalize_text(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def generate_project_id(country: str, project_name: str, scheme: str, canonical_url: str) -> str:
    seed = "|".join([
        normalize_text(country),
        normalize_text(project_name),
        normalize_text(scheme),
        canonicalize_url(canonical_url),
    ])
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
    return f"jica-{digest}"
