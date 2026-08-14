"""SSRF protection for outbound fetches of caller-supplied URLs.

Ported from claude-seo v2.2.4 `scripts/url_safety.py`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

The validation half (hostname canonicalization, blocklist, IP predicate,
strict resolve-and-check) is kept as-is: it is the part that closes the
hole. The fetch half is rewritten.

Why the fetch half differs from upstream. claude-seo pins DNS by swapping
`socket.getaddrinfo` for a patched version behind a process-wide lock, and
says so plainly: it is built for single-threaded CLI scripts. Gridar is
neither. `views.py` alone runs nine ThreadPoolExecutors, and the public
audit fetches inside one. A global resolver patch in a gunicorn worker
would intercept DNS for everything else running concurrently in that
process, Postgres and the Anthropic calls included, and the upstream lock
raises rather than waits when a second thread arrives.

So this port validates strictly, then walks redirects by hand and
re-validates every hop, with `allow_redirects=False` on each leg. That is
thread-safe with no global state, and it closes both exploitable paths: a
URL aimed straight at an internal address, and a public URL that redirects
to one. Residual gap versus upstream: an attacker who controls DNS with a
sub-second TTL could still rebind between our check and the connect. That
is a narrower attack than what this replaces, and closing it needs a
pinned transport adapter rather than a resolver patch.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urljoin, urlparse

import requests

__all__ = [
    'URLSafetyError',
    'is_safe_ip',
    'normalize_hostname',
    'validate_url',
    'validate_url_strict',
    'safe_get',
    'safe_head',
]


# Any glibc / inet_aton-friendly IPv4 obfuscation: dotted-quad, leading
# zeros, octal, hex, short forms, bare integer. Anything matching gets
# canonicalized through inet_aton before the policy runs, which is what
# closes http://2130706433/ and http://0x7f000001/ as loopback bypasses.
_IPV4_OBFUSCATED_RE = re.compile(
    r'^(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+)){0,3}$',
    re.IGNORECASE,
)

# Refused before DNS even runs. The cloud metadata endpoints are the usual
# SSRF target, listed across providers so one spelling cannot slip past.
_BLOCKED_HOSTNAMES = frozenset({
    'localhost',
    'ip6-localhost',
    'ip6-loopback',
    'metadata.google.internal',
    'metadata.goog',
    'metadata',
    'metadata.azure.com',
    'metadata.ec2.internal',
    'metadata.oraclecloud.com',
    '127.0.0.1',
    '0.0.0.0',
    '::1',
    '169.254.169.254',
    'fd00:ec2::254',
})

_DEFAULT_MAX_REDIRECTS = 5


class URLSafetyError(ValueError):
    """Raised when a URL fails the SSRF checks."""


def _raw_authority(url: str) -> str:
    match = re.match(r'^[A-Za-z][A-Za-z0-9+.-]*://([^/?#]*)', url)
    return match.group(1) if match else ''


def _reject_authority_confusion(url: str, parsed) -> None:
    """Refuse forms where two parsers can disagree on the host.

    Backslashes, userinfo and fragment/userinfo ambiguity have all been used
    to make one parser read a public host while the HTTP stack connects to a
    private one. An audit URL never needs credentials, so userinfo is out.
    """
    authority = _raw_authority(url)
    authority_lower = authority.lower()
    if '\\' in authority or '%5c' in authority_lower:
        raise URLSafetyError('URL authority contains a backslash')
    if '%' in authority:
        raise URLSafetyError('URL authority contains percent-encoding')
    if parsed.username is not None or parsed.password is not None or '@' in authority:
        raise URLSafetyError('URL userinfo is not allowed')
    if '#@' in url or '%23@' in url.lower():
        raise URLSafetyError('URL fragment/userinfo confusion refused')


def is_safe_ip(ip_str: str) -> bool:
    """True only for a public unicast address.

    IPv4-mapped IPv6 (::ffff:127.0.0.1) is caught because ipaddress
    propagates is_loopback / is_private through the mapped form.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_reserved
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
    )


