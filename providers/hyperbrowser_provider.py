"""
Hyperbrowser provider module.
Handles session creation, URL retrieval, and cleanup for Hyperbrowser browser automation.
"""

import json
import os
import time

import requests


def create_session(stealth=True, max_retries=3, retry_delay_seconds=5):
    """Create a Hyperbrowser session and return the session ID, CDP URL, and session URL (stealth enabled by default)
    
    Args:
        stealth: If True, enables stealth features (default: True)
        max_retries: Maximum number of retry attempts for transient failures (default: 3)
        retry_delay_seconds: Delay between retries in seconds (default: 5)
    
    Returns:
        tuple: (session_id, cdp_url, session_url)
    
    Raises:
        ValueError: If API key is missing or response is invalid
        requests.exceptions.RequestException: If all retry attempts fail
    """
    hyperbrowser_api_key = os.getenv("HYPERBROWSER_API_KEY")

    if not hyperbrowser_api_key:
        raise ValueError("HYPERBROWSER_API_KEY environment variable not set")

    if stealth:
        print("Creating Hyperbrowser session with stealth features...")
        payload = {"useStealth": True, "useProxy": True, "solveCaptchas": True}
    else:
        print("Creating standard Hyperbrowser session...")
        payload = {}

    last_exception = None
    
    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                print(f"Retry attempt {attempt}/{max_retries} after {retry_delay_seconds}s delay...")
                time.sleep(retry_delay_seconds)

            response = requests.post(
                "https://api.hyperbrowser.ai/api/session",
                headers={
                    "x-api-key": hyperbrowser_api_key,
                    "Content-Type": "application/json",
                },
                data=json.dumps(payload),
                timeout=30,
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

        except requests.exceptions.HTTPError as e:
            last_exception = e
            # Retry on 5xx server errors and 429 rate limiting
            if e.response is not None and e.response.status_code in [429, 500, 502, 503, 504]:
                print(f"Error creating Hyperbrowser session (attempt {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    print(f"All {max_retries} retry attempts failed")
                    raise
                continue
            else:
                # Don't retry on 4xx client errors (except 429)
                print(f"Error creating Hyperbrowser session: {e}")
                raise
                
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_exception = e
            # Retry on connection/timeout errors
            print(f"Connection error creating Hyperbrowser session (attempt {attempt}/{max_retries}): {e}")
            if attempt == max_retries:
                print(f"All {max_retries} retry attempts failed")
                raise
            continue
            
        except Exception as e:
            # Don't retry on other exceptions (e.g., ValueError)
            print(f"Error creating Hyperbrowser session: {e}")
            raise
    
    # Should never reach here, but just in case
    if last_exception:
        raise last_exception
    raise Exception("Failed to create session after all retries")


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
            headers={"x-api-key": hyperbrowser_api_key, "Accept": "*/*"},
        )

        response.raise_for_status()
        print(f"Hyperbrowser session {session_id} stopped successfully")

        # Use session URL from API response if available, otherwise generate it
        session_url = get_session_url(session_id)
        return session_url

    except Exception as e:
        print(f"Error stopping Hyperbrowser session: {e}")
        # Even if cleanup fails, still return the session URL
        session_url = get_session_url(session_id)
        return session_url
