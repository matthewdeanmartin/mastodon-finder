# tests/test_init.py

from pathlib import Path

import pytest

from mastodon_finder.init import (
    CONFIG_FILENAME,
    GITIGNORE_LINE,
    TOML_TEMPLATE,
    create_default_config,
)

# --- Fixtures ---


@pytest.fixture
def isolated_dir(tmp_path: Path, monkeypatch):
    """
    Creates an isolated temporary directory and changes
    the current working directory to it for the test.
    """
    # Change CWD to the temp path so that files are
    # created relative to it.
    monkeypatch.chdir(tmp_path)
    return tmp_path


# --- Test Cases ---


def test_create_default_config_no_files_exist(isolated_dir: Path, capsys):
    """
    Test Case 1: Neither finder.toml nor .gitignore exist.
    Expects both files to be created with the correct content.
    """
    config_file = isolated_dir / CONFIG_FILENAME
    gitignore_file = isolated_dir / ".gitignore"

    # Verify files don't exist initially
    assert not config_file.exists()
    assert not gitignore_file.exists()

    # Run the function
    create_default_config()

    # Capture print output
    out, _ = capsys.readouterr()

    # Verify finder.toml was created
    assert config_file.exists()
    assert config_file.read_text() == TOML_TEMPLATE.strip()
    assert f"Created default config file: '{CONFIG_FILENAME}'" in out

    # Verify .gitignore was created
    assert gitignore_file.exists()
    assert gitignore_file.read_text() == GITIGNORE_LINE.strip()
    assert "Created '.gitignore' and added config file to it." in out


def test_create_default_config_toml_exists(isolated_dir: Path, capsys):
    """
    Test Case 2: finder.toml already exists.
    Expects finder.toml to NOT be overwritten.
    Expects .gitignore to be created (as it's missing).
    """
    config_file = isolated_dir / CONFIG_FILENAME
    gitignore_file = isolated_dir / ".gitignore"

    # Create a pre-existing config file
    original_content = "# This is a custom config"
    config_file.write_text(original_content)

    # Run the function
    create_default_config()

    # Capture print output
    out, _ = capsys.readouterr()

    # Verify finder.toml was NOT modified
    assert config_file.read_text() == original_content
    assert f"'{CONFIG_FILENAME}' already exists." in out

    # Verify .gitignore was still created
    assert gitignore_file.exists()
    assert gitignore_file.read_text() == GITIGNORE_LINE.strip()
    assert "Created '.gitignore' and added config file to it." in out


def test_create_default_config_gitignore_exists_empty(isolated_dir: Path, capsys):
    """
    Test Case 3: .gitignore exists but is empty (or just doesn't have the line).
    Expects finder.toml to be created.
    Expects .gitignore to be appended to.
    """
    config_file = isolated_dir / CONFIG_FILENAME
    gitignore_file = isolated_dir / ".gitignore"

    # Create a pre-existing .gitignore file
    original_content = "# Existing gitignore rules\n"
    gitignore_file.write_text(original_content)

    # Run the function
    create_default_config()

    # Capture print output
    out, _ = capsys.readouterr()

    # Verify finder.toml was created
    assert config_file.exists()
    assert f"Created default config file: '{CONFIG_FILENAME}'" in out

    # Verify .gitignore was appended to
    final_content = gitignore_file.read_text()
    assert final_content == original_content + GITIGNORE_LINE
    assert f"Added '{CONFIG_FILENAME}' to existing '.gitignore'." in out


def test_create_default_config_gitignore_exists_with_line(isolated_dir: Path, capsys):
    """
    Test Case 4: .gitignore exists AND already contains the line.
    Expects finder.toml to be created.
    Expects .gitignore to NOT be modified.
    """
    config_file = isolated_dir / CONFIG_FILENAME
    gitignore_file = isolated_dir / ".gitignore"

    # Create a pre-existing .gitignore file that already has the line
    original_content = f"# Existing rules\n{GITIGNORE_LINE}\n# More rules\n"
    gitignore_file.write_text(original_content)

    # Run the function
    create_default_config()

    # Capture print output
    out, _ = capsys.readouterr()

    # Verify finder.toml was created
    assert config_file.exists()
    assert f"Created default config file: '{CONFIG_FILENAME}'" in out

    # Verify .gitignore was NOT modified
    assert gitignore_file.read_text() == original_content
    assert f"'{CONFIG_FILENAME}' already in '.gitignore'." in out
