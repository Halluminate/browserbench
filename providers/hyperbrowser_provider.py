"""
Hyperbrowser provider module.
Handles session creation, URL retrieval, and cleanup for Hyperbrowser browser automation.
"""

import os
import requests
import json


def create_session(stealth=True):
    """Create a Hyperbrowser session and return the session ID, CDP URL, and session URL (stealth enabled by default)"""
    hyperbrowser_api_key = os.getenv("HYPERBROWSER_API_KEY")

    if not hyperbrowser_api_key:
        raise ValueError("HYPERBROWSER_API_KEY environment variable not set")

    try:
        if stealth:
            print("Creating Hyperbrowser session with stealth features...")
            payload = {
                "useStealth": True,
                "useProxy": True,
                "solveCaptchas": True
            }
        else:
            print("Creating standard Hyperbrowser session...")
            payload = {}

        response = requests.post(
            "https://api.hyperbrowser.ai/api/session",
            headers={"x-api-key": hyperbrowser_api_key, "Content-Type": "application/json"},
            data=json.dumps(payload)
        )

        response.raise_for_status()
        data = response.json()

        session_id = data.get("id")
        cdp_url = data.get("wsEndpoint")
        session_url = data.get("sessionUrl")

        if not session_id or not cdp_url:
            raise ValueError(f"Invalid response from Hyperbrowser API: {data}")

        print(f"Hyperbrowser session created with ID: {session_id}")
        print(f"CDP URL: {cdp_url}")
        print(f"Session URL: {session_url}")

        return session_id, cdp_url, session_url

    except Exception as e:
        print(f"Error creating Hyperbrowser session: {e}")
        raise


def get_session_url(session_id):
    """Get the Hyperbrowser session URL"""
    session_url = f"https://app.hyperbrowser.ai/features/sessions/{session_id}"
    print(f"Hyperbrowser session URL: {session_url}")
    return session_url


def cleanup_session(session_id):
    """Stop a Hyperbrowser session"""
    hyperbrowser_api_key = os.getenv("HYPERBROWSER_API_KEY")

    if not hyperbrowser_api_key:
        print("Warning: HYPERBROWSER_API_KEY not set, cannot stop session")
        # Even without API key, return the session URL
        session_url = get_session_url(session_id)
        return session_url

    try:
        print(f"Stopping Hyperbrowser session {session_id}...")

        response = requests.put(
            f"https://api.hyperbrowser.ai/api/session/{session_id}/stop",
            headers={"x-api-key": hyperbrowser_api_key, "Accept": "*/*"}
        )

        response.raise_for_status()
        data = response.json()
        print(f"Hyperbrowser session {session_id} stopped successfully")

        # Use session URL from API response if available, otherwise generate it
        session_url = get_session_url(session_id)
        return session_url

    except Exception as e:
        print(f"Error stopping Hyperbrowser session: {e}")
        # Even if cleanup fails, still return the session URL
        session_url = get_session_url(session_id)
        return session_url
