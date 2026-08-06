"""Testes de regressão dos defeitos corrigidos na fase de robustez.

Cada teste aqui existe por causa de um defeito real observado, e não de
uma hipótese: o comentário no início de cada classe descreve o sintoma.
"""

import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from macropad.core.models import Action, Profile, Settings
from macropad.core.store import Store
from macropad.device.simulator import SimulatorLink


class DisplayReplayTest(unittest.TestCase):
    """A janela do simulador abria mostrando o texto de boot ("macropad")
    em vez do perfil ativo: o host responde ao ``hello`` com o frame do
    perfil, mas a janela só registra ``on_display`` depois — o frame se
    perdia. O enlace agora guarda o último frame e o reapresenta.
    """

    def setUp(self):
        self.mensagens = []
        self.link = SimulatorLink(
            on_message=self.mensagens.append,
            on_state=lambda conectado, porta: None,
        )

    def test_frame_enviado_antes_da_janela_e_reapresentado(self):
        self.link.send({"t": "text", "lines": ["Sistema"]})

        recebidos = []
        self.link.on_display = recebidos.append

        self.assertEqual(recebidos, [{"t": "text", "lines": ["Sistema"]}])

    def test_frame_seguinte_chega_normalmente(self):
        recebidos = []
        self.link.on_display = recebidos.append
        self.link.send({"t": "text", "lines": ["Edicao"]})

        self.assertEqual(recebidos, [{"t": "text", "lines": ["Edicao"]}])

    def test_apenas_o_ultimo_frame_e_guardado(self):
        self.link.send({"t": "text", "lines": ["Antigo"]})
        self.link.send({"t": "img", "data": "abc"})

        recebidos = []
        self.link.on_display = recebidos.append

        self.assertEqual(recebidos, [{"t": "img", "data": "abc"}])

    def test_mensagem_que_nao_e_display_nao_vira_frame(self):
        self.link.send({"t": "ping"})

        recebidos = []
        self.link.on_display = recebidos.append

        self.assertEqual(recebidos, [])

    def test_desconectar_a_janela_nao_dispara_callback(self):
        self.link.send({"t": "text", "lines": ["Sistema"]})
        self.link.on_display = None  # o que SimulatorWindow.closeEvent faz
        self.link.send({"t": "text", "lines": ["Outro"]})  # não deve lançar


class ConfiguracaoCorrompidaTest(unittest.TestCase):
    """Só o parse do JSON era protegido: um perfil sem ``name`` ou um
    ``obs_port`` não numérico levantavam exceção fora do ``try`` e o
    aplicativo não abria — o usuário perdia todos os perfis. Agora cada
    item inválido é descartado isoladamente.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.config = self.dir / "config.json"
        # As mensagens de descarte são esperadas; não poluem a saída.
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)
        self._tmp.cleanup()

    def _carregar(self, data) -> Store:
        self.config.write_text(json.dumps(data), encoding="utf-8")
        store = Store(data_dir=self.dir)
        store.load()
        return store

    def test_perfil_invalido_nao_derruba_os_validos(self):
        store = self._carregar(
            {
                "profiles": [
                    Profile(name="Bom").to_dict(),
                    {"id": "x"},  # sem "name"
                    Profile(name="Outro").to_dict(),
                ]
            }
        )
        self.assertEqual([p.name for p in store.profiles], ["Bom", "Outro"])

    def test_tecla_invalida_nao_derruba_o_perfil(self):
        perfil = Profile(name="VS Code")
        perfil.bindings[3] = Action(type="text", params={"text": "ok"})
        bruto = perfil.to_dict()
        bruto["bindings"]["nao_e_numero"] = {"type": "hotkey"}
        bruto["bindings"]["7"] = {"sem": "tipo"}

        store = self._carregar({"profiles": [bruto]})

        self.assertEqual([p.name for p in store.profiles], ["VS Code"])
        # A tecla válida sobrevive; as inválidas somem.
        self.assertEqual(store.profiles[0].bindings[3].params["text"], "ok")
        self.assertNotIn(7, store.profiles[0].bindings)

    def test_configuracoes_invalidas_caem_para_os_padroes(self):
        store = self._carregar(
            {
                "settings": {"obs_port": "nao_e_numero"},
                "profiles": [Profile(name="Bom").to_dict()],
            }
        )
        self.assertEqual(store.settings.obs_port, Settings().obs_port)
        # O perfil válido não é afetado pelo bloco de configurações ruim.
        self.assertEqual([p.name for p in store.profiles], ["Bom"])

    def test_raiz_que_nao_e_objeto_recomeca_do_padrao(self):
        store = self._carregar(["isto", "nao", "e", "um", "objeto"])
        self.assertGreaterEqual(len(store.profiles), 1)
        self.assertIsNotNone(store.active_profile)

    def test_blocos_com_tipo_errado_nao_lancam(self):
        store = self._carregar({"profiles": "deveria ser lista", "settings": 42})
        self.assertGreaterEqual(len(store.profiles), 1)
        self.assertIsNotNone(store.active_profile)

    def test_apps_vinculados_como_string_nao_viram_letras(self):
        bruto = Profile(name="X").to_dict()
        bruto["auto_apps"] = "code.exe"  # string, não lista

        store = self._carregar({"profiles": [bruto]})

        self.assertEqual(store.profiles[0].auto_apps, [])

    def test_perfil_ativo_invalido_cai_para_o_primeiro(self):
        store = self._carregar(
            {
                "active_profile_id": 12345,  # nem sequer é texto
                "profiles": [Profile(name="Bom").to_dict()],
            }
        )
        self.assertEqual(store.active_profile_id, store.profiles[0].id)

    def test_arquivo_original_preservado_quando_algo_e_descartado(self):
        self._carregar({"profiles": [{"id": "sem nome"}]})
        self.assertTrue((self.dir / "config.json.bak").exists())


class FalhaAoSalvarTest(unittest.TestCase):
    """``save()`` roda a cada toque na tecla de modo. Sem tratamento, um
    disco cheio ou uma permissão negada subiam pelo handler de sinal do
    Qt e derrubavam o aplicativo.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Store(data_dir=Path(self._tmp.name))
        self.store.load()
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)
        self._tmp.cleanup()

    def _quebrar_escrita(self):
        """Faz qualquer gravação falhar como um disco cheio faria."""
        patcher = mock.patch.object(
            Path, "write_text", side_effect=OSError(28, "No space left on device")
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_falha_ao_salvar_devolve_false_e_nao_lanca(self):
        self._quebrar_escrita()
        self.assertFalse(self.store.save())

    def test_falha_ao_salvar_e_reportada(self):
        avisos = []
        self.store.on_error = avisos.append
        self._quebrar_escrita()

        self.store.save()

        self.assertEqual(len(avisos), 1)
        self.assertIn("não foi possível salvar", avisos[0])

    def test_tecla_de_modo_continua_funcionando_sem_disco(self):
        self.store.add_profile("B")
        primeiro = self.store.profiles[0]
        self.store.active_profile_id = primeiro.id
        self._quebrar_escrita()

        # A troca de perfil acontece em memória mesmo sem conseguir gravar.
        seguinte = self.store.next_profile()

        self.assertNotEqual(seguinte.id, primeiro.id)
        self.assertEqual(self.store.active_profile_id, seguinte.id)

    def test_salvar_com_sucesso_devolve_true(self):
        self.assertTrue(self.store.save())


if __name__ == "__main__":
    unittest.main()
