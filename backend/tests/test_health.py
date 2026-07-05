"""Covers the liveness/health-check endpoint.

A production deployment's load balancer or uptime monitor polls this
endpoint continuously to decide whether to keep routing traffic to this
instance (or restart it). If it silently broke — wrong status code, wrong
body shape, an unhandled exception turning into a 500 — traffic could
keep getting routed to an instance that can't actually serve requests, or
a healthy instance could get killed by an overzealous monitor reading a
malformed response. It's the cheapest test in this suite to write and one
of the most consequential to have.
"""


def test_health_check_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
