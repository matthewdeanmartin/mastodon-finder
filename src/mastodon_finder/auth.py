# mastodon_finder/auth.py
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from mastodon import Mastodon
from mastodon.Mastodon import MastodonError
from rich import print as rprint

log = logging.getLogger(__name__)

# --- Configuration ---
APP_NAME = "mastodon_finder"
SCOPES = ["read"]  # "read" covers search, accounts, and follows
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"  # Standard for CLI apps
ENV_FILE = Path(".env")


def _get_instance_url() -> str:
    """Prompts the user for their instance URL until a valid one is given."""
    while True:
        rprint(
            "\n[bold]Step 1: Enter your Mastodon instance URL[/bold] (e.g., [cyan]mastodon.social[/cyan])"
        )
        try:
            url = input("Instance URL: ").strip()
            if not url:
                continue
            if not (url.startswith("http://") or url.startswith("https://")):
                rprint(
                    f"[yellow]No protocol found, prepending 'https://' -> https://{url}[/yellow]"
                )
                url = f"https://{url}"
            return url
        except KeyboardInterrupt:
            rprint("\n[red]Authentication cancelled.[/red]")
            sys.exit(0)


def _sanitize_url(url: str) -> str:
    """Ensures URL has https and no trailing slash for the API."""
    if not (url.startswith("http://") or url.startswith("https://")):
        url = f"https://{url}"
    return url.rstrip("/")


def _write_env_file(api_base_url: str, access_token: str) -> None:
    """Appends the Mastodon credentials to the .env file."""
    rprint(f"\n[bold]Step 4: Saving credentials to {ENV_FILE.name}[/bold]")
    try:
        with open(ENV_FILE, "a", encoding="utf-8") as f:
            f.write("\n\n# Added by mastodon-finder auth\n")
            f.write(f"MASTODON_BASE_URL={api_base_url}\n")
            f.write(f"MASTODON_ACCESS_TOKEN={access_token}\n")

        rprint(
            f"[green]Success![/green] Credentials saved to [cyan]{ENV_FILE.name}[/cyan]."
        )
        rprint("You can now run the 'run' command.")
        rprint(
            f"[dim](Remember to add '{ENV_FILE.name}' to your .gitignore file if it's not already)[/dim]"
        )

    except Exception as e:
        log.error(f"Failed to write to {ENV_FILE.name}: {e}")
        rprint(f"[red]Error:[/red] Could not write to {ENV_FILE.name}.")
        rprint("Please add the following lines to your .env file manually:")
        rprint(f"MASTODON_BASE_URL={api_base_url}")
        rprint(f"MASTODON_ACCESS_TOKEN={access_token}")


def run_auth_flow():
    """
    Runs the full interactive OAuth flow to get and save user credentials.
    """
    client: Optional[Mastodon] = None
    api_base_url = ""

    try:
        # --- Step 1: Get URL and Register App ---
        rprint("[bold]--- Mastodon Finder Authentication ---[/bold]")
        rprint(
            "This will guide you through getting an API token for your Mastodon account."
        )

        raw_url = _get_instance_url()
        api_base_url = _sanitize_url(raw_url)

        rprint(f"\nRegistering 'mastodon_finder' with [cyan]{api_base_url}[/cyan]...")

        client_id, client_secret = Mastodon.create_app(
            APP_NAME,
            api_base_url=api_base_url,
            scopes=SCOPES,
            redirect_uris=REDIRECT_URI,
        )

        rprint("[green]App registered successfully.[/green]")

        # --- Step 2: Get Authorization URL ---
        client = Mastodon(
            client_id=client_id,
            client_secret=client_secret,
            api_base_url=api_base_url,
        )
        auth_url = client.auth_request_url(redirect_uris=REDIRECT_URI, scopes=SCOPES)

        rprint("\n[bold]Step 2: Authorize the App[/bold]")
        rprint("1. Open this URL in your web browser:")
        rprint(f"\n[link={auth_url}]{auth_url}[/link]\n")
        rprint("2. Log in and click 'Authorize'.")
        rprint("3. You will be given an [bold]Authorization code[/bold].")
        rprint("4. Paste that code back here and press Enter.")

        # --- Step 3: Get Code and Log In ---
        auth_code = input("\nPaste Authorization code: ").strip()
        if not auth_code:
            raise ValueError("Authorization code cannot be empty.")

        rprint("\n[bold]Step 3: Exchanging code for access token...[/bold]")
        access_token = client.log_in(
            code=auth_code,
            redirect_uri=REDIRECT_URI,
            scopes=SCOPES,
        )

        rprint("[green]Login successful![/green]")

        # --- Step 4: Save to .env ---
        _write_env_file(api_base_url, access_token)

    except KeyboardInterrupt:
        rprint("\n[red]Authentication cancelled.[/red]")
        sys.exit(0)
    except MastodonError as e:
        log.error(f"Mastodon API error: {e}")
        rprint("\n[red]Error:[/red] A Mastodon API error occurred.")
        if "getaddrinfo failed" in str(e) or "Name or service not known" in str(e):
            rprint(
                f"Could not connect to [cyan]{api_base_url}[/cyan]. Please check the URL and try again."
            )
        elif "Invalid authorization code" in str(e):
            rprint("The authorization code was incorrect. Please run 'auth' again.")
        else:
            rprint(f"Details: {e}")
        sys.exit(1)
    except Exception as e:
        log.error(f"An unexpected error occurred: {e}")
        rprint(f"\n[red]An unexpected error occurred:[/red] {e}")
        sys.exit(1)
