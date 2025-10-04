"""
Anchor browser provider module.
Handles session creation, URL retrieval, and cleanup for Anchor browser automation.
"""

import os

from anchorbrowser import Anchorbrowser


##Anchor Mobile Proxy
def create_session():
    """Create an Anchor session and return the client, session, and CDP URL"""
    anchor_client = Anchorbrowser(api_key=os.getenv("ANCHOR_API_KEY"))

    anchor_session = anchor_client.sessions.create(
        browser={"captcha_solver": {"active": True}},
        session={
            "proxy": {
                "active": True,
                "country_code": "us",
                "type": "anchor_residential",
            }
        },
    )
    cdp_url = anchor_session.data.cdp_url

    print("Anchor Session's CDP_URL for later use\n", cdp_url)
    print(f"Session created with CAPTCHA solver and proxy: {anchor_session.data.id}")

    return anchor_client, anchor_session, cdp_url


def get_session_url(anchor_client, anchor_session):
    """Get the session recording URL from Anchor session"""
    # Get session recordings for Anchor
    try:
        print("Getting session recordings...")
        recordings = anchor_client.sessions.recordings.list(anchor_session.data.id)
        print("Session recordings retrieved successfully")

        # Extract just the file_link from the first recording
        if recordings.data and recordings.data.items and len(recordings.data.items) > 0:
            session_url = recordings.data.items[0].get("file_link")
            print(f"Anchor recording URL: {session_url}")
            return session_url
        else:
            print("No recordings found")
            return None
    except Exception as e:
        print(f"Error getting session recordings: {e}")
        return None


def cleanup_session(anchor_client, anchor_session):
    """Clean up Anchor session and return recording URL"""
    try:
        print("Deleting Anchor session...")
        anchor_client.sessions.delete(anchor_session.data.id)
        print("Anchor session deleted successfully")
    except Exception as e:
        print(f"Error deleting Anchor session: {e}")

    # Get session recordings for Anchor
    session_url = get_session_url(anchor_client, anchor_session)

    return session_url
