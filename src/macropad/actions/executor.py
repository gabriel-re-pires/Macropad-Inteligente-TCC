"""Execução assíncrona de ações.

O :class:`ActionRunner` mantém uma única thread de trabalho: as ações
disparadas pelas teclas são enfileiradas e executadas em ordem, sem
bloquear a interface nem a thread do enlace serial. Erros são
reportados por callback para exibição na UI (barra de status).
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable

from ..core.models import Action
from . import builtin  # noqa: F401 — registra os tipos embutidos
from .base import ActionContext, ActionError, get

log = logging.getLogger(__name__)


class ActionRunner:
    def __init__(
        self,
        context: ActionContext,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self._context = context
        self._on_error = on_error or (lambda msg: None)
        self._queue: queue.Queue[Action | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True, name="actions")
        self._thread.start()

    def submit(self, action: Action) -> None:
        self._queue.put(action)

    def stop(self) -> None:
        self._queue.put(None)
        self._thread.join(timeout=3.0)

    def _run(self) -> None:
        while True:
            action = self._queue.get()
            if action is None:
                return
            self._execute(action)

    def _execute(self, action: Action) -> None:
        action_type = get(action.type)
        if action_type is None:
            self._on_error(f"Tipo de ação desconhecido: {action.type!r}")
            return
        try:
            action_type.handler(action.params, self._context)
        except ActionError as exc:
            self._on_error(f"{action_type.title}: {exc}")
        except Exception:
            log.exception("erro inesperado ao executar %s", action.type)
            self._on_error(f"Erro inesperado ao executar {action_type.title!r}")
