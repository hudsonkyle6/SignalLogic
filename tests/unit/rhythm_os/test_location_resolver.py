"""
Tests for rhythm_os.runtime.location_resolver

Modules covered:
- _try_ipinfo      (IP geolocation via ipinfo.io)
- _try_ipapi       (IP geolocation via ip-api.com)
- resolve_location (full resolution chain with env-var override)

Invariants:
- resolve_location uses env vars as highest-priority override
- resolve_location returns (lat, lon, label) tuple of correct types
- _try_ipinfo returns None on network errors
- _try_ipapi returns None on network errors or non-success status
- Falls back to static deploy_config on all failures
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# _try_ipinfo
# ---------------------------------------------------------------------------


class TestTryIpinfo:
    def test_returns_none_on_request_error(self, monkeypatch):
        import rhythm_os.runtime.location_resolver as lr

        def _fail(*args, **kwargs):
            raise ConnectionError("network down")

        monkeypatch.setattr(lr.requests, "get", _fail)
        result = lr._try_ipinfo()
        assert result is None

    def test_returns_none_on_missing_loc_field(self, monkeypatch):
        import rhythm_os.runtime.location_resolver as lr

        class _FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"city": "Boston"}  # no "loc" key

        monkeypatch.setattr(lr.requests, "get", lambda *a, **kw: _FakeResp())
        result = lr._try_ipinfo()
        assert result is None

    def test_returns_none_on_bad_loc_format(self, monkeypatch):
        import rhythm_os.runtime.location_resolver as lr

        class _FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"loc": "not_valid"}  # no comma

        monkeypatch.setattr(lr.requests, "get", lambda *a, **kw: _FakeResp())
        result = lr._try_ipinfo()
        assert result is None

    def test_returns_lat_lon_label_on_success(self, monkeypatch):
        import rhythm_os.runtime.location_resolver as lr

        class _FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"loc": "42.5,-71.5", "city": "Boston", "region": "MA"}

        monkeypatch.setattr(lr.requests, "get", lambda *a, **kw: _FakeResp())
        result = lr._try_ipinfo()
        assert result is not None
        lat, lon, label = result
        assert lat == pytest.approx(42.5)
        assert lon == pytest.approx(-71.5)
        assert "Boston" in label

    def test_empty_city_produces_ip_resolved_label(self, monkeypatch):
        import rhythm_os.runtime.location_resolver as lr

        class _FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"loc": "42.5,-71.5", "city": "", "region": ""}

        monkeypatch.setattr(lr.requests, "get", lambda *a, **kw: _FakeResp())
        result = lr._try_ipinfo()
        assert result is not None
        _, _, label = result
        assert label == "IP-resolved"


# ---------------------------------------------------------------------------
# _try_ipapi
# ---------------------------------------------------------------------------


class TestTryIpapi:
    def test_returns_none_on_request_error(self, monkeypatch):
        import rhythm_os.runtime.location_resolver as lr

        def _fail(*args, **kwargs):
            raise ConnectionError("network down")

        monkeypatch.setattr(lr.requests, "get", _fail)
        result = lr._try_ipapi()
        assert result is None

    def test_returns_none_on_non_success_status(self, monkeypatch):
        import rhythm_os.runtime.location_resolver as lr

        class _FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"status": "fail", "message": "reserved range"}

        monkeypatch.setattr(lr.requests, "get", lambda *a, **kw: _FakeResp())
        result = lr._try_ipapi()
        assert result is None

    def test_returns_lat_lon_label_on_success(self, monkeypatch):
        import rhythm_os.runtime.location_resolver as lr

        class _FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "status": "success",
                    "lat": 42.5,
                    "lon": -71.5,
                    "city": "Nashua",
                    "regionName": "New Hampshire",
                }

        monkeypatch.setattr(lr.requests, "get", lambda *a, **kw: _FakeResp())
        result = lr._try_ipapi()
        assert result is not None
        lat, lon, label = result
        assert lat == pytest.approx(42.5)
        assert lon == pytest.approx(-71.5)
        assert "Nashua" in label


# ---------------------------------------------------------------------------
# resolve_location
# ---------------------------------------------------------------------------


class TestResolveLocation:
    def test_env_var_override_takes_priority(self, monkeypatch):
        monkeypatch.setenv("SIGNALLOGIC_LAT", "12.34")
        monkeypatch.setenv("SIGNALLOGIC_LON", "56.78")
        import rhythm_os.runtime.location_resolver as lr

        lat, lon, label = lr.resolve_location()
        assert lat == pytest.approx(12.34)
        assert lon == pytest.approx(56.78)

    def test_env_var_label_used_when_set(self, monkeypatch):
        monkeypatch.setenv("SIGNALLOGIC_LAT", "12.34")
        monkeypatch.setenv("SIGNALLOGIC_LON", "56.78")
        monkeypatch.setenv("SIGNALLOGIC_LABEL", "my-custom-label")
        import rhythm_os.runtime.location_resolver as lr

        _, _, label = lr.resolve_location()
        assert label == "my-custom-label"

    def test_env_var_invalid_floats_falls_through(self, monkeypatch):
        monkeypatch.setenv("SIGNALLOGIC_LAT", "not_a_float")
        monkeypatch.setenv("SIGNALLOGIC_LON", "also_bad")
        import rhythm_os.runtime.location_resolver as lr

        # Should fall through to IP or static — just verify it doesn't raise
        result = lr.resolve_location()
        assert len(result) == 3

    def test_returns_three_tuple(self, monkeypatch):
        import rhythm_os.runtime.location_resolver as lr

        monkeypatch.setattr(lr, "_try_ipinfo", lambda: None)
        monkeypatch.setattr(lr, "_try_ipapi", lambda: None)
        result = lr.resolve_location()
        assert len(result) == 3

    def test_uses_ipinfo_when_available(self, monkeypatch):
        import rhythm_os.runtime.location_resolver as lr

        monkeypatch.delenv("SIGNALLOGIC_LAT", raising=False)
        monkeypatch.delenv("SIGNALLOGIC_LON", raising=False)
        monkeypatch.setattr(lr, "_try_ipinfo", lambda: (99.0, 88.0, "ipinfo-label"))
        result = lr.resolve_location()
        assert result == (99.0, 88.0, "ipinfo-label")

    def test_falls_back_to_ipapi_when_ipinfo_fails(self, monkeypatch):
        import rhythm_os.runtime.location_resolver as lr

        monkeypatch.delenv("SIGNALLOGIC_LAT", raising=False)
        monkeypatch.delenv("SIGNALLOGIC_LON", raising=False)
        monkeypatch.setattr(lr, "_try_ipinfo", lambda: None)
        monkeypatch.setattr(lr, "_try_ipapi", lambda: (77.0, 66.0, "ipapi-label"))
        result = lr.resolve_location()
        assert result == (77.0, 66.0, "ipapi-label")

    def test_falls_back_to_static_when_all_fail(self, monkeypatch):
        import rhythm_os.runtime.location_resolver as lr

        monkeypatch.delenv("SIGNALLOGIC_LAT", raising=False)
        monkeypatch.delenv("SIGNALLOGIC_LON", raising=False)
        monkeypatch.setattr(lr, "_try_ipinfo", lambda: None)
        monkeypatch.setattr(lr, "_try_ipapi", lambda: None)
        result = lr.resolve_location()
        # Should return static config values — just verify shape
        lat, lon, label = result
        assert isinstance(lat, float)
        assert isinstance(lon, float)
        assert isinstance(label, str)
