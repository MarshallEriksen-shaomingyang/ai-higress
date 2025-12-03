import datetime
import logging
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .settings import settings

_LOGGING_CONFIGURED = False


class LocalTimezoneFormatter(logging.Formatter):
    """
    Logging formatter that forces timestamps into a configured timezone.
    Defaults to the system local timezone when LOG_TIMEZONE is not set
    or when the provided timezone is invalid.
    """

    def __init__(self, *args, timezone_name: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._tzinfo = self._resolve_tzinfo(timezone_name)

    @staticmethod
    def _resolve_tzinfo(timezone_name: str | None) -> datetime.tzinfo:
        if timezone_name:
            try:
                return ZoneInfo(timezone_name)
            except ZoneInfoNotFoundError:
                pass
        # Fallback to system local timezone
        return datetime.datetime.now().astimezone().tzinfo or datetime.UTC

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.datetime.fromtimestamp(record.created, tz=self._tzinfo)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat(timespec="milliseconds")


class DailyFileHandler(logging.Handler):
    """
    Simple daily file handler that writes each day's logs into
    logs/app-YYYY-MM-DD.log, keeping at most backup_count files.
    """

    def __init__(
        self,
        log_dir: Path,
        filename_prefix: str = "app",
        backup_count: int = 7,
        encoding: str = "utf-8",
    ) -> None:
        super().__init__()
        self.log_dir = log_dir
        self.filename_prefix = filename_prefix
        self.backup_count = backup_count
        self.encoding = encoding
        self.terminator = "\n"
        self._current_date: datetime.date | None = None
        self._stream = None
        self._ensure_stream()

    def _file_path_for_date(self, day: datetime.date) -> Path:
        return self.log_dir / f"{self.filename_prefix}-{day.isoformat()}.log"

    def _cleanup_old_files(self) -> None:
        if self.backup_count <= 0:
            return
        prefix = f"{self.filename_prefix}-"
        candidates = sorted(
            p
            for p in self.log_dir.iterdir()
            if p.is_file() and p.name.startswith(prefix) and p.suffix == ".log"
        )
        if len(candidates) <= self.backup_count:
            return
        for old in candidates[: len(candidates) - self.backup_count]:
            try:
                old.unlink()
            except OSError:
                # Best-effort cleanup; ignore failures.
                pass

    def _ensure_stream(self) -> None:
        today = datetime.date.today()
        if self._current_date == today and self._stream:
            return

        # Date changed or first use: rotate to a new file.
        self._current_date = today
        if self._stream:
            try:
                self._stream.close()
            except OSError:
                pass
            self._stream = None

        self.log_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._file_path_for_date(today)
        self._stream = open(file_path, "a", encoding=self.encoding)
        self._cleanup_old_files()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._ensure_stream()
            if self._stream is None:
                return
            self._stream.write(msg + self.terminator)
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        try:
            if self._stream:
                try:
                    self._stream.close()
                except OSError:
                    pass
                self._stream = None
        finally:
            super().close()


def setup_logging() -> None:
    """
    Configure application logging.
    Writes logs to a daily rotating file under ./logs/,
    with rotated files named logs/app-YYYY-MM-DD.log.
    """
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    app_logger = logging.getLogger("apiproxy")

    # Resolve log level from settings (LOG_LEVEL env var), defaulting to INFO.
    level_name = getattr(settings, "log_level", "INFO")
    if not isinstance(level_name, str):
        level_name = "INFO"
    level_value = getattr(logging, level_name.upper(), logging.INFO)

    formatter = LocalTimezoneFormatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        timezone_name=getattr(settings, "log_timezone", None),
    )

    # File handler: one log file per day, e.g. logs/app-YYYY-MM-DD.log
    file_handler = DailyFileHandler(
        log_dir=log_dir,
        filename_prefix="app",
        backup_count=7,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # Only application logs (logger "apiproxy") go into the daily log file.
    # Extra safety: filter by logger name in case handlers get attached higher up.
    file_handler.addFilter(lambda record: record.name.startswith("apiproxy"))
    app_logger.setLevel(level_value)
    app_logger.propagate = True  # let logs also go to root/uvicorn handlers (console)
    app_logger.addHandler(file_handler)

    # Console handler: attach to root so that uvicorn/watchfiles and apiproxy
    # logs are visible in the terminal, but not written to our file.
    root_logger.setLevel(level_value)
    has_console = False
    for h in root_logger.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(
            h, logging.FileHandler
        ):
            has_console = True
            break
    if not has_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    _LOGGING_CONFIGURED = True


logger = logging.getLogger("apiproxy")