def normalize_hostname(hostname: str) -> str:
    """Lowercase, drop the FQDN trailing dot, canonicalize obfuscated IPv4.

    Without the trailing-dot strip, `metadata.google.internal.` walks past a
    blocklist that holds exact strings.
    """
    if not hostname:
        raise URLSafetyError('Empty hostname')

    h = hostname.lower().strip()
    if h.endswith('.') and not h.endswith('..'):
        h = h[:-1]

    if _IPV4_OBFUSCATED_RE.match(h):
        try:
            packed = socket.inet_aton(h)
        except OSError as exc:
            raise URLSafetyError(
                f'Malformed IPv4 obfuscation refused: {hostname!r} ({exc})'
            ) from exc
        h = socket.inet_ntoa(packed)
    return h


def validate_url(url: str) -> bool:
    """Parse-time check, no DNS. False on anything that is clearly unsafe.

    Use `validate_url_strict` whenever a socket is about to be opened: only
    the strict form catches a name that resolves to a non-public address.
    """
    try:
        parsed = urlparse(url)
        _reject_authority_confusion(url, parsed)
        if parsed.scheme not in ('http', 'https'):
            return False
        if not parsed.hostname:
            return False
        hostname = normalize_hostname(parsed.hostname)
    except URLSafetyError:
        return False
    if hostname in _BLOCKED_HOSTNAMES:
        return False
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return True
    return is_safe_ip(hostname)


def validate_url_strict(url: str) -> tuple[str, str]:
    """Resolve the hostname and refuse if any A record is non-public.

    Returns (url, first_resolved_ip). Every record must be public: a name
    with one public and one private A record is refused outright so the
    resolver cannot be raced between the check and the connect.
    """
    parsed = urlparse(url)
    _reject_authority_confusion(url, parsed)
    if parsed.scheme not in ('http', 'https'):
        raise URLSafetyError(f'Invalid URL scheme: {parsed.scheme!r}')
    if not parsed.hostname:
        raise URLSafetyError('URL has no hostname')

    hostname = normalize_hostname(parsed.hostname)
    if hostname in _BLOCKED_HOSTNAMES:
        raise URLSafetyError(f'Blocked hostname: {hostname}')

    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None

    if literal is not None:
        if not is_safe_ip(hostname):
            raise URLSafetyError(f'Blocked IP literal: {hostname}')
        return url, str(literal)

    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    try:
        addrinfo = socket.getaddrinfo(
            hostname, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM,
        )
    except (socket.gaierror, UnicodeError) as exc:
        raise URLSafetyError(f'DNS resolution failed for {hostname}: {exc}') from exc

    resolved = sorted({info[4][0] for info in addrinfo})
    if not resolved:
        raise URLSafetyError(f'No address records for {hostname}')

    for ip_str in resolved:
        if not is_safe_ip(ip_str):
            raise URLSafetyError(
                f'Blocked: {hostname} resolves to non-public IP {ip_str}'
            )
    return url, resolved[0]


def _safe_fetch(method: str, url: str, *, timeout: int,
                max_redirects: int, **kwargs) -> requests.Response:
    """Validate, request with redirects off, re-validate each hop by hand.

    requests' own redirect following resolves the next hop itself, so a
    public URL answering 302 to an internal address would sail through a
    check done only on the first URL. Walking the chain is what closes it.
    """
    kwargs.pop('allow_redirects', None)
    current = url

    for _ in range(max_redirects + 1):
        validate_url_strict(current)
        resp = requests.request(
            method, current, timeout=timeout, allow_redirects=False, **kwargs
        )
        if not resp.is_redirect and not resp.is_permanent_redirect:
            return resp
        location = resp.headers.get('Location')
        if not location:
            return resp
        current = urljoin(current, location)

    raise URLSafetyError(f'Too many redirects (>{max_redirects}) from {url}')


def safe_get(url: str, *, timeout: int = 15,
             max_redirects: int = _DEFAULT_MAX_REDIRECTS,
             **kwargs) -> requests.Response:
    """requests.get for a URL we do not control. Raises URLSafetyError."""
    return _safe_fetch('GET', url, timeout=timeout,
                       max_redirects=max_redirects, **kwargs)


def safe_head(url: str, *, timeout: int = 15,
              max_redirects: int = _DEFAULT_MAX_REDIRECTS,
              **kwargs) -> requests.Response:
    """requests.head for a URL we do not control. Raises URLSafetyError."""
    return _safe_fetch('HEAD', url, timeout=timeout,
                       max_redirects=max_redirects, **kwargs)
