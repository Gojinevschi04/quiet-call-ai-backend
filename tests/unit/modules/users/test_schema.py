import pytest

from app.modules.users.schema import ProfileUpdate


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://127.0.0.1:8000/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "file:///etc/passwd",
        "ftp://example.com/",
        "http://localhost/",
        "http://metadata.google.internal/",
        "https://" + "x" * 3000,
    ],
)
def test_profile_update_rejects_ssrf_webhook_url(bad_url: str) -> None:
    with pytest.raises(ValueError):
        ProfileUpdate(webhook_url=bad_url)


@pytest.mark.parametrize(
    "good_url",
    [
        "https://example.com/hook",
        "https://webhooks.site/abc",
    ],
)
def test_profile_update_accepts_safe_webhook_url(good_url: str) -> None:
    profile = ProfileUpdate(webhook_url=good_url)
    assert profile.webhook_url == good_url


def test_profile_update_accepts_none_webhook_url() -> None:
    profile = ProfileUpdate(webhook_url=None)
    assert profile.webhook_url is None


def test_profile_update_accepts_empty_webhook_url() -> None:
    profile = ProfileUpdate(webhook_url="")
    assert profile.webhook_url == ""


import pytest


@pytest.mark.parametrize("good_name", ["Ana", "Maria-Elena", "Dr. Smith", "O'Brien", "Ана", "Maria Popescu"])
def test_profile_update_accepts_valid_assistant_name(good_name: str) -> None:
    update = ProfileUpdate(assistant_name=good_name)
    assert update.assistant_name == good_name


@pytest.mark.parametrize("bad_name", [
    "x" * 41,           # too long
    "<script>",          # angle brackets
    "@everyone",         # special chars
    "\n\ntrick",         # newline injection
])
def test_profile_update_rejects_bad_assistant_name(bad_name: str) -> None:
    with pytest.raises(Exception):
        ProfileUpdate(assistant_name=bad_name)


def test_profile_update_empty_string_normalizes_to_none() -> None:
    update = ProfileUpdate(assistant_name="")
    assert update.assistant_name is None


def test_profile_update_whitespace_only_rejected() -> None:
    with pytest.raises(Exception, match="cannot be empty"):
        ProfileUpdate(assistant_name="   ")


def test_profile_update_trims_whitespace() -> None:
    update = ProfileUpdate(assistant_name="  Ana  ")
    assert update.assistant_name == "Ana"
