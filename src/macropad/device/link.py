"""Enlace com o dispositivo físico via porta serial (USB CDC).

``SerialLink`` roda uma thread própria que:
  1. localiza a porta do macropad (preferindo o VID da Espressif ou a
     porta fixada nas configurações);
  2. faz o handshake ``ping``/``hello``;
  3. lê mensagens continuamente e as repassa aos callbacks;
  4. reconecta automaticamente se o cabo for removido.

Os callbacks são invocados na thread do enlace — a camada de UI os
converte em sinais Qt (ver ``ui.bridge``).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any, Protocol

import serial
from serial.tools import list_ports

from . import protocol

log = logging.getLogger(__name__)


class DeviceLink(Protocol):
    """Interface comum ao enlace serial e ao simulador."""

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def send(self, message: dict[str, Any]) -> None: ...
    @property
    def connected(self) -> bool: ...


def available_ports() -> list[tuple[str, str]]:
    """Lista (porta, descrição) das portas seriais presentes."""
    return [(p.device, p.description or "") for p in list_ports.comports()]


class SerialLink:
    RECONNECT_DELAY_S = 2.0
    HANDSHAKE_TIMEOUT_S = 2.0
    # Ping periódico: mantém o firmware ciente de que o host está presente
    # (no modo híbrido, o firmware desativa o fallback BLE enquanto isso).
    HEARTBEAT_S = 3.0

    def __init__(
        self,
        on_message: Callable[[dict[str, Any]], None],
        on_state: Callable[[bool, str], None],
        preferred_port: str | None = None,
    ) -> None:
        self._on_message = on_message
        self._on_state = on_state
        self.preferred_port = preferred_port
        self._serial: serial.Serial | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._write_lock = threading.Lock()
        # Portas que responderam algo que não é o macropad. Guardá-las evita
        # insistir para sempre na mesma quando há outros dispositivos USB.
        self._rejected: set[str] = set()
        # Se a conexão atual já foi anunciada à interface como ativa.
        self._announced = False

    # ------------------------------------------------------------- ciclo

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="serial-link")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._close()
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

    @property
    def connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def send(self, message: dict[str, Any]) -> None:
        ser = self._serial
        if ser is None or not ser.is_open:
            return
        try:
            with self._write_lock:
                ser.write(protocol.encode(message))
        except (serial.SerialException, OSError):
            self._close()

    # ----------------------------------------------------------- interno

    def _run(self) -> None:
        while self._running:
            port = self._find_port()
            if port is None:
                time.sleep(self.RECONNECT_DELAY_S)
                continue
            self._announced = False
            try:
                self._connect_and_read(port)
            except (serial.SerialException, OSError):
                pass
            finally:
                self._close()
                # Só avisa a queda de uma conexão que chegou a ser anunciada;
                # uma porta que falhou no handshake nunca "conectou".
                if self._announced:
                    self._announced = False
                    self._on_state(False, port)
            time.sleep(self.RECONNECT_DELAY_S)

    def _candidates(self) -> list[str]:
        """Portas plausíveis, das mais prováveis para as menos."""
        ports = list_ports.comports()
        if self.preferred_port:
            return [p.device for p in ports if p.device == self.preferred_port]
        espressif = [p.device for p in ports if p.vid == protocol.ESPRESSIF_VID]
        outras = [
            p.device
            for p in ports
            if p.vid is not None and p.device not in espressif
        ]
        return espressif + outras

    def _find_port(self) -> str | None:
        """Escolhe a próxima porta a tentar, alternando entre as candidatas.

        Sem o rodízio, uma primeira porta que não fosse o macropad (outro
        conversor USB-serial, por exemplo) seria tentada indefinidamente e
        o dispositivo real nunca seria encontrado.
        """
        candidatos = self._candidates()
        if not candidatos:
            self._rejected.clear()
            return None
        pendentes = [c for c in candidatos if c not in self._rejected]
        if not pendentes:
            # Todas já falharam: recomeça a rodada (o macropad pode ter sido
            # ligado depois, ou o firmware ainda estava inicializando).
            self._rejected.clear()
            pendentes = candidatos
        return pendentes[0]

    def _connect_and_read(self, port: str) -> None:
        ser = serial.Serial(port, protocol.BAUD_RATE, timeout=0.5)
        self._serial = ser
        ok, buffer, pending = self._handshake(ser)
        if not ok:
            log.debug("%s não respondeu ao handshake", port)
            self._rejected.add(port)
            return
        self._rejected.discard(port)
        self._announced = True
        self._on_state(True, port)
        # O que chegou junto com a resposta do handshake (tipicamente o
        # ``hello`` logo após o ``pong``) é entregue, não descartado.
        for early in pending:
            self._on_message(early)
        last_ping = time.monotonic()
        while self._running and ser.is_open:
            now = time.monotonic()
            if now - last_ping >= self.HEARTBEAT_S:
                last_ping = now
                self.send(protocol.msg_ping())
            chunk = ser.read(256)
            if not chunk:
                continue
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                message = protocol.decode(line)
                if message is not None:
                    self._on_message(message)

    def _handshake(
        self, ser: serial.Serial
    ) -> tuple[bool, bytes, list[dict[str, Any]]]:
        """Confirma que a porta pertence ao macropad antes de anunciá-la.

        Devolve ``(reconhecido, resto do buffer, mensagens já decodificadas)``.
        O firmware responde ao ``ping`` com ``pong`` e, se acabou de nos
        ver, um ``hello`` na sequência — frequentemente no mesmo pacote.
        Descartar o resto do buffer perderia esse ``hello`` (e com ele a
        primeira atualização do display).
        """
        with self._write_lock:
            ser.write(protocol.encode(protocol.msg_ping()))
        deadline = time.monotonic() + self.HANDSHAKE_TIMEOUT_S
        buffer = b""
        pending: list[dict[str, Any]] = []
        recognized = False
        while time.monotonic() < deadline:
            chunk = ser.read(64)
            if not chunk:
                if recognized:
                    break
                continue
            buffer += chunk
            # Só linhas completas: decodificar fragmentos daria resultados
            # imprevisíveis a cada leitura parcial.
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                decoded = protocol.decode(line)
                if decoded is None:
                    continue
                if decoded.get("t") in ("pong", "hello"):
                    recognized = True
                # Eventos de tecla que chegam ANTES da resposta ao ping
                # ficaram represados no firmware enquanto ninguém lia a
                # porta (o cabo estava ligado, o aplicativo não): são
                # antigos e executá-los agora dispararia ações fantasmas.
                if recognized:
                    pending.append(decoded)
            if recognized and not buffer:
                # Resposta completa já em mãos: não há por que esperar o
                # resto do timeout.
                break
        return recognized, buffer, pending

    def _close(self) -> None:
        ser = self._serial
        self._serial = None
        if ser is not None:
            try:
                ser.close()
            except Exception:  # fechar é best-effort
                # O cabo já pode ter sido removido; o driver lança tipos
                # variados nesse caso e o enlace vai reconectar de todo jeito.
                log.debug("falha ao fechar a porta serial", exc_info=True)
