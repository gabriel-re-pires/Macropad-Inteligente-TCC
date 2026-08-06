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

## Download

**[Baixar a última versão →](https://github.com/gabriel-re-pires/Macropad-Inteligente-TCC/releases/latest)**

Pegue o `MacropadConfigurator.exe` e execute: arquivo único, sem console,
que roda em Windows 10/11 **sem instalar Python nem nada mais**.

Como o executável não é assinado digitalmente, o SmartScreen pode avisar
"O Windows protegeu o computador" na primeira execução — clique em **Mais
informações → Executar assim mesmo**. Quem preferir pode gerar o próprio
executável a partir do código (ver [Gerar o executável](#gerar-o-executável)).

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

- **Para usar:** Windows 10/11. O executável do
  [release](https://github.com/gabriel-re-pires/Macropad-Inteligente-TCC/releases/latest)
  já traz tudo de que precisa.
- **Para desenvolver:** Windows 10/11 e Python 3.11+ (as ações de teclado
  usam a API do Windows via `pynput`).

## Rodar a partir do código

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
.venv\Scripts\python -m unittest discover -t . -v
```

## Qualidade de código

As ferramentas de desenvolvimento ficam no extra `dev`:

```powershell
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\ruff check .     # lint (estilo, imports, armadilhas, bandit)
.venv\Scripts\mypy             # checagem de tipos
```

Ambas são configuradas no `pyproject.toml`. As camadas de domínio
(`core/`, `actions/`, `device/`, `integrations/`) são verificadas
integralmente pelo mypy; em `ui/` o código `attr-defined` fica desligado
porque o PySide6 aceita o atalho de enums (`Qt.AlignHCenter`) que suas
stubs não declaram.

## Gerar o executável

O executável publicado está no
[release](https://github.com/gabriel-re-pires/Macropad-Inteligente-TCC/releases/latest);
gere o seu quando quiser empacotar uma versão do código atual:

```powershell
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python tools\build_exe.py
```

O resultado é `dist\MacropadConfigurator.exe` — arquivo único, sem
console, que roda em um Windows sem Python instalado. O ícone é gerado a
partir do mesmo desenho usado pela janela e pela bandeja
(`tools\make_icon.py`), então nunca diverge.

## Compartilhar perfis

**Exportar…** grava o perfil selecionado em um `.json` com o ícone
embutido; **Importar…** o acrescenta em outra máquina, com um `id` novo.

Um perfil pode conter ações que executam comandos ou abrem programas com
os seus privilégios. Ao importar, o aplicativo lista essas ações e pede
confirmação — importe apenas de fontes confiáveis.

## Registro de log

O aplicativo roda sem console, então as mensagens vão para
`%APPDATA%\MacropadConfigurator\logs\macropad.log` (rotativo, 512 KB × 3),
incluindo o traceback de qualquer erro não tratado. É o primeiro lugar a
consultar quando algo não funciona.

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
├── actions/       # motor de ações (registry + duas vias de execução)
├── integrations/  # Home Assistant, OBS, app em foco
└── ui/            # interface PySide6 (janela, bandeja, diálogos)
tools/             # geração do ícone e do executável
firmware/          # sketch Arduino do ESP32-C3 (ajustar pinos em config.h)
```
