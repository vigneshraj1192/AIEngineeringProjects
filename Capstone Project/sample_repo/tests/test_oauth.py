import pytest
from sample_repo.src.auth.oauth import OAuthHandler

def test_oauth_handler_build_authorize_url():
    handler = OAuthHandler(redirect_uri="https://app.devstream.io/callback?next=/dashboard")
    url = handler.build_authorize_url(state="xyz123")
    assert "https://auth.devstream.io/oauth/authorize?" in url
    assert "client_id=devstream_client" in url
    assert "state=xyz123" in url
    # Verify redirect_uri is URL-encoded
    assert "redirect_uri=https%3A%2F%2Fapp.devstream.io%2Fcallback%3Fnext%3D%2Fdashboard" in url

def test_oauth_handler_parse_callback():
    handler = OAuthHandler()
    res = handler.parse_callback("https://app.devstream.io/callback?code=auth_code_789&state=xyz123")
    assert res["code"] == "auth_code_789"
    assert res["state"] == "xyz123"

def test_oauth_handler_missing_code():
    handler = OAuthHandler()
    with pytest.raises(ValueError):
        handler.parse_callback("https://app.devstream.io/callback?error=access_denied")
