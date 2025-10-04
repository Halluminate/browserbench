"""
Browserbase provider module.
Handles session creation, URL retrieval, and cleanup for Browserbase browser automation.
"""

import os

from browserbase import Browserbase


def create_session(stealth=True):
    """Create a Browserbase session and return the session ID, CDP URL, and client (stealth enabled by default)"""
    bb = Browserbase(api_key=os.getenv("BROWSERBASE_API_KEY"))

    if stealth:
        print("Creating Browserbase session with advanced stealth...")
        session = bb.sessions.create(
            project_id=os.getenv("BROWSERBASE_PROJECT_ID"),
            proxies=True,
            browser_settings={
                "advanced_stealth": True,
            },
        )
    else:
        print("Creating standard Browserbase session...")
        session = bb.sessions.create(
            project_id=os.getenv("BROWSERBASE_PROJECT_ID"),
        )

    session_id = session.id
    cdp_url = session.connect_url

    print(f"Browserbase session created with ID: {session_id}")
    print(f"CDP URL: {cdp_url}")

    return session_id, cdp_url, bb


def get_session_url(session_id):
    """Get the Browserbase session URL"""
    session_url = f"https://www.browserbase.com/sessions/{session_id}"
    print(f"Browserbase session URL: {session_url}")
    return session_url


def cleanup_session(bb_client, session_id):
    """End a Browserbase session using the SDK"""
    try:
        # Sessions typically end automatically, but we can try to close it
        # The SDK might not have a delete method, sessions may auto-expire
        if hasattr(bb_client.sessions, "close"):
            bb_client.sessions.close(session_id)
        elif hasattr(bb_client.sessions, "end"):
            bb_client.sessions.end(session_id)
        else:
            print(
                f"Browserbase session {session_id} - no manual close method available, session will auto-expire"
            )

        print(f"Browserbase session {session_id} closed successfully")

        # Get session URL for Browserbase
        session_url = get_session_url(session_id)
        return session_url

    except Exception as e:
        print(f"Error closing Browserbase session: {e}")
        # Even if cleanup fails, still return the session URL
        session_url = get_session_url(session_id)
        return session_url
