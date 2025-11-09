import logging
import re
from dataclasses import dataclass
from typing import Literal

import openai

import mastodon_finder.config as config
from mastodon_finder.enrich import AccountDossier

log = logging.getLogger(__name__)

# --- Data Structures ---
Decision = Literal["FOLLOW", "MAYBE", "SKIP", "ERROR"]
DECISION_TOKENS = ("FOLLOW", "MAYBE", "SKIP", "ERROR")

@dataclass
class EvaluationResult:
    dossier: AccountDossier
    decision: Decision
    reasoning: str


# --- LLM Client Initialization ---
# Determine API key and base URL
# Prioritize OpenRouter, fallback to OpenAI
api_key_to_use = config.OPENROUTER_API_KEY or config.OPENAI_API_KEY
base_url_to_use = config.OPENROUTER_BASE_URL or None  # None defaults to OpenAI

# Determine model
if config.OPENROUTER_MODEL:
    model_to_use = config.OPENROUTER_MODEL
else:
    model_to_use = config.DEFAULT_OPENAI_MODEL

# Instantiate the client
# This is done at the module level so it's shared
llm_client = None
if api_key_to_use:
    llm_client = openai.OpenAI(
        api_key=api_key_to_use,
        base_url=base_url_to_use,
    )
    log.info(
        f"Initialized LLM client. Model: '{model_to_use}', Base URL: '{base_url_to_use or 'default OpenAI'}'"
    )
else:
    log.warning("LLM client not initialized: No API key found. (OK for --dry-run)")


# --- LLM Runner (Real) ---
def run_llm(system_prompt: str, user_prompt: str) -> str:
    """
    Calls the configured LLM (OpenAI or OpenRouter)
    with the provided system and user prompts.
    """
    if not llm_client:
        log.error("LLM client is not initialized. Cannot make API call.")
        return "DECISION: ERROR\nREASONING: LLM client not initialized. Check API keys."

    log.info(f"Calling LLM (model: {model_to_use})...")

    # Log the prompts that will be sent
    print("\n" + "=" * 20 + " LLM SYSTEM PROMPT " + "=" * 20)
    print(system_prompt)
    print("\n" + "=" * 20 + " LLM USER PROMPT " + "=" * 20)
    print(user_prompt)
    print("=" * 62 + "\n")

    try:
        response = llm_client.chat.completions.create(
            model=model_to_use,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=config.LLM_TEMPERATURE,
            timeout=config.LLM_TIMEOUT,
        )

        output = response.choices[0].message.content
        if not output:
            raise ValueError("LLM returned an empty response.")

        log.info(f"LLM returned: {output.strip().splitlines()[0]}")
        return output

    except openai.APITimeoutError:
        log.error(f"LLM call timed out after {config.LLM_TIMEOUT}s.")
        return "DECISION: ERROR\nREASONING: LLM call timed out."
    except openai.APIConnectionError as e:
        log.error(f"LLM connection error: {e}")
        return f"DECISION: ERROR\nREASONING: LLM connection error: {e}"
    except openai.AuthenticationError as e:
        log.error(f"LLM authentication error. Check your API key. {e}")
        return "DECISION: ERROR\nREASONING: LLM authentication error. Check API key."
    except openai.RateLimitError as e:
        log.error(f"LLM rate limit exceeded: {e}")
        return "DECISION: ERROR\nREASONING: LLM rate limit exceeded."
    except Exception as e:
        log.error(f"An unexpected error occurred during the LLM call: {e}")
        return f"DECISION: ERROR\nREASONING: Unexpected LLM error: {e}"


# --- LLM Output Parser ---
def parse_llm_output(dossier: "AccountDossier", output: str) -> "EvaluationResult":
    """
    Parses the plain-text LLM output into a structured result.

    Handles:
    - Proper tagged output:
        DECISION: FOLLOW
        REASONING: ...
    - Output that is *only* a decision word (e.g. "MAYBE")
    - Output that contains a decision word but no tags
    - Bad / unparsable output -> returns MAYBE with diagnostic
    """
    raw = (output or "").strip()

    # --- 0. Empty / None output
    if not raw:
        log.warning(f"LLM output empty for {dossier.acct}. Defaulting to MAYBE.")
        return EvaluationResult(
            dossier=dossier,
            decision="MAYBE",
            reasoning="LLM_PARSE_ERROR: empty output",
        )

    # --- 1. Try strict tagged form first ------------------------------------
    decision_match = re.search(
        r"DECISION:\s*(FOLLOW|MAYBE|SKIP|ERROR)\b", raw, re.IGNORECASE
    )
    reasoning_match = re.search(r"REASONING:\s*([\s\S]+)", raw, re.IGNORECASE)

    if decision_match:
        decision = decision_match.group(1).upper()
        if reasoning_match:
            reasoning = reasoning_match.group(1).strip() or "N/A"
        else:
            # Tagged decision but no tagged reasoning -> treat remainder as reasoning
            # or just say N/A
            reasoning = "N/A"
        if decision == "ERROR":
            log.warning(f"LLM API error for {dossier.acct}: {reasoning}")
        return EvaluationResult(dossier=dossier, decision=decision, reasoning=reasoning)

    # --- 2. No tags. Try to detect a standalone decision --------------------
    # Case A: output is exactly "FOLLOW" / "MAYBE" / "SKIP" / "ERROR"
    upper_raw = raw.upper()
    if upper_raw in DECISION_TOKENS:
        decision = upper_raw
        reasoning = "N/A"
        if decision == "ERROR":
            log.warning(f"LLM API error for {dossier.acct}: {raw}")
        return EvaluationResult(dossier=dossier, decision=decision, reasoning=reasoning)

    # Case B: output contains one of the tokens, but untagged.
    # e.g. "FOLLOW - strong match on keywords"
    # We'll grab the first occurring token and treat the rest as reasoning.
    token_pattern = re.compile(r"\b(FOLLOW|MAYBE|SKIP|ERROR)\b", re.IGNORECASE)
    token_match = token_pattern.search(raw)
    if token_match:
        decision = token_match.group(1).upper()
        # reasoning = everything except the first occurrence of the token
        before = raw[:token_match.start()].strip()
        after = raw[token_match.end():].strip()
        if before or after:
            reasoning_parts = []
            if before:
                reasoning_parts.append(before)
            if after:
                reasoning_parts.append(after)
            reasoning = " ".join(reasoning_parts).strip()
        else:
            reasoning = "N/A"

        if decision == "ERROR":
            log.warning(f"LLM API error for {dossier.acct}: {reasoning or raw}")
        return EvaluationResult(dossier=dossier, decision=decision, reasoning=reasoning)

    # --- 3. Totally unparsable -> Spec 8 behavior ---------------------------
    log.warning(
        f"LLM output parse error for {dossier.acct}. Defaulting to MAYBE. Output: {raw}"
    )
    return EvaluationResult(
        dossier=dossier,
        decision="MAYBE",
        reasoning=f"LLM_PARSE_ERROR: Could not locate decision token. Full output: {raw}",
    )