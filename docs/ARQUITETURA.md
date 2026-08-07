# Arquitetura do software

## Visão geral

O software segue uma **arquitetura em camadas** com dependências apontando
para o domínio. A camada de domínio (`core/`) não conhece Qt nem pyserial,
o que permite testá-la isoladamente (18 testes em `tests/`).

```
┌─────────────────────────────────────────────────────┐
│  ui/  (PySide6)                                     │
│  MainWindow · KeyGrid · ActionEditor · ProfilePanel │
│  OledPreview · SimulatorWindow · SettingsDialog     │
│  FlashDialog                                        │
└──────────────┬──────────────────────────────────────┘
               │ sinais Qt (DeviceBridge)
┌──────────────▼──────────────────────────────────────┐
│  app.py — raiz de composição                        │
└───┬──────────────┬──────────────────┬───────────────┘
    │              │                  │
┌───▼────────┐ ┌───▼────────────┐ ┌───▼───────────────┐
│ core/      │ │ actions/       │ │ device/           │
│ Controller │ │ ActionRunner   │ │ SerialLink        │
│ Store      │ │ (thread única) │ │ SimulatorLink     │
│ Profile    │ │ registry de    │ │ protocol (JSON)   │
│ Action     │ │ executores     │ │ flasher (esptool) │
│ icons      │ └───┬────────────┘ │ firmware_release  │
└────────────┘     │              └───────────────────┘
              ┌────▼─────────────┐
              │ integrations/    │
              │ home_assistant   │
              └──────────────────┘
```

## Decisões de projeto

1. **Lógica no host, firmware "burro" (arquitetura host-agent).** O
   ESP32-C3 não possui USB HID nativo (seu periférico USB é um
   controlador Serial/JTAG de função fixa). O dispositivo, portanto,
   reporta eventos de tecla via USB CDC e o software executa as ações.
   Vantagens: perfis ilimitados sem regravar firmware, ações impossíveis
   para um HID puro (comandos de terminal, chamadas HTTP ao Home
   Assistant/OBS/webhooks, macros) e atualização do display pelo host.
   **Modo híbrido:** sem o host (detectado pela ausência do *heartbeat*
   `ping` de 3 s), o firmware vira teclado Bluetooth (BLE HID) com
   atalhos fixos — ver `firmware/`. O software roda em segundo plano na
   bandeja do sistema (fechar a janela não encerra) e pode registrar-se
   na chave `Run` do usuário para iniciar com o Windows
   (`core/autostart.py`).

2. **Ações como Strategy + Registry** (`actions/base.py`). Cada tipo de
   ação é uma função registrada com metadados (título e descrição usados
   pela UI). Adicionar um tipo novo = registrar uma função; nenhuma outra
   camada muda.

3. **Threads.** Quatro threads cooperam: a da UI (Qt), a do enlace serial
   (leitura bloqueante + reconexão) e **duas** do `ActionRunner`. A
   comunicação entre elas usa sinais Qt (`DeviceBridge`), que são
   thread-safe, e `queue.Queue` para as ações.

   O `ActionRunner` tem duas vias porque as ações têm naturezas
   diferentes: as de **entrada** (atalho, texto, mídia, comando, macro)
   disputam o foco do teclado e precisam manter a ordem entre si; as de
   **rede** (webhook, Home Assistant, OBS) podem levar segundos até
   estourar o timeout. Numa via única, um webhook parado atrasaria todas
   as teclas seguintes. O tipo de ação declara a via em que roda
   (`remote=True` no `@register`). As filas são limitadas: martelar
   teclas com algo travado descarta com aviso em vez de acumular um lote
   que dispararia tudo depois.

4. **Simulador** (`device/simulator.py`). Implementa a mesma interface
   `DeviceLink` do enlace serial; a janela do simulador renderiza os
   frames exatamente como o firmware faria. Permite desenvolver e
   demonstrar o software sem o hardware.

5. **Ícones dos perfis.** O display é 128×64 monocromático, então
   qualquer imagem é convertida com Pillow: redimensionada com proporção,
   centralizada e quantizada para 1 bpp com difusão de erro
   (Floyd–Steinberg). Pictogramas simples de alto contraste dão o melhor
   resultado; o preview na UI mostra ao usuário exatamente o que
   aparecerá no OLED antes de salvar.

