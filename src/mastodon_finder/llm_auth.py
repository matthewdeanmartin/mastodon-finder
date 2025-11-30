# mastodon_finder/llm_auth.py
from __future__ import annotations

import logging
import sys
from pathlib import Path

from rich import print as rprint

log = logging.getLogger(__name__)

# --- Configuration ---
ENV_FILE = Path(".env")
OPENROUTER_BASE_URL_CONST = "https://openrouter.ai/api/v1"


def _write_llm_env_file(
    openrouter_key: str, openrouter_model: str, openai_key: str
) -> None:
    """Appends the LLM credentials to the .env file."""
    rprint(f"\n[bold]Step 4: Saving credentials to {ENV_FILE.name}[/bold]")

    lines_to_add = ["\n\n# Added by mastodon-finder llm-auth\n"]
    keys_saved = []

    if openrouter_key:
        lines_to_add.append(f"OPENROUTER_API_KEY={openrouter_key}\n")
        lines_to_add.append(f"OPENROUTER_BASE_URL={OPENROUTER_BASE_URL_CONST}\n")
        keys_saved.append("OpenRouter Key")
        if openrouter_model:
            lines_to_add.append(f"OPENROUTER_MODEL={openrouter_model}\n")
            keys_saved.append("OpenRouter Model")

    if openai_key:
        lines_to_add.append(f"OPENAI_API_KEY={openai_key}\n")
        keys_saved.append("OpenAI Key")

    try:
        with open(ENV_FILE, "a", encoding="utf-8") as f:
            f.writelines(lines_to_add)

        rprint(
            f"[green]Success![/green] Saved: [cyan]{', '.join(keys_saved)}[/cyan] to [cyan]{ENV_FILE.name}[/cyan]."
        )
        rprint(
            f"[dim](Remember to add '{ENV_FILE.name}' to your .gitignore file if it's not already)[/dim]"
        )

    except Exception as e:
        log.error(f"Failed to write to {ENV_FILE.name}: {e}")
        rprint(f"[red]Error:[/red] Could not write to {ENV_FILE.name}.")
        rprint("Please add the following lines to your .env file manually:")
        for line in lines_to_add:
            if line.strip():
                rprint(f"[cyan]{line.strip()}[/cyan]")


def run_llm_auth_flow():
    """
    Runs the full interactive flow to get and save LLM API keys.
    """
    try:
        rprint("[bold]--- LLM API Key Setup ---[/bold]")
        rprint(
            "This will guide you through saving API keys for OpenRouter and/or OpenAI."
        )
        rprint("Press [bold]Enter[/bold] at any prompt to skip that service.")

        # --- Step 1: OpenRouter Key ---
        rprint(
            "\n[bold]Step 1: OpenRouter (Recommended)[/bold] (https://openrouter.ai/keys)"
        )
        openrouter_key = input(
            "Paste OpenRouter API Key (or press Enter to skip): "
        ).strip()

        openrouter_model = ""
        if openrouter_key:
            # --- Step 2: OpenRouter Model (Optional) ---
            rprint("\n[bold]Step 2: OpenRouter Model (Optional)[/bold]")
            rprint(
                "You can set a default model name to use (e.g., 'mistralai/mistral-7b-instruct')."
            )
            openrouter_model = input("Model name (or press Enter to skip): ").strip()

        # --- Step 3: OpenAI Key ---
        rprint(
            "\n[bold]Step 3: OpenAI (Optional)[/bold] (https://platform.openai.com/api-keys)"
        )
        openai_key = input("Paste OpenAI API Key (or press Enter to skip): ").strip()

        # --- Step 4: Save ---
        if not openrouter_key and not openai_key:
            rprint("\n[yellow]No API keys were provided. Exiting.[/yellow]")
            sys.exit(0)

        _write_llm_env_file(openrouter_key, openrouter_model, openai_key)

    except KeyboardInterrupt:
        rprint("\n[red]Authentication cancelled.[/red]")
        sys.exit(0)
    except Exception as e:
        log.error(f"An unexpected error occurred: {e}")
        rprint(f"\n[red]An unexpected error occurred:[/red] {e}")
        sys.exit(1)
