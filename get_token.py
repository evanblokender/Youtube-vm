#!/usr/bin/env python3
"""
One-time OAuth2 setup script to get a refresh token for posting to YouTube chat.
Run this ONCE on a machine with a browser.

Usage:
    pip install google-auth-oauthlib
    python get_token.py
"""

import json
import os
import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Install required: pip install google-auth-oauthlib")
    sys.exit(1)

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

CLIENT_SECRETS = "client_secrets.json"

def main():
    if not os.path.exists(CLIENT_SECRETS):
        # Prompt for values
        print("\n=== YouTube OAuth2 Token Setup ===")
        print("You need OAuth2 credentials from Google Cloud Console.")
        print("Create a project, enable YouTube Data API v3, create OAuth2 Desktop credentials.\n")

        client_id = input("Enter your OAuth2 Client ID: ").strip()
        client_secret = input("Enter your OAuth2 Client Secret: ").strip()

        secrets = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
            }
        }
        with open(CLIENT_SECRETS, "w") as f:
            json.dump(secrets, f)
        print(f"Saved to {CLIENT_SECRETS}")

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
    credentials = flow.run_local_server(port=8080)

    print("\n=== SUCCESS ===")
    print(f"Access Token:  {credentials.token}")
    print(f"Refresh Token: {credentials.refresh_token}")
    print(f"Client ID:     {credentials.client_id}")
    print(f"Client Secret: {credentials.client_secret}")
    print("\nAdd these to your config.json:")
    print(json.dumps({
        "youtube_client_id": credentials.client_id,
        "youtube_client_secret": credentials.client_secret,
        "youtube_refresh_token": credentials.refresh_token,
    }, indent=2))

if __name__ == "__main__":
    main()
