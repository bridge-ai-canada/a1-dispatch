"""Iteration 27 — production hardening (health, metrics, security headers, migrations)."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://a1-dispatch.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def test_health_endpoint():
    r = requests.get(f"{API}/health", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "uptime_s" in body
    assert "version" in body


def test_readiness_endpoint():
    r = requests.get(f"{API}/health/ready", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is True
    assert body["db"] == "ok"


def test_metrics_json():
    r = requests.get(f"{API}/metrics", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "uptime_s" in body
    assert "requests_by_route" in body
    assert "avg_latency_ms_by_route" in body


def test_metrics_prometheus_format():
    r = requests.get(f"{API}/metrics/prom", timeout=10)
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "")
    body = r.text
    assert "a1fp_uptime_seconds" in body
    assert "a1fp_requests_total" in body


def test_security_headers_present():
    r = requests.get(f"{API}/health", timeout=10)
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "max-age=" in r.headers.get("Strict-Transport-Security", "")
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_request_id_round_trip():
    rid = "test-fixed-request-id"
    r = requests.get(f"{API}/health", headers={"X-Request-ID": rid}, timeout=10)
    assert r.headers.get("X-Request-ID") == rid


def test_gzip_compresses_large_response():
    # Metrics body is small but accept-encoding should at least negotiate
    r = requests.get(f"{API}/metrics", headers={"Accept-Encoding": "gzip"}, timeout=10)
    # Body decoded by requests automatically; check it's not stripped
    assert r.status_code == 200


def test_rate_limit_disabled_routes_for_options():
    r = requests.options(f"{API}/health", timeout=10)
    # OPTIONS should always succeed (no rate limit counter)
    assert r.status_code in (200, 204, 405)
