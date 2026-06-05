import logging
import os
import sys
from contextvars import ContextVar
from pathlib import Path

# Пакеты проекта, которые получают DEBUG при --pkg-debug.
_PROJECT_PACKAGES = ("src", "pipelines", "store", "common")

# Контекстная переменная для request_id — позволяет передавать ID через async стек без threading.
_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def setup_logging(
    level: int = logging.INFO,
    log_file: str | None = None,
    log_format: str | None = None,
    debug_packages: bool = False,
) -> None:
    """
    Настроить логирование в консоль и опционально в файл.

    Args:
        level: Уровень root logger (logging.INFO, logging.DEBUG, etc.)
        log_file: Путь к файлу логов (опционально).
                  Может быть переопределён переменной окружения LOG_FILE.
        log_format: Формат логов (опционально, используется default).
        debug_packages: Если True — root остаётся на level, но пакеты проекта
                        (_PROJECT_PACKAGES) переводятся на DEBUG.
                        Позволяет видеть отладочные сообщения своего кода
                        без шума от сторонних библиотек.

    Environment variables:
        LOG_FILE: Переопределяет log_file параметр если задана.
    """
    # Переменная окружения LOG_FILE переопределяет параметр
    env_log_file = os.getenv("LOG_FILE")
    if env_log_file:
        log_file = env_log_file
    if log_format is None:
        log_format = "%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s"

    # Принудительно переключаем stdout на UTF-8 — PyCharm/pydevd заменяет sys.stdout
    # своим wrapper'ом с cp1252, из-за чего кириллица в DEBUG-сообщениях вызывает
    # UnicodeEncodeError. reconfigure() меняет кодировку уже установленного wrapper'а.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    # Консоль
    console_handler: logging.Handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)  # handler пропускает всё; уровень фильтрует logger
    console_handler.setFormatter(logging.Formatter(log_format))

    # Файл (опционально)
    handlers: list[logging.Handler] = [console_handler]
    if log_file:
        # Создать директорию если нужно
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)

    # Настроить root logger
    logging.basicConfig(level=level, handlers=handlers, force=True)

    # Снизить уровень логирования для aiosqlite (избежать логирования полных SQL параметров с unicode)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)

    # Включить DEBUG для пакетов проекта, оставив root на INFO
    if debug_packages:
        for pkg in _PROJECT_PACKAGES:
            logging.getLogger(pkg).setLevel(logging.DEBUG)


def get_request_id() -> str:
    """Return the current request ID, or '-' outside an HTTP request context."""
    return _request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set the current request ID for logging (for use in middleware)."""
    _request_id_var.set(request_id)


def get_logger(name: str) -> logging.Logger:
    """Получить logger по имени"""
    return logging.getLogger(name)


# Запоминаем оригинальную фабрику LogRecord и подменяем её на расширенную.
_original_record_factory = logging.getLogRecordFactory()


def _log_record_factory(
    name: str,
    level: int,
    fn,
    lno,
    msg,
    args,
    exc_info,
    func=None,
    sinfo=None,
    **kwargs,
) -> logging.LogRecord:
    """Extended LogRecord factory that injects request_id from ContextVar into every log record."""
    record = _original_record_factory(name, level, fn, lno, msg, args, exc_info, func=func, sinfo=sinfo, **kwargs)
    record.request_id = _request_id_var.get()
    return record


logging.setLogRecordFactory(_log_record_factory)