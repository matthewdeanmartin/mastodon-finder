# tests/test_llm_runner.py

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from mastodon_finder import llm_runner
from mastodon_finder.enrich import AccountDossier
from mastodon_finder.settings import Settings

# --- Fixtures ---


@pytest.fixture
def mock_dossier() -> AccountDossier:
    """Provides a minimal dossier object for parsing tests."""
    return AccountDossier(
        account_id=1,
        acct="@test@example.com",
        display_name="Test",
        url="",
        followers_count=0,
        following_count=0,
        statuses_count=0,
        created_at=datetime.now(),
        note_html="",
        note_text="",
        fields={},
        discovered_via=[],
        bot=False,
        reply_posts_found=0,
    )


@pytest.fixture
def mock_base_settings() -> Settings:
    """Returns a default Settings object."""
    return Settings()


@pytest.fixture(autouse=True)
def reset_llm_singleton(monkeypatch):
    """
    Ensures the global client singleton is reset before each test
    to prevent state leakage.
    """
    monkeypatch.setattr(llm_runner, "_LLM_CLIENT_SINGLETON", None)
    monkeypatch.setattr(llm_runner, "_MODEL_TO_USE", "")


@pytest.fixture
def mock_openai_api():
    """Mocks the openai.OpenAI class."""
    with patch("openai.OpenAI") as mock_openai_class:
        # Mock the instance returned by the class constructor
        mock_instance = Mock()
        # Mock the chain of calls to the create method
        mock_instance.chat.completions.create = Mock()
        mock_openai_class.return_value = mock_instance
        yield mock_openai_class, mock_instance


# --- Tests for parse_llm_output ---


# Use parametrize to test all parsing variations
@pytest.mark.parametrize(
    "raw_output, expected_decision, expected_reason_contains",
    [
        # Case 1: Perfect tagged output
        (
            "DECISION: FOLLOW\nREASONING:\n- This is a great account.",
            "FOLLOW",
            "This is a great account.",
        ),
        # Case 2: Lowercase and whitespace
        (
            " decision:   maybe \n reasoning: mixed signals ",
            "MAYBE",
            "mixed signals",
        ),
        # Case 3: Only a decision word
        ("SKIP", "SKIP", "N/A"),
        # Case 4: Only an error word
        ("ERROR", "ERROR", "N/A"),
        # Case 5: Untagged decision with reasoning
        ("FOLLOW - great python dev", "FOLLOW", "great python dev"),
        # Case 6: Untagged decision with reasoning (weird format)
        ("This guy seems cool MAYBE", "MAYBE", "This guy seems cool"),
        # Case 7: Tagged decision, no reasoning
        ("DECISION: FOLLOW", "FOLLOW", "N/A"),
        # Case 8: Tagged error
        (
            "DECISION: ERROR\nREASONING: Rate limit exceeded.",
            "ERROR",
            "Rate limit exceeded.",
        ),
        # Case 9: Empty string output
        ("", "MAYBE", "LLM_PARSE_ERROR: empty output"),
        # Case 10: None output
        (None, "MAYBE", "LLM_PARSE_ERROR: empty output"),
        # Case 11: Completely unparsable
        ("This is just a random sentence.", "MAYBE", "LLM_PARSE_ERROR:"),
    ],
)
def test_parse_llm_output(
    mock_dossier, raw_output, expected_decision, expected_reason_contains
):
    """Tests the various string parsing rules for LLM output."""
    result = llm_runner.parse_llm_output(mock_dossier, raw_output)

    assert result.dossier == mock_dossier
    assert result.decision == expected_decision
    assert expected_reason_contains in result.reasoning


# --- Tests for _initialize_llm_client ---

# picks up real .env file
# def test_initialize_client_with_openai(
#     mock_base_settings, mock_openai_api
# ):
#     """Tests initialization using default OpenAI settings."""
#     mock_openai_class, _ = mock_openai_api
#     mock_base_settings.env.OPENAI_API_KEY = "sk-openai-key"
#
#     llm_runner._initialize_llm_client(mock_base_settings)
#
#     # Check that the OpenAI client was instantiated correctly
#     mock_openai_class.assert_called_once_with(
#         api_key="sk-openai-key", base_url=None
#     )
#     # Check that the singleton was set
#     assert llm_runner._LLM_CLIENT_SINGLETON is not None
#     # Check that the correct model was selected
#     assert (
#         llm_runner._MODEL_TO_USE
#         == mock_base_settings.llm.default_openai_model
#     )
#     assert llm_runner._LLM_TIMEOUT == mock_base_settings.llm.timeout
#     assert (
#         llm_runner._LLM_TEMPERATURE == mock_base_settings.llm.temperature
#     )


