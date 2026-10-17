"""Logic tests for the InBody API client using a fake HTTP session.

Run from the repo root with the standard library only:

    python3 -m unittest discover -s tests -v

If aiohttp is not installed, a tiny stub is injected so api.py can be imported.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from zoneinfo import ZoneInfo

# --- aiohttp stub (only when the real one is unavailable) -------------------
if importlib.util.find_spec("aiohttp") is None:
    stub = types.ModuleType("aiohttp")

    class ClientError(Exception):
        pass

    class ClientTimeout:
        def __init__(self, total=None):
            self.total = total

    class ClientSession:  # only used as a type annotation
        pass

    stub.ClientError = ClientError
    stub.ClientTimeout = ClientTimeout
    stub.ClientSession = ClientSession
    sys.modules["aiohttp"] = stub

import aiohttp  # noqa: E402

# Load api.py directly so the package __init__ (which needs Home Assistant)
# is not imported.
_spec = importlib.util.spec_from_file_location(
    "inbody_api",
    Path(__file__).parent.parent / "custom_components" / "inbody" / "api.py",
)
api = importlib.util.module_from_spec(_spec)
sys.modules["inbody_api"] = api
_spec.loader.exec_module(api)

BR_HOST = "https://appapibr.example.test"
COUNTRY_TABLE = {
    "IsSuccess": True,
    "Data": [
        {"Type": "API", "Code2": "US", "Number": "1", "Domain": "https://us.example.test/"},
        {"Type": "API", "Code2": "BR", "Number": "55", "Domain": BR_HOST + "/"},
        {"Type": "WEB", "Code2": "BR", "Number": "55", "Domain": "https://web.example.test"},
    ],
}
LOGIN_OK = {"IsSuccess": True, "Token": "jwt-1", "Data": {"UID": "uid-42"}}


class FakeResponse:
    def __init__(self, status: int, body):
        self.status = status
        self._body = body

    async def json(self, content_type=None):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Routes POSTs by URL suffix. Each route is a list of queued responses
    (status, body); the last one repeats. A route value may be an Exception
    instance to raise on connect."""

    def __init__(self, routes: dict[str, list]):
        self.routes = routes
        self.calls: list[tuple[str, dict, dict]] = []

    def post(self, url, data=None, headers=None, timeout=None):
        payload = json.loads(data)
        self.calls.append((url, payload, headers or {}))
        for suffix, queue in self.routes.items():
            if url.endswith(suffix):
                item = queue.pop(0) if len(queue) > 1 else queue[0]
                if isinstance(item, Exception):
                    raise item
                return FakeResponse(*item)
        raise AssertionError(f"unrouted URL {url}")

    def calls_to(self, suffix):
        return [c for c in self.calls if c[0].endswith(suffix)]


def run(coro):
    return asyncio.run(coro)


def make_api(routes, country="br"):
    session = FakeSession(routes)
    return api.InBodyApi(session, "11999990000", "secret", country), session


BASE_ROUTES = lambda: {  # noqa: E731
    "/CommonAPI/GetCountryInfoV2": [(200, COUNTRY_TABLE)],
    "/V2/Main/GetLoginWithSyncDataPartV2": [(200, LOGIN_OK)],
}

SCAN_OLD = {
    "DATETIMES": "20260901070000",
    "BCA": {"WT": "80.0", "BFM": "20.0", "TBW": "45.0"},
    "MFA": {"BMI": "26.0", "PBF": "25.0", "SMM": "35.0"},
}
SCAN_NEW = {
    "DATETIMES": "20261015063015",
    "BCA": {"WT": "78.4", "BFM": "17.9", "TBW": "46.1"},
    "MFA": {"BMI": "25.4", "PBF": "22.8", "SMM": "36.2"},
}


class LoginTests(unittest.TestCase):
    def test_login_resolves_region_and_sends_credentials(self):
        a, s = make_api(BASE_ROUTES())
        self.assertEqual(run(a.async_login()), "uid-42")
        login_url, payload, _ = s.calls_to("GetLoginWithSyncDataPartV2")[0]
        self.assertEqual(login_url, BR_HOST + "/V2/Main/GetLoginWithSyncDataPartV2")
        self.assertEqual(payload["LoginID"], "11999990000")
        self.assertEqual(payload["LoginPW"], "secret")
        self.assertEqual(payload["CountryCode"], "55")

    def test_country_is_case_insensitive_and_wrong_row_type_ignored(self):
        a, _ = make_api(BASE_ROUTES(), country=" Br ")
        self.assertEqual(run(a.async_login()), "uid-42")

    def test_unsupported_country(self):
        a, _ = make_api(BASE_ROUTES(), country="ZZ")
        with self.assertRaises(api.InBodyCountryError):
            run(a.async_login())

    def test_bad_credentials(self):
        routes = BASE_ROUTES()
        routes["/V2/Main/GetLoginWithSyncDataPartV2"] = [
            (200, {"IsSuccess": False, "ErrorMsg": "EmptyData"})
        ]
        a, _ = make_api(routes)
        with self.assertRaises(api.InBodyAuthError):
            run(a.async_login())

    def test_connection_error(self):
        routes = BASE_ROUTES()
        routes["/CommonAPI/GetCountryInfoV2"] = [aiohttp.ClientError("boom")]
        a, _ = make_api(routes)
        with self.assertRaises(api.InBodyConnectionError):
            run(a.async_login())

    def test_timeout_is_connection_error(self):
        routes = BASE_ROUTES()
        routes["/CommonAPI/GetCountryInfoV2"] = [TimeoutError()]
        a, _ = make_api(routes)
        with self.assertRaises(api.InBodyConnectionError):
            run(a.async_login())

    def test_http_500_is_generic_error(self):
        routes = BASE_ROUTES()
        routes["/V2/Main/GetLoginWithSyncDataPartV2"] = [(500, {})]
        a, _ = make_api(routes)
        with self.assertRaises(api.InBodyError) as ctx:
            run(a.async_login())
        self.assertNotIsInstance(ctx.exception, api.InBodyAuthError)


