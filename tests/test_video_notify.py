from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.heygen.delivery import notify_ready, send_whatsapp
from src.heygen.media_store import StoreError, save_mp4
from src.heygen.mobile import normalize_mobile
from src.heygen.prompt import build_video_prompt
from src.heygen.public_id import new_job_id


def api_client():
    from src.app import api

    return api


def test_new_job_id_is_twelve_hex():
    job_id = new_job_id()
    assert len(job_id) == 12
    assert int(job_id, 16) >= 0
    assert job_id != new_job_id()


def test_prompt_uses_session_figures():
    session = {
        "name": "Alex Tan",
        "age": 42,
        "occupation": "Engineer",
        "dependents": 2,
        "incomeMonthly": 9000,
        "expenseMonthly": 5500,
        "residency": "Singapore Citizen",
        "needs": [{"type": "N_RET", "enabled": True, "needAmount": 1_200_000, "existing": 100_000}],
    }
    text = build_video_prompt(session, 38, 61, "+6591234567")
    assert "Alex" in text
    assert "Singapore" in text
    assert "S$9,000" in text
    assert "S$5,500" in text
    assert "S$1,900" in text
    assert "S$950" in text
    assert "38" in text
    assert "61" in text
    assert "retirement" in text
    assert "not a quote" in text
    assert "Singapore" in text
    assert "red lipstick" in text
    assert "English" in text
    from src.heygen.prompt import build_spoken_script

    spoken = build_spoken_script(session, 38, 61)
    assert spoken.startswith("Hello Alex.")
    assert "S$9,000" in spoken
    assert "red lipstick" not in spoken


def test_prompt_spokesperson_follows_mobile_country():
    session = {"name": "Alex", "age": 40, "occupation": "Engineer", "dependents": 1, "incomeMonthly": 8000, "expenseMonthly": 4000}
    ch = build_video_prompt(session, 40, 50, "+41791234567")
    my = build_video_prompt(session, 40, 50, "+60123456789")
    uk = build_video_prompt(session, 40, 50, "+447911123456")
    assert "Switzerland" in ch
    assert "Malaysia" in my
    assert "United Kingdom" in uk
    assert "Singapore" not in ch
    us = build_video_prompt(session, 40, 50, "+12025550123")
    assert us.startswith(
        "The spokesperson should be: A professional woman from the United States in her 30s, having red lipstick, wearing professional attire, standing in a modern office."
    )


def test_normalize_mobile_assumes_singapore():
    assert normalize_mobile("9123 4567") == "+6591234567"
    assert normalize_mobile("+65 9123 4567") == "+6591234567"


def test_country_from_mobile():
    from src.heygen.mobile import country_from_mobile

    assert country_from_mobile("+6591234567") == "Singapore"
    assert country_from_mobile("+41791234567") == "Switzerland"
    assert country_from_mobile("+12025550123") == "the United States"


def test_video_notify_requires_contact(monkeypatch, tmp_path):
    monkeypatch.setenv("GP_VIDEO_JOBS", str(tmp_path / "jobs.sqlite"))
    with TestClient(api_client()) as client:
        r = client.post("/v1/video-notify", json={"session": {"name": "A"}})
        assert r.status_code == 400
        r = client.post("/v1/video-notify", json={"email": "a@b.co", "session": {"name": "A"}})
        assert r.status_code == 400


def test_video_notify_requires_heygen_key(monkeypatch, tmp_path):
    monkeypatch.setenv("GP_VIDEO_JOBS", str(tmp_path / "jobs.sqlite"))
    monkeypatch.delenv("HEYGEN_API_KEY", raising=False)
    with TestClient(api_client()) as client:
        r = client.post(
            "/v1/video-notify",
            json={"mobile": "91234567", "session": {"name": "A"}},
        )
    assert r.status_code == 503


def test_video_notify_queues_job(monkeypatch, tmp_path):
    monkeypatch.setenv("HEYGEN_API_KEY", "test-key")
    monkeypatch.setenv("GP_VIDEO_JOBS", str(tmp_path / "jobs.sqlite"))
    monkeypatch.delenv("MEDIA_DIR", raising=False)
    with (
        patch("src.heygen.pipeline.start_video_generation", return_value="vid-1"),
        patch("src.heygen.pipeline.persist_plan_report"),
        patch("src.heygen.pipeline.maybe_alert_low_balance"),
        patch("src.heygen.pipeline.threading.Thread") as thread,
        TestClient(api_client()) as client,
    ):
        thread.return_value = MagicMock()
        r = client.post(
            "/v1/video-notify",
            json={
                "email": "a@b.co",
                "mobile": "91234567",
                "pre": 40,
                "post": 55,
                "session": {"name": "Alex", "incomeMonthly": 8000},
            },
        )
    assert r.status_code == 202
    assert r.json()["success"] is True
    assert r.json()["jobId"]
    thread.assert_called()
    thread.return_value.start.assert_called()


