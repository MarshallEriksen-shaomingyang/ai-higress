import datetime
import logging
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TextIO
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


def _project_root() -> Path:
    # Keep log files under the backend project root, not the repository root.
    # Local path: backend/app/logging_config.py -> backend/app -> backend
    # Docker image path: /app/app/logging_config.py -> /app
    return Path(__file__).resolve().parents[1]


def _resolve_log_dir(value: str | Path) -> Path:
    p = value if isinstance(value, Path) else Path(value)
    if p.is_absolute():
        return p
    return _project_root() / p


def _resolve_tzinfo(timezone_name: str | None) -> datetime.tzinfo:
    # Keep behaviour aligned with LocalTimezoneFormatter.
    if timezone_name:
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            pass
    return datetime.datetime.now().astimezone().tzinfo or datetime.UTC


def infer_log_business(record: logging.LogRecord) -> str:
    """
    Best-effort mapping from a log record back to a "business bucket".

    We rely on record.pathname (callsite) because most modules import the shared
    `logger` instance (name always "apiproxy"), so record.name is not enough.
    """
    # Honor explicitly assigned biz (e.g. logger.info(..., extra={"biz": "chat_timing"})).
    existing_biz = getattr(record, "biz", None)
    if isinstance(existing_biz, str) and existing_biz.strip():
        return existing_biz.strip()

    name = record.name or ""
    if name.startswith("uvicorn.access"):
        return "access"
    if name.startswith(("uvicorn.error", "uvicorn")):
        return "server"

    path = (record.pathname or "").replace("\\", "/")
    # API routes
    if "/app/api/v1/chat_routes.py" in path:
        return "chat"
    if "/app/api/v1/" in path and "provider" in path:
        return "provider"
    if "/app/api/system_routes.py" in path:
        return "system"
    if "/app/api/metrics_routes.py" in path:
        return "metrics"

    # Domain modules / services
    if "/app/services/chat_routing_service.py" in path:
        return "chat"
    if "/app/provider/" in path or "/app/services/provider_" in path:
        return "provider"
    if "/app/services/credit_" in path:
        return "credits"
    if "/app/upstream.py" in path or "/app/services/upstream_proxy" in path:
        return "upstream"
    if "/app/proxy_pool.py" in path:
        return "upstream"
    if "/app/routing/" in path:
        return "routing"
    if "/app/tasks/" in path or "/app/celery_app.py" in path:
        return "tasks"
    if "/app/db/" in path:
        return "db"

    return "app"


class DailyFolderFileHandler(logging.Handler):
    """
    Writes logs to: <log_dir>/<YYYY-MM-DD>/<filename>
    and keeps at most backup_days date folders.
    """

    def __init__(
        self,
        log_dir: Path,
        filename: str,
        backup_days: int = 7,
        encoding: str = "utf-8",
        timezone_name: str | None = None,
        now_fn: Callable[[], datetime.datetime] | None = None,
    ) -> None:
        super().__init__()
        self.log_dir = log_dir
        self.filename = filename
        self.backup_days = backup_days
        self.encoding = encoding
        self.terminator = "\n"
        self._tzinfo = _resolve_tzinfo(timezone_name)
        # now_fn is mainly for tests.
        self._now_fn = now_fn
        self._current_date: datetime.date | None = None
        self._stream: TextIO | None = None
        self._ensure_stream()

    def _today(self) -> datetime.date:
        if self._now_fn is not None:
            now = self._now_fn()
        else:
            now = datetime.datetime.now(tz=self._tzinfo)
        if now.tzinfo is None:
            now = now.replace(tzinfo=self._tzinfo)
        return now.date()

    def _dir_for_date(self, day: datetime.date) -> Path:
        return self.log_dir / day.isoformat()

    def _file_path_for_date(self, day: datetime.date) -> Path:
        return self._dir_for_date(day) / self.filename

    def _cleanup_old_dirs(self) -> None:
        if self.backup_days <= 0:
            return
        try:
            dirs = [p for p in self.log_dir.iterdir() if p.is_dir()]
        except OSError:
            return

        dated: list[tuple[datetime.date, Path]] = []
        for p in dirs:
            try:
                day = datetime.date.fromisoformat(p.name)
            except ValueError:
                continue
            dated.append((day, p))

        dated.sort(key=lambda x: x[0])
        if len(dated) <= self.backup_days:
            return
        for _, old_dir in dated[: len(dated) - self.backup_days]:
            try:
                shutil.rmtree(old_dir)
            except OSError:
                pass

    def _ensure_stream(self) -> None:
        today = self._today()
        if self._current_date == today and self._stream:
            return

        self._current_date = today
        if self._stream:
            try:
                self._stream.close()
            except OSError:
                pass
            self._stream = None

        file_path = self._file_path_for_date(today)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = open(file_path, "a", encoding=self.encoding)
        self._cleanup_old_dirs()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._ensure_stream()
            if self._stream is None:
                return
            msg = self.format(record)
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


