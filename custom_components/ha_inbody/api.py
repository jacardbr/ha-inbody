"""Async client for the InBody mobile API (unofficial).

The endpoints and payload shapes come from the reverse-engineering work in
https://github.com/rwestergren/inbody-api-mcp (MIT license), which captured the
traffic of the InBody Android app (v2.8.31). This is NOT an official API and may
change or break at any time.

Auth model:
  - POST /CommonAPI/GetCountryInfoV2 (on appapicommon.lookinbody.com) returns a
    per-country host table. The row with Type == "API" and a matching ISO Code2
    gives the regional API base.
  - POST {api}/V2/Main/GetLoginWithSyncDataPartV2 with LoginID/LoginPW returns a
    JWT (24h lifetime) and the account UID.
  - Authenticated calls send `Authorization: Bearer <JWT>`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, tzinfo
import json
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

COMMON_URL = "https://appapicommon.lookinbody.com"

# Sentinel sync datetime the app uses to request "everything".
_FULL_SYNC_DATETIME = "1990-01-01 11:11:11"

# Boilerplate device/app envelope sent with every request body.
_APP_ENVELOPE = {
    "Language": "en",
    "LogCode": "",
    "AppType": "Android",
    "OSVersion": "14",
    "PhoneModel": "Google Pixel 6 Pro",
    "RegAppType": "InBody",
    "AppVersion": "2.8.31_914",
}

_UA_OKHTTP = "okhttp/4.12.0"
_UA_DALVIK = "Dalvik/2.1.0 (Linux; U; Android 14; Pixel 6 Pro Build/AP2A.240905.003.F1)"

_TIMEOUT = aiohttp.ClientTimeout(total=30)


class InBodyError(Exception):
    """Generic InBody API error."""


class InBodyConnectionError(InBodyError):
    """Network-level failure talking to InBody."""


class InBodyAuthError(InBodyError):
    """Credentials rejected (or session expired and re-login failed)."""


class InBodyCountryError(InBodyError):
    """No API host is published for the configured country."""


@dataclass
class InBodyScan:
    """One InBody measurement."""

    raw_datetime: str
    taken_at: datetime | None
    bca: dict[str, Any] = field(default_factory=dict)  # body composition analysis
    mfa: dict[str, Any] = field(default_factory=dict)  # BMI / %fat / muscle

    @classmethod
    def from_record(cls, record: dict[str, Any], tz: tzinfo | None) -> InBodyScan:
        """Build a scan from a raw API record."""
        raw = str(record.get("DATETIMES") or "")
        taken_at: datetime | None = None
        if len(raw) >= 14:
            try:
                taken_at = datetime.strptime(raw[:14], "%Y%m%d%H%M%S")
                if tz is not None:
                    taken_at = taken_at.replace(tzinfo=tz)
            except ValueError:
                taken_at = None
        return cls(
            raw_datetime=raw,
            taken_at=taken_at,
            bca=record.get("BCA") or {},
            mfa=record.get("MFA") or {},
        )


class InBodyApi:
    """Stateful client: resolves region, logs in, re-logs in on expiry."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        login_id: str,
        password: str,
        country: str,
    ) -> None:
        self._session = session
        self._login_id = login_id
        self._password = password
        self._country = country.strip().upper()
        self._api_base: str | None = None
        self._country_number: str | None = None
        self._token: str | None = None
        self._uid: str | None = None

    # ------------------------------------------------------------------
    # Low level
    # ------------------------------------------------------------------

    def _envelope(self, country_number: str, **extra: Any) -> dict[str, Any]:
        return {**_APP_ENVELOPE, "CountryCode": country_number, **extra}

    async def _request(
        self, url: str, payload: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        """POST JSON and return the decoded JSON object."""
        try:
            async with self._session.post(
                url,
                data=json.dumps(payload),
                headers=headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    raise InBodyAuthError(f"HTTP {resp.status}")
                if resp.status >= 400:
                    raise InBodyError(f"HTTP {resp.status} from {url}")
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise InBodyConnectionError(str(err)) from err
        except ValueError as err:
            raise InBodyError(f"Invalid JSON from {url}") from err
        if not isinstance(data, dict):
            raise InBodyError(f"Unexpected response from {url}")
        return data

    # ------------------------------------------------------------------
    # Region + login
    # ------------------------------------------------------------------

    async def _resolve_api_base(self) -> str:
        if self._api_base is not None:
            return self._api_base

        payload = self._envelope("", SyncDatetime=_FULL_SYNC_DATETIME)
        data = await self._request(
            f"{COMMON_URL}/CommonAPI/GetCountryInfoV2",
            payload,
            {
                "User-Agent": _UA_OKHTTP,
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        if not data.get("IsSuccess"):
            raise InBodyError(f"GetCountryInfoV2 failed: {data.get('ErrorMsg')}")

        row = next(
            (
                r
                for r in (data.get("Data") or [])
                if r.get("Type") == "API"
                and str(r.get("Code2")).upper() == self._country
            ),
            None,
        )
        if row is None:
            raise InBodyCountryError(self._country)

        self._api_base = str(row["Domain"]).rstrip("/")
        self._country_number = str(row.get("Number"))
        _LOGGER.debug("InBody API base for %s: %s", self._country, self._api_base)
        return self._api_base

    async def async_login(self) -> str:
        """Authenticate and return the account UID."""
        base = await self._resolve_api_base()
        assert self._country_number is not None

        payload = self._envelope(
            self._country_number,
            AuthProvider="",
            AuthProviderID="",
            AuthToken="",
            CustomKey="",
            DeviceType="Pixel 6 Pro 14",
            LoginID=self._login_id,
            LoginPW=self._password,
            Type="Login",
            SyncDatetime=_FULL_SYNC_DATETIME,
            SyncDatetimeBasalMedical=_FULL_SYNC_DATETIME,
            SyncDatetimeCardiac=_FULL_SYNC_DATETIME,
            SyncDatetimeExercise=_FULL_SYNC_DATETIME,
            SyncDatetimeInBody=_FULL_SYNC_DATETIME,
            SyncDatetimeNutrition=_FULL_SYNC_DATETIME,
            SyncDatetimeSleep=_FULL_SYNC_DATETIME,
            SyncType="Main;InBody;Exercise;Nutrition;Sleep;EasyTrainning;BasalMedical;",
        )
        data = await self._request(
            f"{base}/V2/Main/GetLoginWithSyncDataPartV2",
            payload,
            {
                "User-Agent": _UA_OKHTTP,
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        if not data.get("IsSuccess") or not data.get("Token"):
            raise InBodyAuthError(str(data.get("ErrorMsg") or "login failed"))

        uid = (data.get("Data") or {}).get("UID")
        if not uid:
            raise InBodyAuthError("Login succeeded but no UID returned")
        self._token = data["Token"]
        self._uid = str(uid)
        return self._uid

    # ------------------------------------------------------------------
    # Authenticated calls
    # ------------------------------------------------------------------

    async def _post_auth(
        self, path: str, payload: dict[str, Any], *, _retried: bool = False
    ) -> dict[str, Any]:
        if self._token is None:
            await self.async_login()
        base = await self._resolve_api_base()
        headers = {
            "Authorization": f"Bearer {self._token}",
            "User-Agent": _UA_DALVIK,
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json",
        }
        try:
            data = await self._request(f"{base}{path}", payload, headers)
        except InBodyAuthError:
            if _retried:
                raise
            self._token = None
            await self.async_login()
            return await self._post_auth(path, payload, _retried=True)

        if not data.get("IsSuccess"):
            err = str(data.get("ErrorMsg") or "").lower()
            if not _retried and any(w in err for w in ("token", "auth", "expire")):
                self._token = None
                await self.async_login()
                return await self._post_auth(path, payload, _retried=True)
            raise InBodyError(f"InBody API error: {data.get('ErrorMsg') or data}")
        return data

    async def _get_scans(self, number: int, home_device: bool) -> list[dict[str, Any]]:
        await self._resolve_api_base()
        assert self._country_number is not None
        if self._uid is None:
            await self.async_login()
        payload = self._envelope(
            self._country_number,
            uid=self._uid,
            syncDatetime=_FULL_SYNC_DATETIME,
            NumberPerData=str(number),
            CurrentIndex="0",
            Language="en-US",
            UseInBodyHomeDevice="true" if home_device else "false",
        )
        data = await self._post_auth("/V2/InBody/GetInBodyData", payload)
        return data.get("Data") or []

    async def async_get_latest_scan(self, tz: tzinfo | None) -> InBodyScan | None:
        """Return the most recent scan, or None if the account has no scans."""
        records = await self._get_scans(5, home_device=False)
        if not records:
            # The mobile API has a separate flag for "home" devices; try it
            # before concluding the account is empty. Failures here are ignored.
            try:
                records = await self._get_scans(5, home_device=True)
            except InBodyAuthError:
                raise
            except InBodyError as err:
                _LOGGER.debug("Home-device scan query failed: %s", err)
                records = []
        if not records:
            return None
        latest = max(records, key=lambda r: str(r.get("DATETIMES") or ""))
        return InBodyScan.from_record(latest, tz)
