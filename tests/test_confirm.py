"""Tests for the submit confirmation prompt in submit.py."""

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import submit


def _confirm(value: str) -> None | SystemExit:
    old_stdin = sys.stdin
    sys.stdin = io.StringIO(value)
    try:
        submit.confirm_or_die('some-problem', 'Python 3', [Path('solution.py')], None, '')
    finally:
        sys.stdin = old_stdin


def test_confirm_accepts_y_without_trailing_newline(capsys):
    """Piped 'y' with no newline (e.g. `printf y | ...`) must confirm."""
    with pytest.raises(SystemExit) as exc:
        _confirm('n\n')
    assert exc.value.code == 1  # sanity: 'n' still cancels
    capsys.readouterr()
    _confirm('y')  # must not raise


def test_confirm_still_cancels_on_n_or_empty(capsys):
    with pytest.raises(SystemExit) as exc:
        _confirm('n\n')
    assert exc.value.code == 1
    capsys.readouterr()
    with pytest.raises(SystemExit):
        _confirm('\n')
