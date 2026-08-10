"""Basic tests for the new GraphQL and Cognito API client."""

from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientError, ClientResponseError, ClientSession

from custom_components.kippy.api._base import (
    APPSYNC_ENDPOINT,
    COGNITO_ENDPOINT,
    BaseKippyApi,
)


@pytest.mark.asyncio
async def test_cognito_login_success() -> None:
    """Test successful Amazon Cognito login."""
    mock_session = AsyncMock(spec=ClientSession)
    mock_response = AsyncMock()
    mock_response.status = 200
    # Simulate a successful Cognito AuthenticationResult
    mock_response.json.return_value = {
        "AuthenticationResult": {
            "IdToken": "mock_id_token",
            "AccessToken": "mock_access_token",
            "RefreshToken": "mock_refresh_token",
        }
    }
    mock_session.post.return_value.__aenter__.return_value = mock_response

    api = BaseKippyApi(mock_session)
    auth_data = await api.login("test@example.com", "secure_password")

    assert auth_data["id_token"] == "mock_id_token"
    assert api._credentials == ("test@example.com", "secure_password")
    mock_session.post.assert_called_once()

    # Check if correct URL and payload were passed
    args, kwargs = mock_session.post.call_args
    assert args[0] == COGNITO_ENDPOINT
    assert "json" in kwargs
    assert kwargs["json"]["AuthParameters"]["USERNAME"] == "test@example.com"
    assert (
        kwargs["headers"]["X-Amz-Target"]
        == "AWSCognitoIdentityProviderService.InitiateAuth"
    )


@pytest.mark.asyncio
async def test_execute_graphql_success() -> None:
    """Test a successful GraphQL query execution."""
    mock_session = AsyncMock(spec=ClientSession)
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "data": {"getPets": {"pets": [{"name": "Lola", "species": "CAT"}]}}
    }
    mock_session.post.return_value.__aenter__.return_value = mock_response

    api = BaseKippyApi(mock_session)
    # Mock an already established session
    api._auth = {"id_token": "valid_token"}
    api._credentials = ("test@example.com", "password")

    query = "query { getPets { pets { name species } } }"
    result = await api.execute_graphql(query)

    # Verify the result contains the 'data' part of the payload
    assert result == {"getPets": {"pets": [{"name": "Lola", "species": "CAT"}]}}

    mock_session.post.assert_called_once()
    args, kwargs = mock_session.post.call_args
    assert args[0] == APPSYNC_ENDPOINT
    assert kwargs["headers"]["Authorization"] == "Bearer valid_token"
    assert kwargs["json"]["query"] == query


@pytest.mark.asyncio
async def test_execute_graphql_token_refresh() -> None:
    """Test that GraphQL query automatically refreshes token on 401 Unauthorized."""
    mock_session = AsyncMock(spec=ClientSession)

    # First response: 401 Unauthorized (Token expired)
    mock_response_401 = AsyncMock()
    mock_response_401.status = 401

    # Second response: 200 OK (New Token generated, Request successful)
    mock_response_200 = AsyncMock()
    mock_response_200.status = 200
    mock_response_200.json.return_value = {"data": {"success": True}}

    # Setup sequential responses
    mock_session.post.return_value.__aenter__.side_effect = [
        mock_response_401,  # Fails on GraphQL endpoint
        mock_response_200,  # Cognito Login Success (Mocks the login inner post)
        mock_response_200,  # Succeeds on GraphQL endpoint after retry
    ]

    api = BaseKippyApi(mock_session)
    api._auth = {"id_token": "expired_token"}
    api._credentials = ("test@example.com", "password")

    # We must patch login so it doesn't do a real HTTP call but updates the token
    # or we can let it run through the mock session. Since login uses the SAME session,
    # the second side_effect return will be consumed by login().
    # To keep it simple, we patch login:
    with patch.object(api, "login", new_callable=AsyncMock) as mock_login:
        # Override the side effects to only serve the GraphQL endpoint
        mock_session.post.return_value.__aenter__.side_effect = [
            mock_response_401,  # First GraphQL try -> 401
            mock_response_200,  # Second GraphQL try -> 200
        ]

        async def fake_login(*args, **kwargs):
            api._auth = {"id_token": "new_fresh_token"}

        mock_login.side_effect = fake_login

        result = await api.execute_graphql("query { test }")

        assert result == {"success": True}
        # login is called twice: once by ensure_login(), once by the 401 refresh
        assert mock_login.call_count == 2
        assert mock_session.post.call_count == 2

        # Verify the second call used the new token
        last_call_kwargs = mock_session.post.call_args_list[1][1]
        assert last_call_kwargs["headers"]["Authorization"] == "Bearer new_fresh_token"


@pytest.mark.asyncio
async def test_login_returns_cached_auth() -> None:
    """Test that login returns cached auth without a second request."""
    mock_session = AsyncMock(spec=ClientSession)

    api = BaseKippyApi(mock_session)
    api._auth = {"id_token": "cached_token"}

    result = await api.login("test@example.com", "password")

    assert result == {"id_token": "cached_token"}
    mock_session.post.assert_not_called()


@pytest.mark.asyncio
async def test_login_no_authentication_result() -> None:
    """Test that login raises when no AuthenticationResult is returned."""
    mock_session = AsyncMock(spec=ClientSession)
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {}
    mock_session.post.return_value.__aenter__.return_value = mock_response

    api = BaseKippyApi(mock_session)

    with pytest.raises(ClientResponseError):
        await api.login("test@example.com", "password")


@pytest.mark.asyncio
async def test_login_client_error() -> None:
    """Test that login propagates a ClientError."""
    mock_session = AsyncMock(spec=ClientSession)
    mock_session.post.return_value.__aenter__.side_effect = ClientError("boom")

    api = BaseKippyApi(mock_session)

    with pytest.raises(ClientError):
        await api.login("test@example.com", "password")


@pytest.mark.asyncio
async def test_ensure_login_no_credentials() -> None:
    """Test that ensure_login raises when credentials are missing."""
    mock_session = AsyncMock(spec=ClientSession)

    api = BaseKippyApi(mock_session)

    with pytest.raises(RuntimeError):
        await api.ensure_login()


@pytest.mark.asyncio
async def test_close_closes_session() -> None:
    """Test that close closes the underlying session."""
    mock_session = AsyncMock(spec=ClientSession)

    api = BaseKippyApi(mock_session)
    await api.close()

    mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_execute_graphql_client_error() -> None:
    """Test that execute_graphql propagates a ClientError."""
    mock_session = AsyncMock(spec=ClientSession)
    mock_session.post.return_value.__aenter__.side_effect = ClientError("boom")

    api = BaseKippyApi(mock_session)
    api._auth = {"id_token": "valid_token"}
    api._credentials = ("test@example.com", "password")

    with pytest.raises(ClientError):
        await api.execute_graphql("query { test }")


@pytest.mark.asyncio
async def test_session_property() -> None:
    """Test the session property returns the underlying session."""
    mock_session = AsyncMock(spec=ClientSession)

    api = BaseKippyApi(mock_session)

    assert api.session is mock_session