6. **Persistência** em JSON legível em `%APPDATA%/MacropadConfigurator/`
   com escrita atômica (arquivo temporário + `replace`) e recuperação de
   arquivo corrompido (backup `.bak` + configuração padrão).

7. **Troca automática de perfil** (`integrations/foreground.py`): um
   `QTimer` de 1 s lê o executável da janela em foco (Win32
   `GetForegroundWindow` + `QueryFullProcessImageName`) e ativa o perfil
   vinculado. A detecção é *edge-triggered* — só reage à **mudança** de
   foco —, então uma troca manual pela tecla de modo prevalece até o
   usuário focar outro aplicativo vinculado. O recurso é opcional
   (desligado por padrão) e configurável por perfil ("Apps vinculados").

8. **Integrações OBS/HA/webhook** são tipos de ação comuns registrados
   no mesmo registry; o cliente obs-websocket é criado sob demanda,
   reutilizado entre ações e refeito automaticamente se o OBS reiniciar.

9. **Gravação do firmware pelo próprio aplicativo**
   (`device/flasher.py` + `device/firmware_release.py` + `ui/flash_dialog.py`).
   O configurador embute o `esptool` — a mesma ferramenta que a Arduino
   IDE usa por baixo — e o chama **dentro do processo**, não por
   `subprocess`: no executável do PyInstaller não existe um interpretador
   Python para invocar. O progresso vem do `TemplateLogger`, ponto de
   extensão oficial do esptool 5, cujo logger global é trocado sob um
   lock e restaurado no `finally`.

   O binário gravado é uma **imagem completa** (bootloader + partições +
   aplicação fundidos por `tools/merge_firmware.py`) escrita em 0x0, e
   não os três arquivos soltos da exportação da Arduino IDE: assim o
   aplicativo não precisa conhecer o layout de partições escolhido na
   compilação. A exportação crua (`*.ino.bin`) continua aceita e vai para
   0x10000, distinguida pelo nome.

   Enquanto o diálogo grava, o enlace serial é pausado
   (`MacropadApp.pause_link`) — o esptool precisa da COM com acesso
   exclusivo — e retomado ao fim. A gravação roda em uma `QThread` para
   não congelar a interface durante os ~20 s do processo.

## Segurança

- A ação "Executar comando" roda o que o **próprio usuário** configurou,
  com os privilégios dele — equivalente a digitar no terminal. Perfis
  recebidos de terceiros devem ser revisados antes de importados.
- O token do Home Assistant e a senha do OBS ficam no **Credential
  Manager do Windows** (`keyring`), não no `config.json` — ver
  `core/secrets.py`. Uma configuração antiga com os valores em texto é
  migrada para o cofre na primeira gravação. Se não houver cofre
  disponível, o valor permanece no arquivo e o fato é registrado no log:
  perder a configuração do usuário seria pior. Ainda assim, recomenda-se
  um token exclusivo para o macropad (revogável no painel do HA).
- O `Store` recebe o cofre por injeção (`vault=`), o que mantém os testes
  fora das credenciais reais do usuário.

## Como estender

- **Novo tipo de ação:** registrar uma função em `actions/builtin.py`
  (ou um novo módulo importado por ele) com `@register(...)` e, se o
  formulário genérico não bastar, adicionar uma página em
  `ui/action_editor.py`. Se a ação fizer E/S de rede, passe
  `remote=True` para que ela use a via própria e não atrase as teclas.
- **Nova integração:** criar módulo em `integrations/` e expor como um
  tipo de ação.
- **Novo hardware:** implementar a interface `DeviceLink`. Se o chip
  não for um ESP32-C3, ajustar `flasher.CHIP` e o layout de endereços.
- **Novo firmware publicado:** gerar a imagem com
  `tools/merge_firmware.py` e anexá-la ao release do GitHub como
  `firmware-<versao>.bin` — o aplicativo passa a oferecê-la sozinho.
