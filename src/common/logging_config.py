import logging
import os
import sys
from pathlib import Path

# Пакеты проекта, которые получают DEBUG при --pkg-debug.
_PROJECT_PACKAGES = ("src", "pipelines", "store", "common")


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


def get_logger(name: str) -> logging.Logger:
    """Получить logger по имени"""
    return logging.getLogger(name)
