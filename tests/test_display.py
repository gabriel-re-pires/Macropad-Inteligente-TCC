"""Testes da composição das telas do display e da fonte do firmware."""

import unittest

from macropad.actions import keys
from macropad.core import display, oled_font, oled_render
from macropad.core.models import (
    GRID_COLS,
    GRID_ROWS,
    KEY_COUNT,
    KEY_LAYOUT,
    SCREEN_H,
    SCREEN_W,
    Action,
    Profile,
    key_at,
    short_label,
)


class LayoutTest(unittest.TestCase):
    def test_layout_tem_18_posicoes_distintas_dentro_da_grade(self):
        self.assertEqual(KEY_COUNT, 18)
        self.assertEqual(len(set(KEY_LAYOUT)), 18)
        for row, col in KEY_LAYOUT:
            self.assertTrue(0 <= row < GRID_ROWS and 0 <= col < GRID_COLS)

    def test_linha_de_cima_tem_tres_teclas_a_direita(self):
        # As duas primeiras posições são o módulo e o display.
        self.assertIsNone(key_at(0, 0))
        self.assertIsNone(key_at(0, 1))
        self.assertEqual([key_at(0, c) for c in (2, 3, 4)], [0, 1, 2])
        self.assertEqual(key_at(3, 4), 17)

    def test_indices_seguem_a_ordem_de_leitura(self):
        ordem = sorted(range(KEY_COUNT), key=lambda k: KEY_LAYOUT[k])
        self.assertEqual(ordem, list(range(KEY_COUNT)))


class ShortLabelTest(unittest.TestCase):
    def test_abreviacoes(self):
        casos = {
            "Copiar": "COP",
            "Ctrl+Shift+P": "CSP",
            "npm run dev": "NRD",
            "Edição": "EDI",
            "x": "X",
            "": "?",
        }
        for texto, esperado in casos.items():
            self.assertEqual(short_label(texto), esperado, texto)

    def test_abreviacao_explicita_prevalece_e_nao_e_reabreviada(self):
        action = Action(type="media", label="Aumentar volume", short="VL+")
        self.assertEqual(action.display_short, "VL+")
        self.assertEqual(Action(type="media", label="Aumentar volume").display_short, "AV")

    def test_abreviacao_e_persistida_e_limitada(self):
        action = Action(type="hotkey", short="ABCD")
        restaurada = Action.from_dict(action.to_dict())
        self.assertEqual(restaurada.short, "ABC")
        # Sem abreviação, o campo nem aparece no JSON.
        self.assertNotIn("short", Action(type="hotkey").to_dict())


