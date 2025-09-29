"""
Browser automation script supporting multiple providers.

Usage:
  python browser_test.py --provider anchor      # Use Anchor browser (default)
  python browser_test.py --provider browserbase # Use Browserbase with advanced stealth (default)
  python browser_test.py --provider browserbase --no-stealth # Use Browserbase without stealth
  python browser_test.py --provider steelbrowser # Use Steel browser with advanced stealth (default)
  python browser_test.py --provider steelbrowser --no-stealth # Use Steel browser without stealth
  python browser_test.py --provider hyperbrowser # Use Hyperbrowser with advanced stealth and features (default)
  python browser_test.py --provider hyperbrowser --no-stealth # Use Hyperbrowser without stealth

Environment variables required:
- For Anchor: ANCHOR_API_KEY
- For Browserbase: BROWSERBASE_API_KEY, BROWSERBASE_PROJECT_ID
- For Steel: STEEL_API_KEY
- For Hyperbrowser: HYPERBROWSER_API_KEY
- For all: OPENAI_API_KEY
"""

from anchorbrowser import Anchorbrowser
from browserbase import Browserbase
from browser_use import Agent, Controller
from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.llm import ChatOpenAI
import os
import asyncio
import requests
import argparse
from steel import Steel
from playwright.sync_api import sync_playwright

from dotenv import load_dotenv
load_dotenv()

def create_browserbase_session(stealth=True):
    """Create a Browserbase session and return the CDP URL (stealth enabled by default)"""
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

def get_browserbase_session_url(session_id):
    """Get the Browserbase session URL"""
    session_url = f"https://www.browserbase.com/sessions/{session_id}"
    print(f"Browserbase session URL: {session_url}")
    return session_url

def delete_browserbase_session(bb_client, session_id):
    """End a Browserbase session using the SDK"""
    try:
        # Sessions typically end automatically, but we can try to close it
        # The SDK might not have a delete method, sessions may auto-expire
        if hasattr(bb_client.sessions, 'close'):
            bb_client.sessions.close(session_id)
        elif hasattr(bb_client.sessions, 'end'):
            bb_client.sessions.end(session_id)
        else:
            print(f"Browserbase session {session_id} - no manual close method available, session will auto-expire")
            return
        print(f"Browserbase session {session_id} closed successfully")
    except Exception as e:
        print(f"Error closing Browserbase session: {e}")

def create_steel_session(starting_url="https://www.google.com/", stealth=True):
    """Create a Steel session (stealth enabled by default)"""
    steel_api_key = os.getenv("STEEL_API_KEY")
    
    if not steel_api_key:
        raise ValueError("STEEL_API_KEY environment variable not set")
    
    try:
        if stealth:
            print("Creating Steel session with advanced stealth features...")
            # Create a new Steel session with enhanced features
            payload = { 
                "useProxy": True,   # Enable proxy usage
                "solveCaptcha": True,  # Enable captcha solving
                "blockAds": True,   # Block ads for better performance
                "stealthConfig": {
                    "humanizeInteractions": True,  # Make interactions more human-like
                    "skipFingerprintInjection": False  # Keep fingerprint protection
                }
            }
        else:
            print("Creating standard Steel session...")
            # Create a basic Steel session without advanced stealth features
            payload = {
                "timeout": 300000  # 5 minute timeout
            }
        
        url = "https://api.steel.dev/v1/sessions"
        headers = {"Content-Type": "application/json", "steel-api-key": steel_api_key}
        
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        session_data = response.json()
        session_id = session_data.get("id")
        
        if not session_id:
            raise ValueError("No session ID returned from Steel API")
        
        # Create the WebSocket CDP URL
        cdp_url = f"wss://connect.steel.dev?apiKey={steel_api_key}&sessionId={session_id}"
        
        print(f"Steel session created with ID: {session_id}")
        if stealth:
            print(f"Features enabled: solveCaptcha=True, useProxy=True, blockAds=True")
        else:
            print("Features: Standard session (no advanced stealth)")
        print(f"CDP URL: {cdp_url}")
        
        return session_id, cdp_url
        
    except Exception as e:
        print(f"Error creating Steel session: {e}")
        raise

def get_steel_session_url(session_id):
    """Get the Steel session recording URL"""
    session_url = f"https://app.steel.dev/sessions/{session_id}"
    print(f"Steel session recording URL: {session_url}")
    return session_url

