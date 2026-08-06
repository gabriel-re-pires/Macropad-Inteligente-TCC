"""Testes de regressão dos defeitos corrigidos na fase de robustez.

Cada teste aqui existe por causa de um defeito real observado, e não de
uma hipótese: o comentário no início de cada classe descreve o sintoma.
"""

import json
import logging
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from macropad.actions import base
from macropad.actions.base import ActionContext
from macropad.actions.executor import ActionRunner
from macropad.core import autostart, profile_io
from macropad.core.models import Action, Profile, Settings
from macropad.core.store import Store
from macropad.device import protocol
from macropad.device.link import SerialLink
from macropad.device.simulator import SimulatorLink

from .apoio import CofreFalso


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
        store = Store(data_dir=self.dir, vault=CofreFalso())
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
        self.store = Store(data_dir=Path(self._tmp.name), vault=CofreFalso())
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


class SegredosNoCofreTest(unittest.TestCase):
    """O token do Home Assistant e a senha do OBS ficavam legíveis no
    config.json. Passam a viver no cofre do sistema, com migração do que
    já existia e retorno ao arquivo se não houver cofre disponível.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.config = self.dir / "config.json"
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)
        self._tmp.cleanup()

    def _json_salvo(self) -> dict:
        return json.loads(self.config.read_text(encoding="utf-8"))

    def test_segredos_saem_do_arquivo_e_vao_para_o_cofre(self):
        cofre = CofreFalso()
        store = Store(data_dir=self.dir, vault=cofre)
        store.load()
        store.settings.ha_token = "token-secreto"
        store.settings.obs_password = "senha-secreta"
        store.save()

        salvo = self._json_salvo()["settings"]
        self.assertEqual(salvo["ha_token"], "")
        self.assertEqual(salvo["obs_password"], "")
        self.assertEqual(cofre.guardados["ha_token"], "token-secreto")
        self.assertEqual(cofre.guardados["obs_password"], "senha-secreta")

    def test_segredos_voltam_do_cofre_ao_recarregar(self):
        cofre = CofreFalso()
        store = Store(data_dir=self.dir, vault=cofre)
        store.load()
        store.settings.ha_token = "token-secreto"
        store.save()

        recarregado = Store(data_dir=self.dir, vault=cofre)
        recarregado.load()
        self.assertEqual(recarregado.settings.ha_token, "token-secreto")

    def test_config_antiga_em_texto_claro_e_migrada(self):
        # Instalação anterior à mudança: o token está no arquivo.
        self.config.write_text(
            json.dumps({"settings": {"ha_token": "token-antigo"}}), encoding="utf-8"
        )
        cofre = CofreFalso()
        store = Store(data_dir=self.dir, vault=cofre)
        store.load()

        self.assertEqual(store.settings.ha_token, "token-antigo")
        store.save()

        self.assertEqual(cofre.guardados["ha_token"], "token-antigo")
        self.assertEqual(self._json_salvo()["settings"]["ha_token"], "")

    def test_sem_cofre_disponivel_o_segredo_fica_no_arquivo(self):
        # Sem backend, perder a configuração seria pior que mantê-la legível.
        cofre = CofreFalso(disponivel=False)
        store = Store(data_dir=self.dir, vault=cofre)
        store.load()
        store.settings.ha_token = "token-secreto"
        store.save()

        self.assertEqual(self._json_salvo()["settings"]["ha_token"], "token-secreto")

    def test_apagar_o_segredo_remove_do_cofre(self):
        cofre = CofreFalso()
        store = Store(data_dir=self.dir, vault=cofre)
        store.load()
        store.settings.ha_token = "token-secreto"
        store.save()

        store.settings.ha_token = ""
        store.save()

        self.assertNotIn("ha_token", cofre.guardados)


class ComandoDeInicializacaoTest(unittest.TestCase):
    """O comando gravado na chave Run usava sempre ``-m macropad``, que não
    existe no executável empacotado: a inicialização automática falharia
    silenciosamente justamente na instalação distribuída.
    """

    def test_no_executavel_empacotado_usa_o_proprio_exe(self):
        with mock.patch.object(sys, "frozen", True, create=True), mock.patch.object(
            sys, "executable", r"C:\Apps\MacropadConfigurator.exe"
        ):
            comando = autostart._command()

        self.assertEqual(comando, r'"C:\Apps\MacropadConfigurator.exe" --minimized')
        self.assertNotIn("-m macropad", comando)

    def test_a_partir_do_codigo_usa_o_python_com_o_modulo(self):
        # Sem sys.frozen: execução normal a partir do ambiente virtual.
        self.assertFalse(getattr(sys, "frozen", False))
        comando = autostart._command()

        self.assertIn("-m macropad", comando)
        self.assertTrue(comando.endswith("--minimized"))

    def test_sempre_inicia_direto_na_bandeja(self):
        self.assertIn("--minimized", autostart._command())


class TrocaDePerfisTest(unittest.TestCase):
    """Exportar e importar perfis entre máquinas. O ícone precisa viajar
    embutido (o caminho de origem não existe no destino) e o id precisa
    ser novo, para que importar duas vezes não sobrescreva nada.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.store = Store(data_dir=self.dir, vault=CofreFalso())
        self.store.load()
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)
        self._tmp.cleanup()

    def _perfil_completo(self) -> Profile:
        perfil = Profile(name="Edição de vídeo")
        perfil.bindings[0] = Action(
            type="hotkey", params={"keys": ["ctrl", "s"]}, label="Salvar"
        )
        perfil.bindings[5] = Action(
            type="command", params={"command": "git pull"}, label="Atualizar"
        )
        perfil.auto_apps = ["premiere.exe"]
        return perfil

    def test_ciclo_completo_preserva_o_conteudo(self):
        original = self._perfil_completo()
        importado = profile_io.from_json(profile_io.to_json(original))

        copia = importado.profile
        self.assertEqual(copia.name, original.name)
        self.assertEqual(copia.bindings[0].params["keys"], ["ctrl", "s"])
        self.assertEqual(copia.bindings[5].params["command"], "git pull")
        self.assertEqual(copia.auto_apps, ["premiere.exe"])

    def test_perfil_importado_recebe_id_novo(self):
        original = self._perfil_completo()
        texto = profile_io.to_json(original)

        primeiro = profile_io.from_json(texto).profile
        segundo = profile_io.from_json(texto).profile

        self.assertNotEqual(primeiro.id, original.id)
        self.assertNotEqual(primeiro.id, segundo.id)

    def test_icone_viaja_embutido_no_arquivo(self):
        icone = self.dir / "icone.png"
        icone.write_bytes(b"\x89PNG\r\n\x1a\n conteudo de teste")
        perfil = Profile(name="Com ícone", icon_path=str(icone))

        importado = profile_io.from_json(profile_io.to_json(perfil, str(icone)))

        self.assertEqual(importado.icon_bytes, icone.read_bytes())
        self.assertEqual(importado.icon_suffix, ".png")

    def test_icone_e_gravado_na_pasta_de_dados_ao_importar(self):
        icone = self.dir / "icone.png"
        icone.write_bytes(b"\x89PNG\r\n\x1a\n conteudo de teste")
        perfil = Profile(name="Com ícone", icon_path=str(icone))
        importado = profile_io.from_json(profile_io.to_json(perfil, str(icone)))

        novo = self.store.add_imported_profile(importado)

        self.assertIsNotNone(novo.icon_path)
        self.assertTrue(Path(novo.icon_path).exists())
        self.assertEqual(Path(novo.icon_path).read_bytes(), icone.read_bytes())

    def test_icone_ausente_nao_impede_a_exportacao(self):
        perfil = Profile(name="X", icon_path=str(self.dir / "nao_existe.png"))
        importado = profile_io.from_json(
            profile_io.to_json(perfil, perfil.icon_path)
        )
        self.assertIsNone(importado.icon_bytes)
        self.assertEqual(importado.profile.name, "X")

    def test_acoes_que_executam_comandos_sao_sinalizadas(self):
        importado = profile_io.from_json(profile_io.to_json(self._perfil_completo()))
        self.assertEqual(importado.sensitive, [(5, "git pull")])

    def test_perfil_inofensivo_nao_gera_alerta(self):
        perfil = Profile(name="Só atalhos")
        perfil.bindings[0] = Action(type="hotkey", params={"keys": ["ctrl", "c"]})
        importado = profile_io.from_json(profile_io.to_json(perfil))
        self.assertEqual(importado.sensitive, [])

    def test_arquivo_de_outro_tipo_e_recusado(self):
        for conteudo in ('{"format": "outra-coisa"}', "{}", "[]", "nao e json"):
            with self.assertRaises(profile_io.ProfileFileError):
                profile_io.from_json(conteudo)

    def test_versao_futura_e_recusada(self):
        documento = json.dumps(
            {"format": profile_io.FORMAT, "version": 99, "profile": {"name": "X"}}
        )
        with self.assertRaises(profile_io.ProfileFileError):
            profile_io.from_json(documento)

    def test_perfil_sem_nome_e_recusado(self):
        documento = json.dumps(
            {"format": profile_io.FORMAT, "version": 1, "profile": {"sem": "nome"}}
        )
        with self.assertRaises(profile_io.ProfileFileError):
            profile_io.from_json(documento)

    def test_icone_corrompido_nao_invalida_o_perfil(self):
        documento = json.dumps(
            {
                "format": profile_io.FORMAT,
                "version": 1,
                "profile": {"name": "X"},
                "icon": {"suffix": ".png", "data": "isto nao e base64!!"},
            }
        )
        importado = profile_io.from_json(documento)
        self.assertEqual(importado.profile.name, "X")
        self.assertIsNone(importado.icon_bytes)

    def test_exportar_e_importar_por_arquivo(self):
        destino = self.dir / "perfil.json"
        self.store.export_profile(self._perfil_completo(), destino)

        importado = profile_io.from_json(destino.read_text(encoding="utf-8"))
        antes = len(self.store.profiles)
        self.store.add_imported_profile(importado)

        recarregado = Store(data_dir=self.dir, vault=CofreFalso())
        recarregado.load()
        self.assertEqual(len(recarregado.profiles), antes + 1)
        self.assertIn("Edição de vídeo", [p.name for p in recarregado.profiles])


