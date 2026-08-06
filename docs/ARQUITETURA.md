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
└──────────────┬──────────────────────────────────────┘
               │ sinais Qt (DeviceBridge)
┌──────────────▼──────────────────────────────────────┐
│  app.py — raiz de composição                        │
└───┬──────────────┬──────────────────┬───────────────┘
    │              │                  │
┌───▼────────┐ ┌───▼────────────┐ ┌───▼─────────────┐
│ core/      │ │ actions/       │ │ device/         │
│ Controller │ │ ActionRunner   │ │ SerialLink      │
│ Store      │ │ (thread única) │ │ (thread própria)│
│ Profile    │ │ registry de    │ │ SimulatorLink   │
│ Action     │ │ executores     │ │ protocol (JSON) │
│ icons      │ └───┬────────────┘ └─────────────────┘
└────────────┘     │
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

3. **Threads.** Três threads cooperam: a da UI (Qt), a do enlace serial
   (leitura bloqueante + reconexão) e a do `ActionRunner` (fila de ações).
   A comunicação entre elas usa sinais Qt (`DeviceBridge`), que são
   thread-safe, e uma `queue.Queue` para as ações.

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

## Segurança

- A ação "Executar comando" roda o que o **próprio usuário** configurou,
  com os privilégios dele — equivalente a digitar no terminal. Perfis
  recebidos de terceiros devem ser revisados antes de importados.
- O token do Home Assistant fica em texto no arquivo de configuração
  local. Recomenda-se um token exclusivo para o macropad (revogável no
  painel do HA). Um aprimoramento futuro é usar o Credential Manager do
  Windows via `keyring`.

## Como estender

- **Novo tipo de ação:** registrar uma função em `actions/builtin.py`
  (ou um novo módulo importado por ele) com `@register(...)` e, se o
  formulário genérico não bastar, adicionar uma página em
  `ui/action_editor.py`.
- **Nova integração:** criar módulo em `integrations/` e expor como um
  tipo de ação.
- **Novo hardware:** implementar a interface `DeviceLink`.