def test_initialize_client_with_openrouter(mock_base_settings, mock_openai_api):
    """Tests initialization using OpenRouter settings."""
    mock_openai_class, _ = mock_openai_api
    mock_base_settings.env.OPENAI_API_KEY = "sk-openai-key"  # Should be ignored
    mock_base_settings.env.OPENROUTER_API_KEY = "sk-openrouter-key"
    mock_base_settings.env.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    mock_base_settings.env.OPENROUTER_MODEL = "openrouter/model"

    llm_runner._initialize_llm_client(mock_base_settings)

    # Check that OpenRouter key and URL were prioritized
    mock_openai_class.assert_called_once_with(
        api_key="sk-openrouter-key", base_url="https://openrouter.ai/api/v1"
    )
    # Check that the singleton was set
    assert llm_runner._LLM_CLIENT_SINGLETON is not None
    # Check that the OpenRouter model was prioritized
    assert llm_runner._MODEL_TO_USE == "openrouter/model"


# picks up real .env file

# def test_initialize_client_no_api_key(mock_base_settings, mock_openai_api):
#     """Tests that the client is not initialized if no API key is found."""
#     mock_openai_class, _ = mock_openai_api
#
#     llm_runner._initialize_llm_client(mock_base_settings)
#
#     # Client constructor should not have been called
#     mock_openai_class.assert_not_called()
#     # Singleton should remain None
#     assert llm_runner._LLM_CLIENT_SINGLETON is None


def test_initialize_client_is_singleton(mock_base_settings, mock_openai_api):
    """Tests that the client is only initialized once."""
    mock_openai_class, _ = mock_openai_api
    mock_base_settings.env.OPENAI_API_KEY = "sk-key"

    # Call initialize twice
    llm_runner._initialize_llm_client(mock_base_settings)
    llm_runner._initialize_llm_client(mock_base_settings)

    # Assert constructor was only called once
    mock_openai_class.assert_called_once()


# --- Tests for run_llm ---

# picks up real .env file

# def test_run_llm_happy_path(mock_base_settings, mock_openai_api):
#     """Tests a successful run_llm call."""
#     _, mock_client_instance = mock_openai_api
#     mock_base_settings.env.OPENAI_API_KEY = "sk-key"
#
#     # Set up the mock response
#     mock_response_content = "DECISION: FOLLOW\nREASONING: Test"
#     mock_response = Mock()
#     mock_response.choices = [Mock(message=Mock(content=mock_response_content))]
#     mock_client_instance.chat.completions.create.return_value = mock_response
#
#     system_prompt = "You are a bot"
#     user_prompt = "Who am I?"
#     output = llm_runner.run_llm(
#         system_prompt, user_prompt, mock_base_settings
#     )
#
#     # Check that the API was called with correct params
#     mock_client_instance.chat.completions.create.assert_called_once_with(
#         model=mock_base_settings.llm.default_openai_model,
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt},
#         ],
#         temperature=mock_base_settings.llm.temperature,
#         timeout=mock_base_settings.llm.timeout,
#     )
#     # Check that the content was returned
#     assert output == mock_response_content

# picks up real .env file

# def test_run_llm_no_client_initialized(mock_base_settings):
#     """
#     Tests that run_llm returns an error if no API key was provided
#     (and thus the client was not initialized).
#     """
#     # No API key set in mock_base_settings
#     output = llm_runner.run_llm("sys", "user", mock_base_settings)
#
#     assert "DECISION: ERROR" in output
#     assert "LLM client not initialized" in output


@pytest.mark.parametrize(
    "api_error, expected_reason",
    [
        # (openai.APITimeoutError(), "LLM call timed out"),
        # (openai.AuthenticationError(message="auth error", response=None, body=None), "LLM authentication error"),
        # (openai.RateLimitError(message="rate limit", response=None, body=None), "LLM rate limit exceeded"),
        (Exception("Unexpected"), "Unexpected LLM error"),
    ],
)
def test_run_llm_api_errors(
    mock_base_settings, mock_openai_api, api_error, expected_reason
):
    """Tests that various openai API errors are caught and handled."""
    _, mock_client_instance = mock_openai_api
    mock_base_settings.env.OPENAI_API_KEY = "sk-key"

    # Make the API call raise the specified error
    mock_client_instance.chat.completions.create.side_effect = api_error

    output = llm_runner.run_llm("sys", "user", mock_base_settings)

    assert "DECISION: ERROR" in output
    assert expected_reason in output
