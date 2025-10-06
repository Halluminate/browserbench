"""
Browser automation script supporting multiple providers.

Usage:
  python browser_test.py --provider anchor      # Use Anchor browser with advanced stealth (default)
  python browser_test.py --provider anchor --no-stealth # Use Anchor without stealth
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

import argparse
import asyncio
import os

from browser_use import Agent, Controller
from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.llm import ChatOpenAI
from dotenv import load_dotenv

# Import provider modules
from providers.anchor_provider import cleanup_session as anchor_cleanup
from providers.anchor_provider import create_session as anchor_create
from providers.browserbase_provider import cleanup_session as browserbase_cleanup
from providers.browserbase_provider import create_session as browserbase_create
from providers.hyperbrowser_provider import cleanup_session as hyperbrowser_cleanup
from providers.hyperbrowser_provider import create_session as hyperbrowser_create
from providers.steel_provider import cleanup_session as steel_cleanup
from providers.steel_provider import create_session as steel_create

load_dotenv()


async def main(
    provider="anchor", stealth=True, task="Check the score of the last 3 patriots games"
):
    """Main function to run browser automation with the specified provider"""
    # Create session based on provider
    if provider == "anchor":
        anchor_client, anchor_session, cdp_url = anchor_create(stealth=stealth)
    elif provider == "browserbase":
        browserbase_session_id, cdp_url, bb_client = browserbase_create(stealth=stealth)
    elif provider == "steelbrowser":
        steel_session_id, cdp_url = steel_create(stealth=stealth)
    elif provider == "hyperbrowser":
        hyperbrowser_session_id, cdp_url, hyperbrowser_session_url = (
            hyperbrowser_create(stealth=stealth)
        )
    else:
        raise ValueError(
            f"Unknown provider: {provider}. Use 'anchor', 'browserbase', 'steelbrowser', or 'hyperbrowser'"
        )

    # Configure your LLM (example with OpenAI)
    llm = ChatOpenAI(
        # model='gpt-oss-120b',
        model='gpt-4o',
        api_key=os.getenv('OPENAI_API_KEY'),
    )

    # Initialize browser session with Anchor
    profile = BrowserProfile(keep_alive=True)
    browser_session = BrowserSession(
        headless=False, cdp_url=cdp_url, browser_profile=profile
    )

    # Create controller and agent
    controller = Controller()
    agent = Agent(
        task=task,
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

    # Check if the task was successful
    is_successful = False
    error_message = None
    
    if hasattr(history, "is_successful"):
        # is_successful is a method, not a property - must call it
        is_successful_attr = getattr(history, "is_successful")
        if callable(is_successful_attr):
            is_successful = is_successful_attr()
        else:
            is_successful = is_successful_attr
    
    # Check for errors - has_errors might also be a method
    if hasattr(history, "has_errors"):
        has_errors_attr = getattr(history, "has_errors")
        has_errors_value = has_errors_attr() if callable(has_errors_attr) else has_errors_attr
        
        if has_errors_value:
            # Extract error messages
            if hasattr(history, "errors"):
                errors = history.errors()
                if errors:
                    error_message = "; ".join(str(e) for e in errors)
    
    # Extract final result using the proper method
    final_message = ""
    try:
        # Use the proper final_result() method
        if hasattr(history, "final_result"):
            final_message = history.final_result()
        else:
            print("final_result() method not found, falling back to manual extraction")
            # Fallback to manual extraction if the method doesn't exist
            if hasattr(history, "extracted_content"):
                contents = history.extracted_content()
                if contents:
                    final_message = contents[-1]  # Get the last extracted content
            elif hasattr(history, "__iter__"):
                # If history is iterable, get the last item with extracted content
                for action_result in reversed(list(history)):
                    if (
                        hasattr(action_result, "extracted_content")
                        and action_result.extracted_content
                    ):
                        final_message = action_result.extracted_content
                        break
    except Exception as e:
        print(f"Error extracting final message: {e}")
        final_message = "Could not extract final message"
        error_message = str(e) if not error_message else f"{error_message}; {e}"

    # Clean up - stop browser session and terminate provider session
    try:
        print("Stopping browser session...")
        await browser_session.stop()
        print("Browser session stopped successfully")
    except Exception as e:
        print(f"Error stopping browser session: {e}")

    # Provider-specific cleanup using the provider modules
    session_url = None
    if (
        provider == "anchor"
        and "anchor_client" in locals()
        and "anchor_session" in locals()
    ):
        session_url = anchor_cleanup(anchor_client, anchor_session)
    elif (
        provider == "browserbase"
        and "browserbase_session_id" in locals()
        and "bb_client" in locals()
    ):
        session_url = browserbase_cleanup(bb_client, browserbase_session_id)
    elif provider == "steelbrowser" and "steel_session_id" in locals():
        session_url = steel_cleanup(steel_session_id)
    elif provider == "hyperbrowser" and "hyperbrowser_session_id" in locals():
        session_url = hyperbrowser_cleanup(hyperbrowser_session_id)

    # Return the final result, session URL, success status, and error message
    return final_message, session_url, is_successful, error_message


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run browser automation with different providers"
    )
    parser.add_argument(
        "--provider",
        choices=["anchor", "browserbase", "steelbrowser", "hyperbrowser"],
        default="anchor",
        help="Browser provider to use (default: anchor)",
    )
    parser.add_argument(
        "--no-stealth",
        action="store_true",
        help="Disable advanced stealth mode for Browserbase, Steel, and Hyperbrowser (stealth is enabled by default)",
    )
    parser.add_argument(
        "--task",
        type=str,
        default="Check the score of the last 3 patriots games",
        help="Custom task for the browser agent (default: 'Check the score of the last 3 patriots games')",
    )
    args = parser.parse_args()

    # For all providers, stealth is enabled by default, disabled only with --no-stealth
    stealth_enabled = not args.no_stealth

    final_result, session_data, is_successful, error_message = asyncio.run(
        main(provider=args.provider, stealth=stealth_enabled, task=args.task)
    )
    print("\n=== Final Results ===")
    print("Success:", is_successful)
    print("Final Result (from history.final_result()):", final_result)
    if error_message:
        print("Error Message:", error_message)

    if args.provider == "browserbase" and session_data:
        print("Browserbase Session URL:", session_data)
    elif args.provider == "anchor" and session_data:
        print("Anchor Session Recording:", session_data)
    elif args.provider == "steelbrowser" and session_data:
        print("Steel Session Recording URL:", session_data)
    elif args.provider == "hyperbrowser" and session_data:
        print("Hyperbrowser Session URL:", session_data)
