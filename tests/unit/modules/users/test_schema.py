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