class FilaDeAcoesTest(unittest.TestCase):
    """A fila era única e bloqueante: um webhook parado no timeout de 5 s
    atrasava todas as teclas seguintes. Também era ilimitada (teclas
    marteladas viravam um lote que disparava tudo depois) e o encerramento
    esperava executar o que estivesse pendente.
    """

    def setUp(self):
        # Os tipos de ação de teste não podem vazar para os outros testes.
        self._registry = dict(base._registry)
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        base._registry.clear()
        base._registry.update(self._registry)
        logging.disable(logging.NOTSET)

    def _registrar_bloqueante(self, liberar: threading.Event) -> threading.Event:
        """Registra uma ação de rede que trava até ``liberar`` ser acionado."""
        comecou = threading.Event()

        @base.register("t_rede", "Rede lenta", "", remote=True)
        def _rede(params, ctx):
            comecou.set()
            liberar.wait(timeout=5)

        return comecou

    def test_acao_de_rede_nao_atrasa_as_teclas(self):
        liberar = threading.Event()
        comecou = self._registrar_bloqueante(liberar)

        prontas = threading.Event()
        executadas = []

        @base.register("t_local", "Atalho", "")
        def _local(params, ctx):
            executadas.append(params["n"])
            if len(executadas) == 3:
                prontas.set()

        runner = ActionRunner(context=ActionContext())
        # As limpezas rodam na ordem inversa do registro: liberar a ação
        # travada precisa acontecer antes do stop(), senão o join espera.
        self.addCleanup(runner.stop)
        self.addCleanup(liberar.set)

        runner.submit(Action(type="t_rede"))
        self.assertTrue(comecou.wait(timeout=3), "a via de rede não iniciou")
        for n in range(3):
            runner.submit(Action(type="t_local", params={"n": n}))

        self.assertTrue(prontas.wait(timeout=3), "as teclas ficaram presas")
        self.assertEqual(executadas, [0, 1, 2])
        # E a ação de rede continua travada — as teclas passaram na frente.
        self.assertFalse(liberar.is_set())

    def test_fila_cheia_descarta_com_aviso(self):
        liberar = threading.Event()
        comecou = self._registrar_bloqueante(liberar)

        avisos = []
        runner = ActionRunner(context=ActionContext(), on_error=avisos.append)
        self.addCleanup(runner.stop)
        self.addCleanup(liberar.set)

        runner.submit(Action(type="t_rede"))
        self.assertTrue(comecou.wait(timeout=3))
        # A via está ocupada e a fila, vazia: o excedente é exato.
        for _ in range(ActionRunner.QUEUE_MAX + 3):
            runner.submit(Action(type="t_rede"))

        self.assertEqual(len(avisos), 3)
        self.assertIn("descartada", avisos[0])

    def test_encerrar_nao_executa_o_que_ficou_na_fila(self):
        liberar = threading.Event()
        comecou = self._registrar_bloqueante(liberar)

        contadas = []

        @base.register("t_conta", "Conta", "", remote=True)
        def _conta(params, ctx):
            contadas.append(params["n"])

        runner = ActionRunner(context=ActionContext())
        runner.submit(Action(type="t_rede"))
        self.assertTrue(comecou.wait(timeout=3))
        for n in range(3):
            runner.submit(Action(type="t_conta", params={"n": n}))

        # A thread está presa na ação de rede; o join expira depressa.
        with mock.patch.object(ActionRunner, "JOIN_TIMEOUT_S", 0.2):
            runner.stop()
        liberar.set()
        time.sleep(0.3)

        self.assertEqual(contadas, [], "ações pendentes rodaram no encerramento")

    def test_tipo_desconhecido_e_reportado_sem_enfileirar(self):
        avisos = []
        runner = ActionRunner(context=ActionContext(), on_error=avisos.append)
        self.addCleanup(runner.stop)

        runner.submit(Action(type="nao_existe"))

        self.assertEqual(len(avisos), 1)
        self.assertIn("desconhecido", avisos[0])


