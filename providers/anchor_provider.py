"""
Anchor browser provider module.
Handles session creation, URL retrieval, and cleanup for Anchor browser automation.
"""

import os
import time

import httpx
from anchorbrowser import Anchorbrowser


##Anchor Mobile Proxy
def create_session(stealth=False, max_retries=3, retry_delay_seconds=5):
    """Create an Anchor session and return the client, session, and CDP URL
    
    Args:
        stealth: If True, enables extra_stealth mode with anchor_mobile proxy.
                 If False, uses standard anchor_residential proxy (current behavior).
        max_retries: Maximum number of retry attempts for transient failures (default: 3)
        retry_delay_seconds: Delay between retries in seconds (default: 5)
    
    Returns:
        tuple: (anchor_client, anchor_session, cdp_url)
    
    Raises:
        Exception: If all retry attempts fail
    """
    anchor_client = Anchorbrowser(api_key=os.getenv("ANCHOR_API_KEY"))
    
    last_exception = None

    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                print(f"Retry attempt {attempt}/{max_retries} after {retry_delay_seconds}s delay...")
                time.sleep(retry_delay_seconds)

            if stealth:
                # Use direct HTTP POST for advanced stealth mode (not officially in SDK)
                session_creation_response = anchor_client.post(
                    "/v1/sessions",
                    cast_to=httpx.Response,
                    body={
                        "session": {
                            "proxy": {"active": True, "type": "anchor_mobile"},
                            "timeout": {"idle_timeout": 5, "max_duration": 30},
                        },
                        "browser": {
                            "captcha_solver": {"active": True},
                            "extra_stealth": {"active": True},
                        },
                    },
                )
                
                # Parse JSON response manually
                session_data = session_creation_response.json()["data"]
                session_id = session_data["id"]
                cdp_url = session_data["cdp_url"]
                
                print("Anchor Session's CDP_URL for later use (STEALTH MODE)\n", cdp_url)
                print(f"Session created with CAPTCHA solver, extra_stealth, and mobile proxy: {session_id}")
                
                # Create a simple object to hold session data for compatibility with cleanup
                class SessionWrapper:
                    def __init__(self, session_id):
                        self.data = type('obj', (object,), {'id': session_id})()
                
                anchor_session = SessionWrapper(session_id)
                
            else:
                # Use standard SDK method (no changes to current behavior)
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
            
        except Exception as e:
            last_exception = e
            error_str = str(e).lower()
            
            # Retry on transient errors (connection, timeout, server errors)
            should_retry = any(keyword in error_str for keyword in [
                "timeout", "connection", "500", "502", "503", "504", "429"
            ])
            
            if should_retry:
                print(f"Error creating Anchor session (attempt {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    print(f"All {max_retries} retry attempts failed")
                    raise
                continue
            else:
                # Don't retry on other errors
                print(f"Error creating Anchor session: {e}")
                raise
    
    # Should never reach here, but just in case
    if last_exception:
        raise last_exception
    raise Exception("Failed to create session after all retries")


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
