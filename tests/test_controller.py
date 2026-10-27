"""Testes do controlador (tecla -> ação, tecla de modo -> troca de perfil)."""

import base64
import tempfile
import unittest
from pathlib import Path

from macropad.core import display, icons
from macropad.core.controller import Controller
from macropad.core.models import Action
from macropad.core.store import Store

from .apoio import CofreFalso


class FakeRunner:
    def __init__(self):
        self.submitted = []

    def submit(self, action):
        self.submitted.append(action)


class ControllerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Store(data_dir=Path(self._tmp.name), vault=CofreFalso())
        self.store.load()
        self.store.settings.mode_key = 17

        profile_a = self.store.profiles[0]
        profile_a.name = "A"
        profile_a.bindings[0] = Action(type="text", params={"text": "olá"}, label="Oi")
        self.profile_b = self.store.add_profile("B")

        self.runner = FakeRunner()
        self.sent = []
        self.changed = []
        self.scheduled = []
        self.controller = Controller(
            store=self.store,
            runner=self.runner,
            send=self.sent.append,
            on_profile_changed=self.changed.append,
            schedule=lambda seconds, fn: self.scheduled.append((seconds, fn)),
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _press(self, key):
        self.controller.handle_message({"t": "key", "k": key, "e": "down"})

    def _last_frame(self):
        """Quadro 1 bpp da última mensagem ``img`` enviada ao dispositivo."""
        message = self.sent[-1]
        self.assertEqual(message["t"], "img")
        return icons.unpack_bits(base64.b64decode(message["d"]))

    def _expected(self, name, highlight=None):
        profile = next(p for p in self.store.profiles if p.name == name)
        return display.profile_frame(profile, 17, "mapa", highlight)

    def test_key_down_dispatches_bound_action(self):
        self._press(0)
        self.assertEqual(len(self.runner.submitted), 1)
        self.assertEqual(self.runner.submitted[0].params["text"], "olá")

    def test_key_up_and_unbound_keys_are_ignored(self):
        self.controller.handle_message({"t": "key", "k": 0, "e": "up"})
        self._press(3)  # sem ação
        self.assertEqual(self.runner.submitted, [])

    def test_mode_key_switches_profile_and_updates_display(self):
        self.assertEqual(self.store.active_profile.name, "A")
        self._press(17)
        self.assertEqual(self.store.active_profile.name, "B")
        self.assertEqual(self.changed[-1].name, "B")
        # O display recebe o mapa de teclas do novo perfil.
        self.assertEqual(self._last_frame().tobytes(), self._expected("B").tobytes())
        # A tecla de modo nunca dispara ações.
        self.assertEqual(self.runner.submitted, [])

    def test_hello_pushes_current_display(self):
        self.controller.handle_message({"t": "hello", "keys": 18})
        self.assertEqual(self._last_frame().tobytes(), self._expected("A").tobytes())

    def test_hello_forces_resend_even_if_unchanged(self):
        # O dispositivo pode ter reiniciado: após "hello" o quadro vai de novo.
        self.controller.handle_message({"t": "hello"})
        self.controller.handle_message({"t": "hello"})
        self.assertEqual(len(self.sent), 2)

    def test_identical_frame_is_not_resent(self):
        self.controller.push_display()
        self.controller.push_display()
        self.assertEqual(len(self.sent), 1)

    def test_activate_profile_from_ui(self):
        self.controller.activate_profile(self.profile_b.id)
        self.assertEqual(self.store.active_profile_id, self.profile_b.id)
        self.assertEqual(self._last_frame().tobytes(), self._expected("B").tobytes())

    def test_key_press_highlights_then_restores_display(self):
        self._press(0)
        self.assertEqual(
            self._last_frame().tobytes(), self._expected("A", highlight=0).tobytes()
        )
        # O retorno ao normal fica agendado e, ao disparar, reenvia o mapa.
        self.assertEqual(len(self.scheduled), 1)
        self.scheduled[0][1]()
        self.assertEqual(self._last_frame().tobytes(), self._expected("A").tobytes())

    def test_key_feedback_can_be_disabled(self):
        self.store.settings.key_feedback = False
        self._press(0)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.scheduled, [])

    def test_icon_mode_without_icon_shows_profile_name(self):
        self.store.settings.display_mode = "icone"
        self.controller.push_display()
        from macropad.core import oled_render

        expected = oled_render.render_text_lines(["A"])
        self.assertEqual(self._last_frame().tobytes(), expected.tobytes())


if __name__ == "__main__":
    unittest.main()
