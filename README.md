# Macropad Configurator

Software de configuração e controle do macropad ESP32-C3 (18 teclas +
display OLED 0,96") — TCC de Engenharia da Computação, UEMG Ituiutaba.

O aplicativo detecta o macropad pela porta USB, permite associar uma ação
a cada tecla, organiza as ações em **perfis** ilimitados (com nome e
ícone exibidos no display do dispositivo) e alterna entre perfis por uma
**tecla de modo** escolhida pelo usuário no próprio teclado. Também é
possível **trocar de perfil automaticamente pelo aplicativo em foco**
(opcional; a tecla de modo continua prevalecendo até o foco mudar).

Roda em **segundo plano na bandeja do sistema** (fechar a janela não
encerra) e pode **iniciar junto com o Windows**. O projeto é **híbrido**:
com o software rodando, o macropad tem os recursos completos via USB;
sem o software, o firmware atua como teclado Bluetooth (BLE HID) com
atalhos fixos — ver [firmware/](firmware/README.md).

## Tipos de ação

| Tipo | Exemplo |
|---|---|
| Atalho de teclado | `Ctrl+Shift+P` |
| Digitar texto (+ Enter) | enviar `npm run dev` ao terminal do VS Code |
| Executar comando | `git pull` na pasta do projeto, em terminal visível ou oculto |
| Abrir app/arquivo/site | abrir o VS Code, uma pasta ou uma URL |
| Controle de mídia | volume, mudo, tocar/pausar, próxima faixa |
| Macro | sequência de ações com intervalo configurável |
| Home Assistant | apagar as luzes da sala via API REST local |
| OBS Studio | trocar cena, mutar microfone, gravar/transmitir (obs-websocket) |
| Webhook (HTTP) | chamar n8n, IFTTT, Zapier ou qualquer URL |
| Alternar perfil | mesmo efeito da tecla de modo |

## Requisitos

- Windows 10/11 (ações de teclado usam a API do Windows via `pynput`)
- Python 3.11+

## Instalação e execução

```powershell
cd tcc-macropad
py -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m macropad
```

Ou, no dia a dia, apenas `run.bat`.

**Sem o hardware em mãos?** Selecione **Simulador** na caixa "Conexão":
uma janela reproduz o dispositivo (display + 18 teclas) e todo o software
funciona de forma idêntica.

## Testes

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

## Documentação

- [docs/PROTOCOLO.md](docs/PROTOCOLO.md) — contrato serial host ↔ firmware
  (referência para a implementação do firmware).
- [docs/ARQUITETURA.md](docs/ARQUITETURA.md) — camadas, decisões de
  projeto e como estender.
- [firmware/README.md](firmware/README.md) — firmware de referência do
  ESP32-C3 (modo híbrido USB serial + BLE HID).

## Estrutura

```
src/macropad/
├── core/          # domínio: modelos, perfis, persistência, controlador
├── device/        # protocolo JSON-serial, enlace pyserial, simulador
├── actions/       # motor de ações (registry + thread de execução)
├── integrations/  # Home Assistant, OBS, app em foco
└── ui/            # interface PySide6 (janela, bandeja, diálogos)
firmware/          # sketch Arduino do ESP32-C3 (ajustar pinos em config.h)
```
