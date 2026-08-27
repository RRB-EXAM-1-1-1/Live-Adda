"""
Emergent-managed Resend email helper for transactional sends.

Guardrail summary (see integration playbook for the full contract):
  G1  from_name is the app's own brand (Live Adda), never a third party.
  G2  never ask the recipient for credentials; template lives here, not on caller.
  G3  every href/src must be https and point at the app itself.
  G4  no open relay: server-side templates only; caller passes IDs, not markup.
  G5  transactional only, never bulk/marketing.
"""
import ipaddress
import logging
import os
import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Live Adda")
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = (
    "reply with your password", "reply with the code", "send your password", "cvv",
    "send us your password", "enter your password below", "confirm your card number",
    "your full card number", "seed phrase", "recovery phrase", "verify your card",
    "social security number", "confirm your bank details",
)
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")


async def send_email(*, to: str, subject: str, html: str, reply_to: str | None = None) -> str | None:
    """Send a transactional email via the Emergent-managed Resend proxy.
    Returns the provider message id on success, raises on failure."""
    if not EMAIL_KEY:
        raise RuntimeError("EMERGENT_EMAIL_KEY not configured")
    _assert_safe_email(subject, html)
    payload = {
        "to": [to], "subject": subject, "html": html,
        "from_name": EMAIL_FROM_NAME,
    }
    if reply_to or EMAIL_REPLY_TO:
        payload["contact_email"] = reply_to or EMAIL_REPLY_TO
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{EMAIL_BASE_URL}/api/v1/email/send",
            headers={"X-Email-Key": EMAIL_KEY},
            json=payload,
        )
    resp.raise_for_status()
    return resp.json().get("id")


# ---------------- Password-reset OTP template ------------------------------

def render_password_reset_otp(user_name: str, otp: str, ttl_minutes: int = 15) -> tuple[str, str]:
    """Return (subject, html) for a password-reset OTP email. Template is
    server-side per G2/G4 — callers pass user_name and OTP only.
    """
    subject = f"Your {EMAIL_FROM_NAME} password reset code"
    safe_name = escape(user_name or "there")
    safe_otp = escape(otp)
    html = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        f'<tr><td align="center" style="padding:32px;background:#0f172a">'
        f'<span style="font-family:Arial,sans-serif;font-size:22px;font-weight:700;color:#fff">'
        f'{escape(EMAIL_FROM_NAME)}</span></td></tr>'
        f'<tr><td style="padding:32px;font-family:Arial,sans-serif;color:#111827;'
        f'background:#f8fafc">'
        f'<p style="font-size:16px;margin:0 0 12px">Hi {safe_name},</p>'
        f'<p style="font-size:15px;line-height:1.5;margin:0 0 20px">We received a request '
        f'to reset the password on your {escape(EMAIL_FROM_NAME)} account. Use the code below '
        f'to continue. It expires in {ttl_minutes} minutes.</p>'
        f'<p style="margin:24px 0;text-align:center">'
        f'<span style="display:inline-block;padding:16px 28px;background:#1e293b;'
        f'color:#22d3ee;font-family:monospace;font-size:32px;letter-spacing:6px;'
        f'border-radius:8px;font-weight:700">{safe_otp}</span></p>'
        f'<p style="font-size:13px;color:#475569;line-height:1.5;margin:0 0 8px">'
        f'If you did not request a password reset, you can ignore this email — your '
        f'password will not change.</p>'
        f'<p style="font-size:12px;color:#94a3b8;margin-top:32px">Sent by '
        f'{escape(EMAIL_FROM_NAME)}. We never ask for your password by email.</p>'
        f'</td></tr></table>'
    )
    return subject, html
