#!/usr/bin/env python3
# encoding: utf-8

import sys
import json
import time
from workflow import Workflow, web

API_BASE = "https://api.capacities.io"

# Cache settings
SPACE_INFO_CACHE_KEY = "space_info_cache"
SPACE_INFO_CACHE_TTL = 3600  # 1 hour cache
RATE_LIMIT_KEY = "space_info_rate_limit"
RATE_LIMIT_WINDOW = 60  # 1 minute
RATE_LIMIT_MAX_REQUESTS = 4  # API allows 5


def get_api_token(wf):
    import os

    # Try environment variables first (for Alfred user config)
    possible_names = ["api_token", "API_TOKEN", "capacities_api_token"]

    for name in possible_names:
        token = os.getenv(name)
        if token:
            return token

    # Try workflow settings
    token = wf.settings.get("api_token")
    if token:
        return token

    return None


def get_default_space_id(wf):
    import os

    # Try environment variables first (for Alfred user config)
    possible_names = ["default_space_id", "DEFAULT_SPACE_ID"]

    for name in possible_names:
        space_id = os.getenv(name)
        if space_id:
            return space_id

    # Try workflow settings
    space_id = wf.settings.get("default_space_id")
    if space_id:
        return space_id

    return None


def check_rate_limit(wf, space_id):
    """Check if we can make a space-info request without hitting rate limit"""
    now = time.time()
    rate_limit_data = wf.cached_data(RATE_LIMIT_KEY, max_age=0) or {}

    # Clean up old entries
    space_requests = rate_limit_data.get(space_id, [])
    space_requests = [
        req_time for req_time in space_requests if now - req_time < RATE_LIMIT_WINDOW
    ]

    # Check if we can make another request
    if len(space_requests) >= RATE_LIMIT_MAX_REQUESTS:
        return False

    # Record this request
    space_requests.append(now)
    rate_limit_data[space_id] = space_requests
    wf.cache_data(RATE_LIMIT_KEY, rate_limit_data)

    return True


def get_cached_space_info(wf, space_id):
    """Get space info from cache or API with rate limiting"""
    # Try cache first
    cache_data = (
        wf.cached_data(SPACE_INFO_CACHE_KEY, max_age=SPACE_INFO_CACHE_TTL) or {}
    )

    if space_id in cache_data:
        return cache_data[space_id], None

    # Check rate limit before making API call
    if not check_rate_limit(wf, space_id):
        return None, "Rate limit exceeded for space-info requests"

    # Make API request directly (avoid circular reference)
    token = get_api_token(wf)
    if not token:
        return None, "API token not found"

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    url = f"{API_BASE}/space-info?spaceid={space_id}"

    try:
        response = web.get(url, headers=headers)
        response.raise_for_status()

        if response.text.strip():
            result = response.json()
        else:
            result = {"success": True}
    except Exception as e:
        return None, f"Space info request failed: {str(e)}"

    # Cache the result
    cache_data[space_id] = result
    wf.cache_data(SPACE_INFO_CACHE_KEY, cache_data)

    return result, None


def get_object_type_name(wf, space_id, structure_id):
    """Get the human-readable name for an object type (structure)"""
    # Handle built-in types first
    builtin_types = {
        "RootDailyNote": "Daily Note",
        "RootPage": "Page",
        "MediaWebResource": "Web Resource",
        "MediaFile": "File",
        "MediaImage": "Image",
    }

    if structure_id in builtin_types:
        return builtin_types[structure_id]

    # For empty or invalid inputs, return as-is
    if not structure_id:
        return "Unknown"

    # For custom types, only try cache lookup (no new API calls during search)
    if space_id and structure_id:
        try:
            # Only check cache, don't make new API requests
            cache_data = (
                wf.cached_data(SPACE_INFO_CACHE_KEY, max_age=SPACE_INFO_CACHE_TTL) or {}
            )

            if space_id in cache_data:
                space_info = cache_data[space_id]
                # The API returns object types in 'structures', not 'collections'
                structures = space_info.get("structures", [])

                for structure in structures:
                    if structure.get("id") == structure_id:
                        return structure.get("title", structure_id)
        except Exception as e:
            wf.logger.debug(f"Error getting object type name: {e}")
            pass

    # Fallback to structure ID
    return structure_id


