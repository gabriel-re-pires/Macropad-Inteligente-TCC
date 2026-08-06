"""Testes do controlador (tecla -> ação, tecla de modo -> troca de perfil)."""

import tempfile
import unittest
from pathlib import Path

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
        self.controller = Controller(
            store=self.store,
            runner=self.runner,
            send=self.sent.append,
            on_profile_changed=self.changed.append,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _press(self, key):
        self.controller.handle_message({"t": "key", "k": key, "e": "down"})

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
        # Sem ícone: o display recebe o nome do perfil.
        self.assertEqual(self.sent[-1]["t"], "text")
        self.assertEqual(self.sent[-1]["lines"], ["B"])
        # A tecla de modo nunca dispara ações.
        self.assertEqual(self.runner.submitted, [])

    def test_hello_pushes_current_display(self):
        self.controller.handle_message({"t": "hello", "keys": 18})
        self.assertEqual(self.sent[-1]["t"], "text")
        self.assertEqual(self.sent[-1]["lines"], ["A"])

    def test_activate_profile_from_ui(self):
        self.controller.activate_profile(self.profile_b.id)
        self.assertEqual(self.store.active_profile_id, self.profile_b.id)
        self.assertEqual(self.sent[-1]["lines"], ["B"])


if __name__ == "__main__":
    unittest.main()
