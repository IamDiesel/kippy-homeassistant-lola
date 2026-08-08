"""Core HTTP client and authentication helpers for the Kippy API."""

from __future__ import annotations

import asyncio
import logging
import ssl
from typing import Any, Dict, Optional

from aiohttp import ClientError, ClientResponseError, ClientSession

from ..const import (
    ERROR_NO_AUTH_DATA,
    ERROR_NO_CREDENTIALS,
    ERROR_UNEXPECTED_AUTH_FAILURE,
)

_LOGGER = logging.getLogger(__name__)

COGNITO_ENDPOINT = "https://cognito-idp.eu-west-1.amazonaws.com/"
COGNITO_CLIENT_ID = "57bn1c33eu2r5libvqvhfnv4qb"
APPSYNC_ENDPOINT = (
    "https://l2nea6uaizdn3j3h2ex7frcqhy.appsync-api.eu-west-1.amazonaws.com/graphql"
)


class BaseKippyApi:
    """Minimal Kippy API wrapper handling Cognito auth and GraphQL requests."""

    def __init__(
        self,
        session: ClientSession,
        ssl_context: Optional[ssl.SSLContext] = None,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._auth: Optional[Dict[str, Any]] = None
        self._credentials: tuple[str, str] | None = None
        self._ssl_context = ssl_context

    @classmethod
    async def async_create(cls, session: ClientSession) -> "BaseKippyApi":
        """Create an instance of the API client with an SSL context."""
        loop = asyncio.get_running_loop()
        ctx = await loop.run_in_executor(None, ssl.create_default_context)
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        if hasattr(ssl, "OP_LEGACY_SERVER_CONNECT"):
            ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
        return cls(session, ctx)

    @property
    def session(self) -> ClientSession:
        """Return the underlying :class:`aiohttp.ClientSession`."""
        return self._session

    async def login(
        self, email: str, password: str, force: bool = False
    ) -> Dict[str, Any]:
        """Login to Amazon Cognito and cache the JWT tokens."""
        if not force and self._auth is not None:
            return self._auth

        payload = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": COGNITO_CLIENT_ID,
            "AuthParameters": {
                "USERNAME": email,
                "PASSWORD": password,
            },
        }

        headers = {
            "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-User-Agent": "aws-amplify/0.0.x dart",
        }

        try:
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug("Cognito Login request initiated for %s", email)

            async with self._session.post(
                COGNITO_ENDPOINT,
                json=payload,
                headers=headers,
                ssl=self._ssl_context,
            ) as resp:
                if resp.status >= 400:
                    error_text = await resp.text()
                    _LOGGER.error(
                        "Cognito Login failed. Status: %s, Response: %s",
                        resp.status,
                        error_text,
                    )

                resp.raise_for_status()

                # FIX: aiohttp zwingen, den AWS Content-Type zu akzeptieren
                data = await resp.json(content_type=None)

                auth_result = data.get("AuthenticationResult")
                if not auth_result:
                    raise ClientResponseError(
                        resp.request_info,
                        resp.history,
                        status=401,
                        message="No AuthenticationResult in response",
                    )

                self._auth = {
                    "id_token": auth_result.get("IdToken"),
                    "access_token": auth_result.get("AccessToken"),
                    "refresh_token": auth_result.get("RefreshToken"),
                }
                self._credentials = (email, password)
                return self._auth

        except ClientResponseError as err:
            _LOGGER.debug("Cognito Login failed: status=%s", err.status)
            raise
        except ClientError as err:
            _LOGGER.debug("Error communicating with Cognito: %s", err)
            raise

    async def ensure_login(self) -> None:
        """Ensure a valid login session is available."""
        if self._credentials is None:
            raise RuntimeError(ERROR_NO_CREDENTIALS)
        email, password = self._credentials
        await self.login(email, password)

    async def close(self) -> None:
        """Close the underlying :class:`aiohttp.ClientSession`."""
        await self._session.close()

    async def execute_graphql(
        self, query: str, variables: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Execute a GraphQL query/mutation with automatic token refresh."""
        await self.ensure_login()

        if not self._auth or "id_token" not in self._auth:
            raise RuntimeError(ERROR_NO_AUTH_DATA)

        payload = {"query": query, "variables": variables or {}}

        for attempt in range(2):
            headers = {
                "Authorization": f"Bearer {self._auth['id_token']}",
                "Content-Type": "application/json",
            }

            try:
                async with self._session.post(
                    APPSYNC_ENDPOINT,
                    json=payload,
                    headers=headers,
                    ssl=self._ssl_context,
                ) as resp:
                    if resp.status == 401 and attempt == 0:
                        _LOGGER.debug("Token expired, refreshing login...")
                        await self.login(
                            self._credentials[0], self._credentials[1], force=True
                        )
                        continue

                    if resp.status >= 400:
                        err_text = await resp.text()
                        _LOGGER.error(
                            "GraphQL Request failed. Status: %s, Response: %s",
                            resp.status,
                            err_text,
                        )

                    resp.raise_for_status()

                    # FIX: Auch hier den Content-Type Check abschalten
                    result = await resp.json(content_type=None)

                    if "errors" in result:
                        _LOGGER.error(
                            "GraphQL response contained errors: %s", result["errors"]
                        )

                    return result.get("data", {})

            except ClientError as err:
                _LOGGER.debug("GraphQL Request Error: %s", err)
                raise

        raise RuntimeError(ERROR_UNEXPECTED_AUTH_FAILURE)