def delete_steel_session(session_id):
    """Release a Steel session"""
    steel_api_key = os.getenv("STEEL_API_KEY")
    
    if not steel_api_key:
        print("Warning: STEEL_API_KEY not set, cannot release session")
        return
    
    try:
        print(f"Releasing Steel session {session_id}...")
        
        url = f"https://api.steel.dev/v1/sessions/{session_id}/release"
        headers = {"Content-Type": "application/json", "Steel-Api-Key": steel_api_key}
        
        response = requests.post(url, json={}, headers=headers)
        response.raise_for_status()
        
        print(f"Steel session {session_id} released successfully")
        
    except Exception as e:
        print(f"Error releasing Steel session: {e}")

def create_hyperbrowser_session(stealth=True):
    """Create a Hyperbrowser session and return the CDP URL (stealth enabled by default)"""
    import json
    
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

def get_hyperbrowser_session_url(session_id):
    """Get the Hyperbrowser session URL"""
    session_url = f"https://app.hyperbrowser.ai/sessions/{session_id}"
    print(f"Hyperbrowser session URL: {session_url}")
    return session_url

def delete_hyperbrowser_session(session_id):
    """Stop a Hyperbrowser session"""
    hyperbrowser_api_key = os.getenv("HYPERBROWSER_API_KEY")
    
    if not hyperbrowser_api_key:
        print("Warning: HYPERBROWSER_API_KEY not set, cannot stop session")
        return
    
    try:
        print(f"Stopping Hyperbrowser session {session_id}...")
        
        response = requests.put(
            f"https://api.hyperbrowser.ai/api/session/{session_id}/stop",
            headers={"x-api-key": hyperbrowser_api_key, "Accept": "*/*"}
        )
        
        response.raise_for_status()
        data = response.json()
        print(f"Hyperbrowser session {session_id} stopped successfully")
        
    except Exception as e:
        print(f"Error stopping Hyperbrowser session: {e}")

