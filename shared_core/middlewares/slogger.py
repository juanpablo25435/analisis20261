import logging
import sys
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from colorama import Fore, Style, init


class ColorFormatter(logging.Formatter):
    """Console formatter with colorized log levels."""

    COLORS = {
        logging.DEBUG: Fore.LIGHTBLACK_EX,
        logging.INFO: Fore.BLUE,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
        logging.FATAL: Fore.RED + Style.BRIGHT,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        init(autoreset=True)

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, "")
        original_levelname = record.levelname
        record.levelname = f"{color}{original_levelname}{Style.RESET_ALL}"
        formatted = super().format(record)
        record.levelname = original_levelname
        return formatted


class SafeLogger:
    """Robust logger that safely stringifies arbitrary payloads."""

    def __init__(self, name: str, base_log_path: str | Path = ".logs"):
        self._logger = self.__setup_logger(name, Path(base_log_path))

    def _safe_str(self, obj: Any) -> str:
        try:
            if isinstance(obj, (list, tuple, set, dict)):
                return str(obj)
            return str(obj).encode("utf-8", errors="replace").decode("utf-8")
        except Exception:
            return "[Objeto no representable]"

    def _safe_format(self, *args, **kwargs) -> str:
        args_str = " ".join(self._safe_str(arg) for arg in args)
        if kwargs:
            kwargs_str = " ".join(f"{key}={self._safe_str(value)}" for key, value in kwargs.items())
            return f"{args_str} {kwargs_str}"
        return args_str

    def __setup_logger(self, name: str, base_log_dir: Path) -> logging.Logger:
        base_log_dir.mkdir(exist_ok=True)
        current_time = datetime.now()
        date_dir = base_log_dir / current_time.strftime("%d_%m_%Y")
        date_dir.mkdir(exist_ok=True)
        hour_dir = date_dir / f"{current_time.strftime('%H')}hrs"
        hour_dir.mkdir(exist_ok=True)

        detailed_log_file = hour_dir / f"{name}.log"
        last_log_file = base_log_dir / f"last_{name}.log"

        logger = logging.getLogger(name)
        logger.setLevel(logging.ERROR)
        logger.propagate = False
        logger.handlers.clear()

        plain_formatter = logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s %(processName)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        colored_formatter = ColorFormatter(
            "%(levelname)s (%(asctime)s): %(message)s",
            datefmt="%H:%M:%S",
        )

        detailed_file_handler = logging.FileHandler(
            detailed_log_file,
            mode="w",
            encoding="utf-8",
        )
        detailed_file_handler.setLevel(logging.DEBUG)
        detailed_file_handler.setFormatter(plain_formatter)

        last_file_handler = logging.FileHandler(
            last_log_file,
            mode="w",
            encoding="utf-8",
        )
        last_file_handler.setLevel(logging.DEBUG)
        last_file_handler.setFormatter(plain_formatter)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(colored_formatter)

        logger.addHandler(detailed_file_handler)
        logger.addHandler(last_file_handler)
        logger.addHandler(console_handler)
        return logger

    def set_log(self, level: int, *args, **kwargs) -> None:
        self._logger.log(level, self._safe_format(*args, **kwargs))

    def debug(self, *args, **kwargs) -> None:
        self.set_log(logging.DEBUG, *args, **kwargs)

    def info(self, *args, **kwargs) -> None:
        self.set_log(logging.INFO, *args, **kwargs)

    def warn(self, *args, **kwargs) -> None:
        self.set_log(logging.WARNING, *args, **kwargs)

    def error(self, *args, **kwargs) -> None:
        self.set_log(logging.ERROR, *args, **kwargs)

    def critic(self, *args, **kwargs) -> None:
        self.set_log(logging.CRITICAL, *args, **kwargs)

    def fatal(self, *args, **kwargs) -> None:
        self.set_log(logging.FATAL, *args, **kwargs)


def get_logger(name: str) -> SafeLogger:
    return SafeLogger(name)


def log_execution(logger: SafeLogger):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                logger.debug(f"Iniciando {func.__name__}")
                result = func(*args, **kwargs)
                logger.debug(f"Completado {func.__name__}")
                return result
            except Exception as error:
                logger.error(f"Error en {func.__name__}: {error}")
                raise

        return wrapper

    return decorator