def test_video_notify_overwrites_same_mobile(monkeypatch, tmp_path):
    monkeypatch.setenv("HEYGEN_API_KEY", "test-key")
    monkeypatch.setenv("GP_VIDEO_JOBS", str(tmp_path / "jobs.sqlite"))
    with (
        patch("src.heygen.pipeline.start_video_generation", return_value="vid-1"),
        patch("src.heygen.pipeline.persist_plan_report"),
        patch("src.heygen.pipeline.maybe_alert_low_balance"),
        patch("src.heygen.pipeline.threading.Thread") as thread,
        TestClient(api_client()) as client,
    ):
        thread.return_value = MagicMock()
        first = client.post(
            "/v1/video-notify",
            json={"mobile": "91234567", "session": {"name": "Alex"}},
        )
        second = client.post(
            "/v1/video-notify",
            json={"mobile": "+65 9123 4567", "email": "a@b.co", "session": {"name": "Alex"}},
        )
        other = client.post(
            "/v1/video-notify",
            json={"mobile": "92222222", "session": {"name": "Bea"}},
        )
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["jobId"] == second.json()["jobId"]
    assert other.json()["jobId"] != first.json()["jobId"]


def test_video_status_returns_job(monkeypatch, tmp_path):
    monkeypatch.setenv("GP_VIDEO_JOBS", str(tmp_path / "jobs.sqlite"))
    from src.heygen.jobs import insert_job, update_job

    insert_job("abc123abc123", email="a@b.co", mobile="+6591234567", first_name="Alex", prompt="hi")
    update_job("abc123abc123", status="completed", media_url="http://lx43:8042/videos/gp/abc123abc123.mp4")
    with TestClient(api_client()) as client:
        missing = client.get("/v1/video-notify/nope")
        r = client.get("/v1/video-notify/abc123abc123")
    assert missing.status_code == 404
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    assert "videos/gp/abc123abc123.mp4" in r.json()["mediaUrl"]


def test_video_notify_heygen_402_explains_credits(monkeypatch, tmp_path):
    monkeypatch.setenv("HEYGEN_API_KEY", "test-key")
    monkeypatch.setenv("GP_VIDEO_JOBS", str(tmp_path / "jobs.sqlite"))
    from src.heygen.agent import HEYGEN_NEEDS_CREDIT, GenerateError

    with (
        patch("src.heygen.pipeline.start_video_generation", side_effect=GenerateError(HEYGEN_NEEDS_CREDIT, status=402, endpoint="https://api.heygen.com/v3/videos")),
        patch("src.heygen.pipeline.persist_plan_report"),
        patch("src.heygen.pipeline.maybe_alert_low_balance"),
        patch("src.heygen.ops_alert.send_email", return_value={"ok": True}) as em,
        TestClient(api_client()) as client,
    ):
        r = client.post(
            "/v1/video-notify",
            json={"mobile": "91234567", "session": {"name": "Alex"}},
        )
    assert r.status_code == 503
    assert "credits" in r.json()["detail"].lower()
    em.assert_called_once()
    assert em.call_args.args[0] == "michael.gerber@vitalus.ch"
    assert "402" in em.call_args.args[1] or "402" in em.call_args.args[2]


def test_start_video_generation_posts_avatar_iii(monkeypatch):
    monkeypatch.setenv("HEYGEN_API_KEY", "test-key")
    monkeypatch.setenv("HEYGEN_AVATAR_ID", "Juan_standing_office_front")
    from src.heygen.agent import start_video_generation

    captured: dict = {}

    class FakeResp:
        status_code = 200
        text = '{"data":{"video_id":"v1"}}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"video_id": "v1"}}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return FakeResp()

    with patch("src.heygen.agent.requests.post", side_effect=fake_post):
        vid = start_video_generation("Hello Alex.")
    assert vid == "v1"
    assert captured["url"].endswith("/v3/videos")
    assert captured["json"]["type"] == "avatar"
    assert captured["json"]["engine"] == {"type": "avatar_iii"}
    assert captured["json"]["avatar_id"] == "Juan_standing_office_front"
    assert captured["json"]["script"] == "Hello Alex."
    assert captured["json"]["voice_id"]


def test_start_video_generation_402_raises_credits(monkeypatch):
    monkeypatch.setenv("HEYGEN_API_KEY", "test-key")
    from src.heygen.agent import GenerateError, start_video_generation

    class FakeResp:
        status_code = 402
        text = '{"error":"payment required"}'

        def raise_for_status(self):
            raise AssertionError("402 should not raise_for_status")

    with patch("src.heygen.agent.requests.post", return_value=FakeResp()):
        with pytest.raises(GenerateError, match="credits"):
            start_video_generation("hi")