async def main(provider="anchor", stealth=True):
    # Initialize variables for cleanup
    anchor_client = None
    anchor_session = None
    browserbase_session_id = None
    bb_client = None
    steel_session_id = None
    hyperbrowser_session_id = None
    hyperbrowser_session_url = None
    
    if provider == "anchor":
        # Create Anchor session
        anchor_client = Anchorbrowser(
            api_key=os.getenv("ANCHOR_API_KEY")
        )

        anchor_session = anchor_client.sessions.create()
        cdp_url = anchor_session.data.cdp_url
        print("Anchor Session's CDP_URL for later use\n", cdp_url)
    elif provider == "browserbase":
        # Create Browserbase session (stealth enabled by default)
        browserbase_session_id, cdp_url, bb_client = create_browserbase_session(stealth=stealth)
    elif provider == "steelbrowser":
        # Create Steel session (stealth enabled by default)
        steel_session_id, cdp_url = create_steel_session(stealth=stealth)
    elif provider == "hyperbrowser":
        # Create Hyperbrowser session (stealth enabled by default)
        hyperbrowser_session_id, cdp_url, hyperbrowser_session_url = create_hyperbrowser_session(stealth=stealth)
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'anchor', 'browserbase', 'steelbrowser', or 'hyperbrowser'")

    # Configure your LLM (example with OpenAI)
    llm = ChatOpenAI(
        model='gpt-4o',
        api_key=os.getenv('OPENAI_API_KEY'),
    )

    # Initialize browser session with Anchor
    profile = BrowserProfile(keep_alive=True)
    browser_session = BrowserSession(
        headless=False,
        cdp_url=cdp_url,
        browser_profile=profile
    )

    # Create controller and agent
    controller = Controller()
    agent = Agent(
        task="Check the score of the last 3 patriots games",
        llm=llm,
        enable_memory=False,
        use_vision=False,
        controller=controller,
        browser_session=browser_session,
    )

    # Run the agent
    history = await agent.run(max_steps=40)
    print("History:", history)
    
    # Debug: Check what attributes the history object has
    print("History type:", type(history))
    print("History attributes:", dir(history))
    
    # Extract final result using the proper method
    final_message = ""
    try:
        # Use the proper final_result() method
        if hasattr(history, 'final_result'):
            final_message = history.final_result()
        else:
            print("final_result() method not found, falling back to manual extraction")
            # Fallback to manual extraction if the method doesn't exist
            if hasattr(history, 'extracted_content'):
                contents = history.extracted_content()
                if contents:
                    final_message = contents[-1]  # Get the last extracted content
            elif hasattr(history, '__iter__'):
                # If history is iterable, get the last item with extracted content
                for action_result in reversed(list(history)):
                    if hasattr(action_result, 'extracted_content') and action_result.extracted_content:
                        final_message = action_result.extracted_content
                        break
    except Exception as e:
        print(f"Error extracting final message: {e}")
        final_message = "Could not extract final message"
    
    # Clean up - stop browser session and terminate provider session
    try:
        print("Stopping browser session...")
        await browser_session.stop()
        print("Browser session stopped successfully")
    except Exception as e:
        print(f"Error stopping browser session: {e}")
    
    # Provider-specific cleanup
    recording_data = None
    if provider == "anchor" and anchor_client and anchor_session:
        try:
            print("Deleting Anchor session...")
            anchor_client.sessions.delete(anchor_session.data.id)
            print("Anchor session deleted successfully")
        except Exception as e:
            print(f"Error deleting Anchor session: {e}")
        
        # Get session recordings for Anchor
        try:
            print("Getting session recordings...")
            recordings = anchor_client.sessions.recordings.list(anchor_session.data.id)
            print("Session recordings retrieved successfully")
            
            # Extract just the file_link from the first recording
            if recordings.data and recordings.data.items and len(recordings.data.items) > 0:
                session_url = recordings.data.items[0].get('file_link')
                print(f"Anchor recording URL: {session_url}")
            else:
                print("No recordings found")
                session_url = None
        except Exception as e:
            print(f"Error getting session recordings: {e}")
            session_url = None
    elif provider == "browserbase" and browserbase_session_id:
        # Get session URL for Browserbase
        try:
            print("Getting Browserbase session URL...")
            session_url = get_browserbase_session_url(browserbase_session_id)
        except Exception as e:
            print(f"Error getting Browserbase session URL: {e}")
            session_url = None
            
        try:
            print("Deleting Browserbase session...")
            delete_browserbase_session(bb_client, browserbase_session_id)
        except Exception as e:
            print(f"Error deleting Browserbase session: {e}")
    elif provider == "steelbrowser" and steel_session_id:
        # Get session URL for Steel
        try:
            print("Getting Steel session recording URL...")
            session_url = get_steel_session_url(steel_session_id)
        except Exception as e:
            print(f"Error getting Steel session URL: {e}")
            session_url = None
            
        # Release Steel session
        try:
            print("Releasing Steel session...")
            delete_steel_session(steel_session_id)
        except Exception as e:
            print(f"Error releasing Steel session: {e}")
    elif provider == "hyperbrowser" and hyperbrowser_session_id:
        # Use session URL from API response
        session_url = hyperbrowser_session_url
            
        # Stop Hyperbrowser session
        try:
            print("Stopping Hyperbrowser session...")
            delete_hyperbrowser_session(hyperbrowser_session_id)
        except Exception as e:
            print(f"Error stopping Hyperbrowser session: {e}")
    
    # Return both the final result and session URL (or recording for Anchor)
    return final_message, session_url

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run browser automation with different providers")
    parser.add_argument(
        "--provider", 
        choices=["anchor", "browserbase", "steelbrowser", "hyperbrowser"], 
        default="anchor",
        help="Browser provider to use (default: anchor)"
    )
    parser.add_argument(
        "--no-stealth",
        action="store_true",
        help="Disable advanced stealth mode for Browserbase, Steel, and Hyperbrowser (stealth is enabled by default)"
    )
    args = parser.parse_args()
    
    # Validate no-stealth option
    if args.no_stealth and args.provider not in ["browserbase", "steelbrowser", "hyperbrowser"]:
        print("Warning: --no-stealth option only works with --provider browserbase, --provider steelbrowser, or --provider hyperbrowser. Ignoring option.")
    
    # For Browserbase, Steel, and Hyperbrowser, stealth is enabled by default, disabled only with --no-stealth
    stealth_enabled = not args.no_stealth if args.provider in ["browserbase", "steelbrowser", "hyperbrowser"] else False
    
    final_result, session_data = asyncio.run(main(provider=args.provider, stealth=stealth_enabled))
    print("\n=== Final Results ===")
    print("Final Result (from history.final_result()):", final_result)
    
    if args.provider == "browserbase" and session_data:
        print("Browserbase Session URL:", session_data)
    elif args.provider == "anchor" and session_data:
        print("Anchor Session Recording:", session_data)
    elif args.provider == "steelbrowser" and session_data:
        print("Steel Session Recording URL:", session_data)
    elif args.provider == "hyperbrowser" and session_data:
        print("Hyperbrowser Session URL:", session_data)