class RodizioDePortasTest(unittest.TestCase):
    """``_find_port`` devolvia sempre a primeira candidata. Se ela não fosse
    o macropad (outro conversor USB-serial ligado, por exemplo), o enlace
    tentava a mesma porta indefinidamente e nunca achava o dispositivo.
    """

    class PortaFalsa:
        def __init__(self, device, vid):
            self.device = device
            self.vid = vid
            self.description = ""

    def setUp(self):
        self.portas = [
            self.PortaFalsa("COM3", 0x1234),                  # outro conversor
            self.PortaFalsa("COM4", 0x5678),                  # mais um
            self.PortaFalsa("COM5", protocol.ESPRESSIF_VID),  # o macropad
            self.PortaFalsa("COM1", None),                    # não é USB
        ]
        patcher = mock.patch(
            "macropad.device.link.list_ports.comports", return_value=self.portas
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _link(self, preferred=None) -> SerialLink:
        return SerialLink(
            on_message=lambda m: None,
            on_state=lambda conectado, porta: None,
            preferred_port=preferred,
        )

    def test_espressif_vem_primeiro_e_portas_sem_vid_ficam_de_fora(self):
        self.assertEqual(self._link()._candidates(), ["COM5", "COM3", "COM4"])

    def test_alterna_entre_as_candidatas_que_falharam(self):
        link = self._link()
        tentadas = []
        for _ in range(3):
            porta = link._find_port()
            tentadas.append(porta)
            link._rejected.add(porta)  # simula falha de handshake
        self.assertEqual(tentadas, ["COM5", "COM3", "COM4"])

    def test_reinicia_a_rodada_quando_todas_falharam(self):
        link = self._link()
        link._rejected.update({"COM3", "COM4", "COM5"})
        # O macropad pode ter sido ligado depois: vale tentar de novo.
        self.assertEqual(link._find_port(), "COM5")

    def test_porta_fixada_e_a_unica_considerada(self):
        self.assertEqual(self._link("COM4")._candidates(), ["COM4"])

    def test_porta_fixada_ausente_nao_cai_para_outra(self):
        link = self._link("COM9")
        self.assertEqual(link._candidates(), [])
        self.assertIsNone(link._find_port())


if __name__ == "__main__":
    unittest.main()
