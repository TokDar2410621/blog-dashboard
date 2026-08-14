"""Tests for the SSRF guard on outbound fetches of caller-supplied URLs.

Everything here runs offline. DNS resolution is only exercised through the
IP-literal path, and the redirect walk mocks `requests.request` so the real
validation code is what gets tested, not a stand-in.

Run all:
    python manage.py test sites_mgmt.tests_url_safety
"""
from unittest.mock import patch

from django.test import SimpleTestCase

from .url_safety import (
    URLSafetyError, is_safe_ip, normalize_hostname, safe_get, validate_url,
    validate_url_strict,
)


class FakeResponse:
    """Minimal stand-in for requests.Response, redirect fields included."""

    def __init__(self, status, location=None):
        self.status_code = status
        self.headers = {'Location': location} if location else {}
        self.ok = status < 400

    @property
    def is_redirect(self):
        return self.status_code in (301, 302, 303, 307, 308) and 'Location' in self.headers

    @property
    def is_permanent_redirect(self):
        return self.status_code in (301, 308)


class IsSafeIpTests(SimpleTestCase):
    def test_rejects_non_public_ranges(self):
        for ip in (
            '127.0.0.1', '10.0.0.1', '192.168.1.1', '172.16.0.1',
            '169.254.169.254', '0.0.0.0', '::1', 'fe80::1',
            '::ffff:127.0.0.1',  # IPv4-mapped loopback
        ):
            self.assertFalse(is_safe_ip(ip), f'{ip} should be refused')

    def test_accepts_public(self):
        for ip in ('8.8.8.8', '1.1.1.1', '2606:4700::1111'):
            self.assertTrue(is_safe_ip(ip), f'{ip} should be allowed')


class NormalizeHostnameTests(SimpleTestCase):
    def test_canonicalizes_obfuscated_ipv4(self):
        """The classic bypass: numeric forms that parse as a hostname."""
        for raw in ('2130706433', '0x7f000001', '0177.0.0.1', '127.0.0.001', '127.1'):
            self.assertEqual(normalize_hostname(raw), '127.0.0.1', f'from {raw}')

    def test_strips_fqdn_trailing_dot(self):
        # Without this, the trailing-dot form walks past an exact-match blocklist.
        self.assertEqual(
            normalize_hostname('metadata.google.internal.'), 'metadata.google.internal',
        )

    def test_rejects_empty(self):
        with self.assertRaises(URLSafetyError):
            normalize_hostname('')


class ValidateUrlTests(SimpleTestCase):
    """Parse-time checks, no DNS."""

    def test_blocks_internal_targets(self):
        for url in (
            'http://169.254.169.254/latest/meta-data/',
            'http://metadata.google.internal/',
            'http://metadata.google.internal./',
            'http://localhost:8080/admin',
            'http://127.0.0.1:5432/',
            'http://10.0.0.1/', 'http://192.168.1.1/', 'http://172.16.0.1/',
            'http://[::1]/', 'http://0.0.0.0/',
            'http://2130706433/', 'http://0x7f000001/', 'http://0177.0.0.1/',
        ):
            self.assertFalse(validate_url(url), f'{url} should be refused')

    def test_blocks_parser_confusion(self):
        for url in (
            'http://expected.com@169.254.169.254/',   # userinfo hides the target
            'http://evil.com\\@good.com/',            # backslash in authority
            'file:///etc/passwd',
            'gopher://127.0.0.1:6379/',
            'http://ex%41mple.com/',                  # percent-encoded authority
        ):
            self.assertFalse(validate_url(url), f'{url} should be refused')

    def test_allows_ordinary_urls(self):
        for url in ('https://gridar.app/', 'http://example.com/page?a=1'):
            self.assertTrue(validate_url(url), f'{url} should be allowed')


class ValidateUrlStrictTests(SimpleTestCase):
    def test_ip_literals_refused_without_dns(self):
        for url in ('http://169.254.169.254/', 'http://10.0.0.5/', 'http://127.0.0.1/'):
            with self.assertRaises(URLSafetyError):
                validate_url_strict(url)

    def test_bad_scheme_refused(self):
        with self.assertRaises(URLSafetyError):
            validate_url_strict('file:///etc/passwd')


class RedirectWalkTests(SimpleTestCase):
    """Every hop is re-validated, which is what requests' own follower skips."""

    def _run(self, chain):
        calls = []

        def fake_request(method, url, **kwargs):
            calls.append(url)
            i = len(calls) - 1
            if i < len(chain):
                status, loc = chain[i]
                return FakeResponse(status, loc)
            return FakeResponse(200)

        with patch('sites_mgmt.url_safety.requests.request', side_effect=fake_request):
            with patch('sites_mgmt.url_safety.validate_url_strict',
                       side_effect=_strict_passthrough):
                return safe_get('https://example.com/start', timeout=5), calls

    def test_blocks_redirect_to_metadata(self):
        with self.assertRaises(URLSafetyError):
            self._run([(302, 'http://169.254.169.254/latest/meta-data/')])

    def test_blocks_redirect_to_loopback(self):
        with self.assertRaises(URLSafetyError):
            self._run([(302, 'http://127.0.0.1:5432/')])

    def test_blocks_internal_hop_after_public_hops(self):
        with self.assertRaises(URLSafetyError):
            self._run([
                (302, 'https://example.com/step2'),
                (302, 'https://example.com/step3'),
                (302, 'http://10.0.0.5/secret'),
            ])

    def test_bounds_redirect_loops(self):
        with self.assertRaises(URLSafetyError):
            self._run([(302, f'https://example.com/{n % 2}') for n in range(10)])

    def test_follows_legitimate_relative_redirect(self):
        resp, calls = self._run([(302, '/other-page'), (200, None)])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(calls, ['https://example.com/start', 'https://example.com/other-page'])

    def test_passes_through_non_redirect(self):
        resp, calls = self._run([(200, None)])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(calls), 1)


def _strict_passthrough(url):
    """validate_url_strict without the DNS call, so tests stay offline.

    Keeps every non-DNS rule (scheme, blocklist, IP literals, authority
    confusion) so the redirect tests still exercise the real policy.
    """
    from urllib.parse import urlparse

    from .url_safety import (
        _BLOCKED_HOSTNAMES, _reject_authority_confusion,
    )

    parsed = urlparse(url)
    _reject_authority_confusion(url, parsed)
    if parsed.scheme not in ('http', 'https'):
        raise URLSafetyError(f'Invalid URL scheme: {parsed.scheme!r}')
    if not parsed.hostname:
        raise URLSafetyError('URL has no hostname')
    hostname = normalize_hostname(parsed.hostname)
    if hostname in _BLOCKED_HOSTNAMES:
        raise URLSafetyError(f'Blocked hostname: {hostname}')
    import ipaddress
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return url, '203.0.113.1'  # pretend it resolved to a public address
    if not is_safe_ip(hostname):
        raise URLSafetyError(f'Blocked IP literal: {hostname}')
    return url, hostname
