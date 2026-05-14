import logging
import os
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    log_format: Optional[str] = None,
) -> None:
    """
    Настроить логирование в консоль и опционально в файл

    Args:
        level: Уровень логирования (logging.INFO, logging.DEBUG, etc.)
        log_file: Путь к файлу логов (опционально).
                  Может быть переопределён переменной окружения LOG_FILE
        log_format: Формат логов (опционально, используется default)

    Environment variables:
        LOG_FILE: Переопределяет log_file параметр если задана
    """
    # Переменная окружения LOG_FILE переопределяет параметр
    env_log_file = os.getenv("LOG_FILE")
    if env_log_file:
        log_file = env_log_file
    if log_format is None:
        log_format = "%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s"

    # Консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(log_format))

    # Файл (опционально)
    handlers = [console_handler]
    if log_file:
        # Создать директорию если нужно
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)

    # Настроить root logger
    logging.basicConfig(level=level, handlers=handlers, force=True)


def get_logger(name: str) -> logging.Logger:
    """Получить logger по имени"""
    return logging.getLogger(name)