class DailyFolderBusinessFileHandler(logging.Handler):
    """
    Route logs into per-day folders and per-business files:
    <log_dir>/<YYYY-MM-DD>/<business>.log
    """

    def __init__(
        self,
        log_dir: Path,
        backup_days: int = 7,
        encoding: str = "utf-8",
        timezone_name: str | None = None,
        now_fn: Callable[[], datetime.datetime] | None = None,
    ) -> None:
        super().__init__()
        self.log_dir = log_dir
        self.backup_days = backup_days
        self.encoding = encoding
        self.terminator = "\n"
        self._tzinfo = _resolve_tzinfo(timezone_name)
        # now_fn is mainly for tests.
        self._now_fn = now_fn
        self._current_date: datetime.date | None = None
        self._streams: dict[str, TextIO] = {}
        self._ensure_date()

    def _today(self) -> datetime.date:
        if self._now_fn is not None:
            now = self._now_fn()
        else:
            now = datetime.datetime.now(tz=self._tzinfo)
        if now.tzinfo is None:
            now = now.replace(tzinfo=self._tzinfo)
        return now.date()

    def _cleanup_old_dirs(self) -> None:
        if self.backup_days <= 0:
            return
        try:
            dirs = [p for p in self.log_dir.iterdir() if p.is_dir()]
        except OSError:
            return

        dated: list[tuple[datetime.date, Path]] = []
        for p in dirs:
            try:
                day = datetime.date.fromisoformat(p.name)
            except ValueError:
                continue
            dated.append((day, p))

        dated.sort(key=lambda x: x[0])
        if len(dated) <= self.backup_days:
            return
        for _, old_dir in dated[: len(dated) - self.backup_days]:
            try:
                shutil.rmtree(old_dir)
            except OSError:
                pass

    def _close_all_streams(self) -> None:
        for stream in self._streams.values():
            try:
                stream.close()
            except OSError:
                pass
        self._streams.clear()

    def _ensure_date(self) -> None:
        today = self._today()
        if self._current_date == today:
            return
        self._current_date = today
        self._close_all_streams()
        (self.log_dir / today.isoformat()).mkdir(parents=True, exist_ok=True)
        self._cleanup_old_dirs()

    def _file_path(self, biz: str) -> Path:
        assert self._current_date is not None
        safe = "".join(c if (c.isalnum() or c in ("-", "_")) else "_" for c in biz)
        return self.log_dir / self._current_date.isoformat() / f"{safe}.log"

    def _stream_for_biz(self, biz: str):
        stream = self._streams.get(biz)
        if stream is not None:
            return stream
        file_path = self._file_path(biz)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        stream = open(file_path, "a", encoding=self.encoding)
        self._streams[biz] = stream
        return stream

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._ensure_date()
            biz = infer_log_business(record)
            # Expose biz for formatters.
            record.biz = biz
            stream = self._stream_for_biz(biz)
            msg = self.format(record)
            stream.write(msg + self.terminator)
            stream.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        try:
            self._close_all_streams()
        finally:
            super().close()


class EnsureBizFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "biz"):
            record.biz = infer_log_business(record)
        return True


class FixedBizFilter(logging.Filter):
    def __init__(self, biz: str) -> None:
        super().__init__()
        self._biz = biz

    def filter(self, record: logging.LogRecord) -> bool:
        record.biz = self._biz
        return True