class FontTest(unittest.TestCase):
    def test_tabela_completa_e_glifo_conhecido(self):
        self.assertEqual(len(oled_font.FONT), 256 * 5)
        # 'A' na fonte clássica da GFX.
        self.assertEqual(list(oled_font.glyph(ord("A"))), [0x7C, 0x12, 0x11, 0x12, 0x7C])

    def test_largura_de_texto_como_getTextBounds(self):  # noqa: N802 — nome da GFX
        self.assertEqual(oled_render.text_width("abc", 1), 18)
        self.assertEqual(oled_render.text_width("abc", 2), 36)

    def test_desenho_do_caractere_respeita_celula_6x8(self):
        frame = oled_render.new_frame()
        oled_render.draw_text(frame, 10, 20, "A", 1)
        pixels = frame.load()
        # Coluna 0 de 'A' = 0x7C: bits 2..6 acesos -> linhas 22..26.
        acesos = [y for y in range(SCREEN_H) if pixels[10, y]]
        self.assertEqual(acesos, [22, 23, 24, 25, 26])
        # A 6ª coluna da célula é o espaçamento: sempre apagada.
        self.assertFalse(any(pixels[15, y] for y in range(SCREEN_H)))

    def test_texto_em_tamanho_2_dobra_os_pixels(self):
        f1 = oled_render.new_frame()
        f2 = oled_render.new_frame()
        oled_render.draw_text(f1, 0, 0, "A", 1)
        oled_render.draw_text(f2, 0, 0, "A", 2)
        p1, p2 = f1.load(), f2.load()
        for x in range(12):
            for y in range(16):
                self.assertEqual(bool(p2[x, y]), bool(p1[x // 2, y // 2]))

    def test_tela_de_texto_segue_a_geometria_do_firmware(self):
        # Uma linha: tamanho 2, altura 20, y = (64 - 20 + 4) // 2 = 24.
        frame = oled_render.render_text_lines(["A"])
        pixels = frame.load()
        linhas = sorted({y for y in range(SCREEN_H) for x in range(SCREEN_W) if pixels[x, y]})
        self.assertEqual(linhas[0], 24)  # a 3ª coluna de 'A' (0x11) acende o bit 0
        # Três linhas: tamanho 1, altura 12, y inicial = (64 - 36 + 4) // 2 = 16.
        frame = oled_render.render_text_lines(["A", "A", "A"])
        pixels = frame.load()
        linhas = sorted({y for y in range(SCREEN_H) for x in range(SCREEN_W) if pixels[x, y]})
        self.assertEqual(linhas[0], 16)
        self.assertEqual(linhas[-1], 16 + 2 * 12 + 6)  # bit 6 = última linha de 'A'


class KeymapFrameTest(unittest.TestCase):
    def _perfil(self):
        perfil = Profile(name="VS Code")
        perfil.bindings[0] = Action(type="hotkey", label="Salvar")
        perfil.bindings[17] = Action(type="hotkey", label="Zzz")
        return perfil

    def test_quadro_tem_o_tamanho_do_display(self):
        frame = display.profile_frame(self._perfil(), None, "mapa")
        self.assertEqual(frame.size, (SCREEN_W, SCREEN_H))
        self.assertEqual(frame.mode, "1")

    def test_cabecalho_invertido_mostra_o_nome(self):
        frame = display.profile_frame(self._perfil(), None, "mapa")
        pixels = frame.load()
        # Cantos da faixa do título acesos; nome em preto no meio.
        self.assertTrue(pixels[0, 0] and pixels[SCREEN_W - 1, 0])
        self.assertTrue(any(not pixels[x, 4] for x in range(40, 88)))

    def test_tecla_de_modo_e_destaque_mudam_o_quadro(self):
        perfil = self._perfil()
        base = display.profile_frame(perfil, None, "mapa").tobytes()
        self.assertNotEqual(display.profile_frame(perfil, 17, "mapa").tobytes(), base)
        self.assertNotEqual(
            display.profile_frame(perfil, None, "mapa", highlight=0).tobytes(), base
        )

    def test_nada_e_desenhado_fora_da_area_util(self):
        shorts = {k: "WWW" for k in range(KEY_COUNT)}
        frame = display.keymap_frame("W" * 30, shorts, highlight=17)
        pixels = frame.load()
        # Última linha do mapa termina antes do fim do display.
        self.assertFalse(any(pixels[x, SCREEN_H - 1] for x in range(SCREEN_W)))

    def test_modo_icone_sem_icone_usa_o_nome_no_maior_tamanho_que_couber(self):
        curto = display.profile_frame(Profile(name="VS Code"), None, "icone")
        longo = display.profile_frame(Profile(name="Edição de vídeo longa"), None, "icone")
        self.assertEqual(curto.tobytes(), oled_render.render_text_lines(["VS Code"]).tobytes())
        self.assertEqual(
            longo.tobytes(),
            oled_render.render_text_lines(["Edicao de video longa"]).tobytes(),
        )

    def test_payload_e_mensagem_sao_reversiveis(self):
        frame = display.profile_frame(self._perfil(), 17, "mapa")
        message = {"t": "img", "fmt": "xbm1", "d": display.frame_payload(frame)}
        restaurado = display.frame_from_message(message)
        self.assertEqual(restaurado.tobytes(), frame.tobytes())
        self.assertIsNone(display.frame_from_message({"t": "img", "d": "!!!"}))
        self.assertIsNone(display.frame_from_message({"t": "ping"}))


class GravacaoDeAtalhoTest(unittest.TestCase):
    """A UI grava combinações com QKeySequenceEdit; a tradução para os
    nomes do pynput é pura e fica fora do Qt."""

    def test_combinacoes(self):
        from PySide6.QtGui import QKeySequence

        casos = {
            "Ctrl+Shift+P": ["ctrl", "shift", "p"],
            "Alt+F4": ["alt", "f4"],
            "Ctrl+Alt+Del": ["ctrl", "alt", "delete"],
            "Meta+E": ["win", "e"],
            "Return": ["enter"],
            "Ctrl+Shift": [],  # só modificadores: inválido
        }
        for texto, esperado in casos.items():
            nomes = keys.names_from_qt(QKeySequence(texto))
            self.assertEqual(nomes, esperado, texto)
            for nome in nomes:
                self.assertTrue(keys.is_valid(nome), nome)


if __name__ == "__main__":
    unittest.main()