def test_wait_for_url_polls_until_completed():
    with (
        patch("src.heygen.agent.time.sleep"),
        patch(
            "src.heygen.agent.poll_video_status",
            side_effect=[("processing", None), ("completed", "https://cdn.example/v.mp4")],
        ),
    ):
        from src.heygen.agent import wait_for_url

        status, url = wait_for_url("vid-1")
    assert status == "completed"
    assert url == "https://cdn.example/v.mp4"


def test_notify_ready_sends_email_and_whatsapp():
    with (
        patch("src.heygen.delivery.send_email", return_value={"ok": True}) as em,
        patch("src.heygen.delivery.send_whatsapp", return_value={"ok": True}) as wa,
    ):
        out = notify_ready("a@b.co", "+6590000000", "http://lx43:8042/videos/gp/x.mp4", "job1", "Alex")
    assert out["email"]["ok"]
    assert out["whatsapp"]["ok"]
    assert "videos/gp/x.mp4" in em.call_args.args[2]
    assert "videos/gp/x.mp4" in wa.call_args.args[1]
    assert "Video id: job1" in em.call_args.args[2]
    assert "Video id: job1" in wa.call_args.args[1]
    assert "not advice to buy" in em.call_args.args[2]


def test_send_whatsapp_posts_text_link(monkeypatch):
    monkeypatch.setenv("WHATSAPP_GATEWAY_URL", "http://wa.test:8091")

    class FakeResp:
        def read(self):
            return b'{"ok":true}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("src.heygen.delivery.urllib.request.urlopen", return_value=FakeResp()) as opener:
        result = send_whatsapp("+6590000000", "watch http://lx43:8042/videos/gp/id.mp4", "job1")
    assert result["ok"] is True
    req = opener.call_args[0][0]
    assert req.full_url == "http://wa.test:8091/send"
    assert b"videos/gp/id.mp4" in req.data
    assert b"job1" in req.data


def test_finish_job_stores_and_notifies(monkeypatch, tmp_path):
    monkeypatch.setenv("GP_VIDEO_JOBS", str(tmp_path / "jobs.sqlite"))
    from src.heygen.jobs import get_job, insert_job, update_job
    from src.heygen.pipeline import _finish_job

    insert_job("abc123", email="a@b.co", mobile="+6591111111", first_name="Alex", prompt="hi")
    update_job("abc123", heygen_id="vid-1")
    public = "http://lx43:8042/videos/gp/abc123.mp4"
    with (
        patch("src.heygen.pipeline.wait_for_url", return_value=("completed", "https://heygen.example/v.mp4")),
        patch("src.heygen.pipeline.save_mp4", return_value=public),
        patch("src.heygen.pipeline.persist_plan_report"),
        patch(
            "src.heygen.pipeline.notify_ready",
            return_value={"email": {"ok": True}, "whatsapp": {"ok": True}},
        ) as notify,
    ):
        _finish_job("abc123")
    job = get_job("abc123")
    assert job["status"] == "completed"
    assert job["media_url"] == public
    notify.assert_called_once()
    assert public in notify.call_args.args


def test_save_mp4_writes_under_media_dir(monkeypatch, tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setenv("MEDIA_DIR", str(media))
    monkeypatch.setenv("MEDIA_PUBLIC_BASE_URL", "http://lx43:8042/videos")

    class FakeResp:
        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size=1):  # noqa: ARG002
            yield b"x" * 2000

    with patch("src.heygen.media_store.requests.get", return_value=FakeResp()):
        url = save_mp4("https://heygen.example/v.mp4", "abc123")
    dest = media / "gp" / "abc123.mp4"
    assert dest.is_file()
    assert dest.stat().st_size >= 2000
    assert url == "http://lx43:8042/videos/gp/abc123.mp4"


def test_save_mp4_errors_when_download_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "nope"))
    monkeypatch.setenv("MEDIA_PUBLIC_BASE_URL", "http://lx43:8042/videos")
    with patch("src.heygen.media_store.requests.get", side_effect=OSError("nope")):
        with pytest.raises(StoreError):
            save_mp4("https://heygen.example/v.mp4", "abc")


def test_low_balance_alert_emails_once(monkeypatch, tmp_path):
    monkeypatch.setenv("GP_VIDEO_JOBS", str(tmp_path / "jobs.sqlite"))
    monkeypatch.setenv("HEYGEN_ALERT_EMAIL", "michael.gerber@vitalus.ch")
    from src.heygen.ops_alert import maybe_alert_low_balance

    with (
        patch("src.heygen.ops_alert.wallet_remaining_usd", return_value=0.37),
        patch("src.heygen.ops_alert.send_email", return_value={"ok": True}) as em,
    ):
        maybe_alert_low_balance()
        maybe_alert_low_balance()
    assert em.call_count == 1
    assert em.call_args.args[0] == "michael.gerber@vitalus.ch"
    assert "10" in em.call_args.args[1]
    assert "0.37" in em.call_args.args[2]