def make_api_request(wf, endpoint, method="GET", data=None):
    token = get_api_token(wf)
    if not token:
        return (
            None,
            "API token not found. Use 'cap config' to see configuration instructions.",
        )

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    url = f"{API_BASE}{endpoint}"

    try:
        if method == "GET":
            response = web.get(url, headers=headers)
        elif method == "POST":
            response = web.post(
                url, headers=headers, data=json.dumps(data) if data else None
            )

        response.raise_for_status()

        # Some endpoints might return empty responses on success
        if response.text.strip():
            return response.json(), None
        else:
            return {"success": True}, None

    except Exception as e:
        return (
            None,
            f"API request failed: {str(e)} (Status: {getattr(response, 'status_code', 'unknown') if 'response' in locals() else 'connection error'})",
        )


def search_content(wf, query):
    # Require minimum 3 characters for search to reduce API calls
    if len(query.strip()) < 3:
        wf.add_item(
            "Keep typing...",
            f"Enter at least 3 characters to search (currently: {len(query.strip())})",
            icon="icon.png",
        )
        return

    # Check if user has configured a default space ID
    default_space_id = get_default_space_id(wf)

    if default_space_id:
        space_ids = [default_space_id]
    else:
        # Get all spaces for the search
        spaces_result, spaces_error = make_api_request(wf, "/spaces")
        if spaces_error or not spaces_result or not spaces_result.get("spaces"):
            wf.add_item("Error", "Could not get spaces for search", icon="icon.png")
            return

        space_ids = [space["id"] for space in spaces_result["spaces"]]

    data = {"searchTerm": query, "spaceIds": space_ids, "mode": "fullText"}

    result, error = make_api_request(wf, "/search", method="POST", data=data)
    if error:
        wf.add_item("Error", error, icon="icon.png")
        return

    if not result or not result.get("results"):
        wf.add_item("No results", f"No content found for '{query}'", icon="icon.png")
        return

    for item in result["results"][:20]:
        title = item.get("title", "Untitled")
        space_name = item.get("spaceName", "Unknown Space")
        space_id = item.get("spaceId", "")
        structure_id = item.get("structureId", item.get("type", "Unknown"))

        # Get the human-readable object type name (with fast fallback)
        item_type = get_object_type_name(wf, space_id, structure_id)

        subtitle = f"Type: {item_type}"

        # Add snippet if available
        if item.get("snippet"):
            snippet = (
                item["snippet"][:80] + "..."
                if len(item["snippet"]) > 80
                else item["snippet"]
            )
            subtitle += f" | {snippet}"

        # Create Capacities app URL
        space_id = item.get("spaceId", "")
        item_id = item.get("id", "")
        structure_id = item.get("structureId", "")

        if space_id and item_id:
            if structure_id:
                capacities_url = f"capacities://{space_id}/{item_id}?bid={structure_id}"
            else:
                capacities_url = f"capacities://{space_id}/{item_id}"
        else:
            capacities_url = item.get("webUrl", "")

        wf.add_item(
            title,
            subtitle,
            arg=capacities_url,
            valid=bool(capacities_url),
            icon="icon.png",
        )


def prepare_save_weblink(wf, args):
    if len(args) < 2:
        wf.add_item(
            "Save Weblink",
            "Format: caps <url> [title] - Press Enter to save",
            icon="icon.png",
        )
        return

    url = args[1]
    title = " ".join(args[2:]) if len(args) > 2 else None

    # Validate URL
    import re

    if not re.match(r"https?://", url):
        wf.add_item(
            "Invalid URL", "Please provide a valid HTTP/HTTPS URL", icon="icon.png"
        )
        return

    # Show preview of what will be saved
    subtitle = f"URL: {url}"
    if title:
        subtitle += f" | Title: {title}"
    subtitle += " - Press Enter to save"

    wf.add_item(
        "Save to Capacities",
        subtitle,
        arg=f"save_execute:{url}:{title or ''}",
        valid=True,
        icon="icon.png",
    )


def save_weblink(wf, url, title=None):
    # Check if user has configured a default space ID
    default_space_id = get_default_space_id(wf)

    if not default_space_id:
        # Get the first available space
        spaces_result, error = make_api_request(wf, "/spaces")
        if error:
            wf.add_item("Error", error, icon="icon.png")
            return

        if not spaces_result or not spaces_result.get("spaces"):
            wf.add_item("Error", "No spaces found", icon="icon.png")
            return

        default_space_id = spaces_result["spaces"][0]["id"]

    data = {"spaceId": default_space_id, "url": url}

    if title:
        data["titleOverwrite"] = title

    result, error = make_api_request(wf, "/save-weblink", method="POST", data=data)
    if error:
        wf.add_item("Error", error, icon="icon.png")
        return

    wf.add_item(
        "Weblink saved", f"Successfully saved {url} to Capacities", icon="icon.png"
    )


