import datetime
import logging
from pathlib import Path

from app.logging_config import DailyFolderBusinessFileHandler, DailyFolderFileHandler


def _fixed_now() -> datetime.datetime:
    return datetime.datetime(2025, 1, 2, 3, 4, 5, tzinfo=datetime.UTC)


def _make_record(*, name: str, pathname: str, msg: str) -> logging.LogRecord:
    return logging.LogRecord(
        name=name,
        level=logging.INFO,
        pathname=pathname,
        lineno=123,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_daily_folder_business_handler_routes_by_pathname(tmp_path: Path) -> None:
    handler = DailyFolderBusinessFileHandler(
        log_dir=tmp_path,
        backup_days=7,
        timezone_name="UTC",
        now_fn=_fixed_now,
    )
    handler.setFormatter(logging.Formatter("[%(biz)s] %(message)s"))

    handler.emit(
        _make_record(
            name="apiproxy",
            pathname="backend/app/api/v1/chat_routes.py",
            msg="chat hello",
        )
    )
    handler.emit(
        _make_record(
            name="apiproxy",
            pathname="backend/app/provider/key_pool.py",
            msg="provider hello",
        )
    )

    day_dir = tmp_path / "2025-01-02"
    assert (day_dir / "chat.log").read_text(encoding="utf-8").splitlines()[-1] == (
        "[chat] chat hello"
    )
    assert (day_dir / "provider.log").read_text(encoding="utf-8").splitlines()[-1] == (
        "[provider] provider hello"
    )
    handler.close()


def test_daily_folder_business_handler_routes_speech_logs(tmp_path: Path) -> None:
    """Test that speech-related logs (TTS/STT) are routed to speech.log."""
    handler = DailyFolderBusinessFileHandler(
        log_dir=tmp_path,
        backup_days=7,
        timezone_name="UTC",
        now_fn=_fixed_now,
    )
    handler.setFormatter(logging.Formatter("[%(biz)s] %(message)s"))

    # TTS service log
    handler.emit(
        _make_record(
            name="apiproxy",
            pathname="backend/app/services/tts_app_service.py",
            msg="tts: upstream http error",
        )
    )
    # STT service log
    handler.emit(
        _make_record(
            name="apiproxy",
            pathname="backend/app/services/stt_app_service.py",
            msg="stt: candidate failed",
        )
    )
    # Audio routes log
    handler.emit(
        _make_record(
            name="apiproxy",
            pathname="backend/app/api/v1/audio_routes.py",
            msg="audio transcription request",
        )
    )
    # Audio storage service log
    handler.emit(
        _make_record(
            name="apiproxy",
            pathname="backend/app/services/audio_storage_service.py",
            msg="audio file stored",
        )
    )

    day_dir = tmp_path / "2025-01-02"
    speech_log = day_dir / "speech.log"
    assert speech_log.exists(), "speech.log should be created"
    lines = speech_log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    assert "[speech] tts: upstream http error" in lines[0]
    assert "[speech] stt: candidate failed" in lines[1]
    assert "[speech] audio transcription request" in lines[2]
    assert "[speech] audio file stored" in lines[3]
    handler.close()


def test_daily_folder_file_handler_writes_to_named_file(tmp_path: Path) -> None:
    handler = DailyFolderFileHandler(
        log_dir=tmp_path,
        filename="access.log",
        backup_days=7,
        timezone_name="UTC",
        now_fn=_fixed_now,
    )
    handler.setFormatter(logging.Formatter("%(message)s"))

    record = _make_record(
        name="uvicorn.access",
        pathname="/usr/local/lib/python3.12/site-packages/uvicorn/protocols/http/h11_impl.py",
        msg="GET / 200",
    )
    handler.emit(record)

    content = (tmp_path / "2025-01-02" / "access.log").read_text(encoding="utf-8")
    assert "GET / 200" in content
    handler.close()