def setup_logging() -> None:
    """
    Configure application logging.
    Writes logs to a daily rotating folder under LOG_DIR (default: ./logs/),
    with files split by business, e.g. logs/2025-12-12/chat.log.
    """
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    log_dir = _resolve_log_dir(getattr(settings, "log_dir", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    app_logger = logging.getLogger("apiproxy")
    access_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_error_logger = logging.getLogger("uvicorn.error")

    # Resolve log level from settings (LOG_LEVEL env var), defaulting to INFO.
    level_name = getattr(settings, "log_level", "INFO")
    if not isinstance(level_name, str):
        level_name = "INFO"
    level_value = getattr(logging, level_name.upper(), logging.INFO)

    formatter = LocalTimezoneFormatter(
        "%(asctime)s [%(levelname)s] [%(biz)s] %(name)s - %(message)s",
        timezone_name=getattr(settings, "log_timezone", None),
    )

    backup_days = getattr(settings, "log_backup_days", 7)
    try:
        backup_days = int(backup_days)
    except (TypeError, ValueError):
        backup_days = 7

    split_by_business = getattr(settings, "log_split_by_business", True)
    if not isinstance(split_by_business, bool):
        split_by_business = str(split_by_business).strip().lower() in ("1", "true", "yes")

    if split_by_business:
        file_handler: logging.Handler = DailyFolderBusinessFileHandler(
            log_dir=log_dir,
            backup_days=backup_days,
            encoding="utf-8",
            timezone_name=getattr(settings, "log_timezone", None),
        )
    else:
        # Backward-ish compatibility: keep a single app.log per day.
        file_handler = DailyFolderFileHandler(
            log_dir=log_dir,
            filename="app.log",
            backup_days=backup_days,
            encoding="utf-8",
            timezone_name=getattr(settings, "log_timezone", None),
        )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(EnsureBizFilter())
    # Only application logs (logger "apiproxy") go into the business log files.
    file_handler.addFilter(lambda record: record.name.startswith("apiproxy"))
    app_logger.setLevel(level_value)
    app_logger.propagate = True  # let logs also go to root/uvicorn handlers (console)
    app_logger.addHandler(file_handler)

    # Uvicorn logs: keep access/server logs separate for easier analysis.
    access_file_handler = DailyFolderFileHandler(
        log_dir=log_dir,
        filename="access.log",
        backup_days=backup_days,
        encoding="utf-8",
        timezone_name=getattr(settings, "log_timezone", None),
    )
    access_file_handler.setFormatter(formatter)
    access_file_handler.addFilter(FixedBizFilter("access"))
    access_logger.setLevel(level_value)
    access_logger.propagate = True
    access_logger.addHandler(access_file_handler)

    # Debug file for image upstream payloads，仅非生产环境启用，便于排查。
    if getattr(settings, "environment", "development").lower() != "production":
        image_debug_handler = DailyFolderFileHandler(
            log_dir=log_dir,
            filename="image-debug.log",
            backup_days=backup_days,
            encoding="utf-8",
            timezone_name=getattr(settings, "log_timezone", None),
        )
        image_debug_handler.setFormatter(formatter)
        image_debug_handler.addFilter(FixedBizFilter("image_debug"))
        image_debug_logger = logging.getLogger("apiproxy.image_debug")
        image_debug_logger.setLevel(logging.DEBUG)
        image_debug_logger.propagate = False
        image_debug_logger.addHandler(image_debug_handler)

    server_file_handler = DailyFolderFileHandler(
        log_dir=log_dir,
        filename="server.log",
        backup_days=backup_days,
        encoding="utf-8",
        timezone_name=getattr(settings, "log_timezone", None),
    )
    server_file_handler.setFormatter(formatter)
    server_file_handler.addFilter(FixedBizFilter("server"))
    # Avoid duplicating uvicorn.error records, and avoid mixing uvicorn.access into server.log.
    server_file_handler.addFilter(
        lambda record: not (record.name or "").startswith("uvicorn.access")
    )
    uvicorn_logger.setLevel(level_value)
    uvicorn_logger.propagate = True
    uvicorn_logger.addHandler(server_file_handler)
    uvicorn_error_logger.setLevel(level_value)
    uvicorn_error_logger.propagate = True

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
        console_handler.addFilter(EnsureBizFilter())
        root_logger.addHandler(console_handler)

    _LOGGING_CONFIGURED = True


logger = logging.getLogger("apiproxy")
