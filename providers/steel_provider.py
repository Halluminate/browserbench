"""
Steel browser provider module.
Handles session creation, URL retrieval, and cleanup for Steel browser automation.
"""

import os
import time

import requests


def create_session(starting_url="https://www.google.com/", stealth=True, max_retries=3, retry_delay_seconds=5):
    """Create a Steel session (stealth enabled by default)
    
    Args:
        starting_url: Starting URL (default: "https://www.google.com/")
        stealth: If True, enables advanced stealth features (default: True)
        max_retries: Maximum number of retry attempts for transient failures (default: 3)
        retry_delay_seconds: Delay between retries in seconds (default: 5)
    
    Returns:
        tuple: (session_id, cdp_url)
    
    Raises:
        ValueError: If API key is missing or response is invalid
        requests.exceptions.RequestException: If all retry attempts fail
    """
    steel_api_key = os.getenv("STEEL_API_KEY")

    if not steel_api_key:
        raise ValueError("STEEL_API_KEY environment variable not set")

    if stealth:
        print("Creating Steel session with advanced stealth features...")
        # Create a new Steel session with enhanced features
        payload = {
            "useProxy": True,  # Enable proxy usage
            "solveCaptcha": True,  # Enable captcha solving  # Block ads for better performance
            "stealthConfig": {
                "humanizeInteractions": True,  # Make interactions more human-like
                "skipFingerprintInjection": False,  # Keep fingerprint protection
            },
        }
    else:
        print("Creating standard Steel session...")
        # Create a standard session without advanced features
        payload = {"useProxy": False, "solveCaptcha": False}

    url = "https://api.steel.dev/v1/sessions"
    headers = {"Content-Type": "application/json", "steel-api-key": steel_api_key}
    
    last_exception = None
    
    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                print(f"Retry attempt {attempt}/{max_retries} after {retry_delay_seconds}s delay...")
                time.sleep(retry_delay_seconds)

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            session_data = response.json()
            session_id = session_data.get("id")

            if not session_id:
                raise ValueError("No session ID returned from Steel API")

            # Create the WebSocket CDP URL
            cdp_url = (
                f"wss://connect.steel.dev?apiKey={steel_api_key}&sessionId={session_id}"
            )

            print(f"Steel session created with ID: {session_id}")
            if stealth:
                print("Features enabled: solveCaptcha=True, useProxy=True, blockAds=True")
            else:
                print("Features: Standard session (no advanced stealth)")
            print(f"CDP URL: {cdp_url}")

            return session_id, cdp_url

        except requests.exceptions.HTTPError as e:
            last_exception = e
            # Retry on 5xx server errors and 429 rate limiting
            if e.response is not None and e.response.status_code in [429, 500, 502, 503, 504]:
                print(f"Error creating Steel session (attempt {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    print(f"All {max_retries} retry attempts failed")
                    raise
                continue
            else:
                # Don't retry on 4xx client errors (except 429)
                print(f"Error creating Steel session: {e}")
                raise
                
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_exception = e
            # Retry on connection/timeout errors
            print(f"Connection error creating Steel session (attempt {attempt}/{max_retries}): {e}")
            if attempt == max_retries:
                print(f"All {max_retries} retry attempts failed")
                raise
            continue
            
        except Exception as e:
            # Don't retry on other exceptions (e.g., ValueError)
            print(f"Error creating Steel session: {e}")
            raise
    
    # Should never reach here, but just in case
    if last_exception:
        raise last_exception
    raise Exception("Failed to create session after all retries")


def get_session_url(session_id):
    """Get the Steel session recording URL"""
    session_url = f"https://app.steel.dev/sessions/{session_id}"
    print(f"Steel session recording URL: {session_url}")
    return session_url


def cleanup_session(session_id):
    """Release a Steel session"""
    steel_api_key = os.getenv("STEEL_API_KEY")

    if not steel_api_key:
        print("Warning: STEEL_API_KEY not set, cannot release session")
        # Even without API key, return the session URL
        session_url = get_session_url(session_id)
        return session_url

    try:
        print(f"Releasing Steel session {session_id}...")

        url = f"https://api.steel.dev/v1/sessions/{session_id}/release"
        headers = {"Content-Type": "application/json", "Steel-Api-Key": steel_api_key}

        response = requests.post(url, json={}, headers=headers)
        response.raise_for_status()

        print(f"Steel session {session_id} released successfully")

        # Get session URL for Steel
        session_url = get_session_url(session_id)
        return session_url

    except Exception as e:
        print(f"Error releasing Steel session: {e}")
        # Even if cleanup fails, still return the session URL
        session_url = get_session_url(session_id)
        return session_url
