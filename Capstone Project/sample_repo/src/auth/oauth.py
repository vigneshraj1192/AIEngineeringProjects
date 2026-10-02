"""Sample OAuth authentication handler for DevStream Labs."""

import urllib.parse
from typing import Dict, Any, Optional

class OAuthHandler:
    """Manages GitHub and internal OAuth redirect flows."""

    def __init__(self, client_id: str = "devstream_client", redirect_uri: str = "https://app.devstream.io/callback"):
        self.client_id = client_id
        self.redirect_uri = redirect_uri

    def build_authorize_url(self, state: str, extra_params: Optional[Dict[str, str]] = None) -> str:
        """
        Construct authorization URL for OAuth redirect.
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state,
        }
        if extra_params:
            params.update(extra_params)

        # URL-encode query string
        query_string = urllib.parse.urlencode(params)
        return f"https://auth.devstream.io/oauth/authorize?{query_string}"

    def parse_callback(self, callback_url: str) -> Dict[str, str]:
        """
        Extract code and state from callback URL.
        """
        parsed = urllib.parse.urlparse(callback_url)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" not in params:
            raise ValueError("Missing 'code' query parameter in callback")
        return {
            "code": params["code"][0],
            "state": params.get("state", [""])[0]
        }
