import json
import logging
import sys
from typing import Mapping


class StructuredFormatter(logging.Formatter):
    """Serializa registros em JSON leve para facilitar correlação e observabilidade."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, str] = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        extra = getattr(record, "extra", None)
        if isinstance(extra, Mapping):
            payload.update({k: v for k, v in extra.items() if k not in payload})

        return json.dumps(payload, ensure_ascii=False)


def configure_structured_logging(level: int = logging.INFO) -> None:
    """Reconfigura o root logger para emitir eventos estruturados."""

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
