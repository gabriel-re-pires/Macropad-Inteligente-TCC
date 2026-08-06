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

import threading
import time
from typing import Any, Callable, Protocol

import serial
from serial.tools import list_ports

from . import protocol


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
            try:
                self._connect_and_read(port)
            except (serial.SerialException, OSError):
                pass
            finally:
                was_connected = self._serial is not None
                self._close()
                if was_connected:
                    self._on_state(False, port)
            time.sleep(self.RECONNECT_DELAY_S)

    def _find_port(self) -> str | None:
        ports = list_ports.comports()
        if self.preferred_port:
            for p in ports:
                if p.device == self.preferred_port:
                    return p.device
            return None
        espressif = [p.device for p in ports if p.vid == protocol.ESPRESSIF_VID]
        if espressif:
            return espressif[0]
        usb = [p.device for p in ports if p.vid is not None]
        return usb[0] if usb else None

    def _connect_and_read(self, port: str) -> None:
        ser = serial.Serial(port, protocol.BAUD_RATE, timeout=0.5)
        self._serial = ser
        if not self._handshake(ser):
            return
        self._on_state(True, port)
        buffer = b""
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

    def _handshake(self, ser: serial.Serial) -> bool:
        """Confirma que a porta pertence ao macropad antes de anunciá-la."""
        with self._write_lock:
            ser.write(protocol.encode(protocol.msg_ping()))
        deadline = time.monotonic() + self.HANDSHAKE_TIMEOUT_S
        buffer = b""
        while time.monotonic() < deadline:
            buffer += ser.read(64)
            for line in buffer.split(b"\n"):
                message = protocol.decode(line)
                if message and message.get("t") in ("pong", "hello", "key"):
                    return True
        return False

    def _close(self) -> None:
        ser = self._serial
        self._serial = None
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