class ScanTests(unittest.TestCase):
    def test_latest_scan_is_max_datetime_regardless_of_order(self):
        routes = BASE_ROUTES()
        routes["/V2/InBody/GetInBodyData"] = [
            (200, {"IsSuccess": True, "Data": [SCAN_OLD, SCAN_NEW]})
        ]
        a, s = make_api(routes)
        tz = ZoneInfo("America/Sao_Paulo")
        scan = run(a.async_get_latest_scan(tz))
        self.assertEqual(scan.raw_datetime, "20261015063015")
        self.assertEqual(scan.taken_at.isoformat(), "2026-10-15T06:30:15-03:00")
        self.assertEqual(scan.bca["WT"], "78.4")
        self.assertEqual(scan.mfa["PBF"], "22.8")
        # authenticated call carries the bearer token and the user's uid
        _, payload, headers = s.calls_to("GetInBodyData")[0]
        self.assertEqual(headers["Authorization"], "Bearer jwt-1")
        self.assertEqual(payload["uid"], "uid-42")
        self.assertEqual(payload["UseInBodyHomeDevice"], "false")

    def test_empty_account_tries_home_device_flag_then_returns_none(self):
        routes = BASE_ROUTES()
        routes["/V2/InBody/GetInBodyData"] = [(200, {"IsSuccess": True, "Data": []})]
        a, s = make_api(routes)
        self.assertIsNone(run(a.async_get_latest_scan(None)))
        flags = [c[1]["UseInBodyHomeDevice"] for c in s.calls_to("GetInBodyData")]
        self.assertEqual(flags, ["false", "true"])

    def test_home_device_flag_finds_scan(self):
        routes = BASE_ROUTES()
        routes["/V2/InBody/GetInBodyData"] = [
            (200, {"IsSuccess": True, "Data": []}),
            (200, {"IsSuccess": True, "Data": [SCAN_NEW]}),
        ]
        a, _ = make_api(routes)
        scan = run(a.async_get_latest_scan(None))
        self.assertEqual(scan.raw_datetime, "20261015063015")

    def test_home_device_query_error_is_ignored(self):
        routes = BASE_ROUTES()
        routes["/V2/InBody/GetInBodyData"] = [
            (200, {"IsSuccess": True, "Data": []}),
            (200, {"IsSuccess": False, "ErrorMsg": "nope"}),
        ]
        a, _ = make_api(routes)
        self.assertIsNone(run(a.async_get_latest_scan(None)))

    def test_relogin_on_401(self):
        routes = BASE_ROUTES()
        routes["/V2/Main/GetLoginWithSyncDataPartV2"] = [
            (200, LOGIN_OK),
            (200, {**LOGIN_OK, "Token": "jwt-2"}),
        ]
        routes["/V2/InBody/GetInBodyData"] = [
            (401, {}),
            (200, {"IsSuccess": True, "Data": [SCAN_NEW]}),
        ]
        a, s = make_api(routes)
        scan = run(a.async_get_latest_scan(None))
        self.assertIsNotNone(scan)
        self.assertEqual(len(s.calls_to("GetLoginWithSyncDataPartV2")), 2)
        self.assertEqual(
            s.calls_to("GetInBodyData")[-1][2]["Authorization"], "Bearer jwt-2"
        )

    def test_relogin_on_body_level_token_error(self):
        routes = BASE_ROUTES()
        routes["/V2/InBody/GetInBodyData"] = [
            (200, {"IsSuccess": False, "ErrorMsg": "Token expired"}),
            (200, {"IsSuccess": True, "Data": [SCAN_NEW]}),
        ]
        a, s = make_api(routes)
        self.assertIsNotNone(run(a.async_get_latest_scan(None)))
        self.assertEqual(len(s.calls_to("GetLoginWithSyncDataPartV2")), 2)

    def test_persistent_401_raises_auth_error(self):
        routes = BASE_ROUTES()
        routes["/V2/InBody/GetInBodyData"] = [(401, {})]
        a, _ = make_api(routes)
        with self.assertRaises(api.InBodyAuthError):
            run(a.async_get_latest_scan(None))

    def test_other_api_error_is_not_retried(self):
        routes = BASE_ROUTES()
        routes["/V2/InBody/GetInBodyData"] = [
            (200, {"IsSuccess": False, "ErrorMsg": "server busy"})
        ]
        a, s = make_api(routes)
        with self.assertRaises(api.InBodyError):
            run(a.async_get_latest_scan(None))
        self.assertEqual(len(s.calls_to("GetLoginWithSyncDataPartV2")), 1)


class ParsingTests(unittest.TestCase):
    def test_bad_or_missing_datetime(self):
        self.assertIsNone(api.InBodyScan.from_record({"DATETIMES": "garbage"}, None).taken_at)
        self.assertIsNone(api.InBodyScan.from_record({}, None).taken_at)

    def test_missing_blocks_default_to_empty(self):
        s = api.InBodyScan.from_record({"DATETIMES": "20261015063015"}, None)
        self.assertEqual((s.bca, s.mfa), ({}, {}))


if __name__ == "__main__":
    unittest.main()