def prepare_save_note(wf, args):
    if len(args) < 2:
        wf.add_item(
            "Add to Daily Note",
            "Format: capn <text> - Press Enter to save",
            icon="icon.png",
        )
        return

    text = " ".join(args[1:])

    if len(text.strip()) == 0:
        wf.add_item(
            "Empty Note", "Please enter some text for the note", icon="icon.png"
        )
        return

    # Show preview of what will be saved
    preview = text[:100] + "..." if len(text) > 100 else text

    wf.add_item(
        "Add to Daily Note",
        f"Text: {preview} - Press Enter to save",
        arg=f"note_execute:{text}",
        valid=True,
        icon="icon.png",
    )


def save_to_daily_note(wf, text):
    # Check if user has configured a default space ID
    default_space_id = get_default_space_id(wf)

    if not default_space_id:
        # Get the first available space
        spaces_result, error = make_api_request(wf, "/spaces")
        if error:
            wf.add_item("Error", error, icon="icon.png")
            return

        if not spaces_result or not spaces_result.get("spaces"):
            wf.add_item("Error", "No spaces found", icon="icon.png")
            return

        default_space_id = spaces_result["spaces"][0]["id"]

    data = {"spaceId": default_space_id, "mdText": text}

    result, error = make_api_request(
        wf, "/save-to-daily-note", method="POST", data=data
    )
    if error:
        wf.add_item("Error", error, icon="icon.png")
        return

    wf.add_item(
        "Added to daily note",
        f"Successfully added text to today's daily note",
        icon="icon.png",
    )


def show_help(wf):
    commands = [
        ("cap <query>", "Search content (3+ chars, auto-delayed)"),
        ("caps <url> [title]", "Save weblink (press Enter to confirm)"),
        ("capn <text>", "Add to daily note (press Enter to confirm)"),
    ]

    for command, description in commands:
        wf.add_item(command, description, icon="icon.png")


def main(wf):
    import sys
    import os

    # Get arguments - try environment variable first (Alfred actions use this)
    env_query = os.environ.get("query", "").strip()
    if env_query:
        # Check if this is an execution command - don't split if it is
        if env_query.startswith(("note_execute:", "save_execute:")):
            raw_command = env_query
            args = [env_query]  # Keep as single argument
        else:
            args = env_query.split()
    elif len(sys.argv) > 1:
        # Parse the query string from Alfred script filter
        query = sys.argv[1].strip()
        if query:
            if query.startswith(("note_execute:", "save_execute:")):
                raw_command = query
                args = [query]
            else:
                args = query.split()
        else:
            args = []
    else:
        args = wf.args if wf.args else []

    if not args:
        show_help(wf)
        wf.send_feedback()
        return

    command = args[0]
    command_lower = command.lower()

    # Handle Capacities URLs - pass them through to the URL opener
    if command.startswith("capacities://"):
        # Just output the URL for the URL opener action to handle
        print(command)
        return

    # Handle execution commands (triggered by Enter)
    elif command_lower.startswith("save_execute:"):
        # Remove the command prefix
        content = command[len("save_execute:") :]
        # Split only on the last colon to separate URL from title
        if ":" in content:
            # Find the last colon that's not part of the URL protocol
            colon_pos = content.rfind(":")
            if (
                colon_pos > content.find("://") + 3
            ):  # Make sure it's not the protocol colon
                url = content[:colon_pos]
                title = content[colon_pos + 1 :] if content[colon_pos + 1 :] else None
            else:
                url = content
                title = None
        else:
            url = content
            title = None
        save_weblink(wf, url, title)
    elif command_lower.startswith("note_execute:"):
        parts = command.split(":", 1)
        if len(parts) >= 2:
            text = parts[1]
            save_to_daily_note(wf, text)
    # Handle separate script filter commands
    elif command_lower == "caps":
        # Handle "caps url title" from separate script filter
        new_args = ["save"] + args[1:] if len(args) > 1 else ["save"]
        prepare_save_weblink(wf, new_args)
    elif command_lower == "capn":
        # Handle "capn text" from separate script filter
        new_args = ["note"] + args[1:] if len(args) > 1 else ["note"]
        prepare_save_note(wf, new_args)
    else:
        # Default behavior: treat everything else as search
        query = " ".join(args)
        if len(query.strip()) >= 3:
            search_content(wf, query)
        else:
            show_help(wf)

    wf.send_feedback()


if __name__ == "__main__":
    wf = Workflow()
    sys.exit(wf.run(main))
