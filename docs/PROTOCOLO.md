# Protocolo de comunicação host ↔ macropad

Este documento é o **contrato entre o software de configuração (host) e o
firmware do ESP32-C3**. Quem for implementar o firmware deve seguir
exatamente estas mensagens.

## Transporte

- **USB CDC serial** (a porta serial nativa do ESP32-C3 via USB Serial/JTAG).
- **115200 bps**, 8N1.
- Mensagens **JSON em uma única linha**, terminadas por `\n` (JSON Lines).
- O host tolera linhas que não sejam JSON (logs de boot do ESP32 são
  ignorados), mas o firmware **não deve** imprimir logs após o boot para
  não poluir o canal.
- O firmware deve suportar linhas de entrada de até **2048 bytes**
  (necessário para a mensagem de imagem).

## Identificação da porta

O host procura portas com o VID USB da Espressif (`0x303A`) e confirma o
dispositivo com um handshake: envia `ping` e espera `pong` (ou qualquer
mensagem válida) em até 2 segundos.

## Mensagens: dispositivo → host

| Mensagem | Quando enviar |
|---|---|
| `{"t":"hello","fw":"1.0.0","keys":18,"screen":{"w":128,"h":64}}` | ao iniciar e ao receber `ping` (junto com `pong`) |
| `{"t":"pong"}` | em resposta a `ping` |
| `{"t":"key","k":0,"e":"down"}` | tecla pressionada (`k` = índice 0–17) |
| `{"t":"key","k":0,"e":"up"}` | tecla solta |

Índice das teclas: varredura por linhas, da esquerda para a direita, de
cima para baixo (tecla 0 = superior esquerda, tecla 17 = inferior direita).
O firmware deve aplicar *debounce* (~5 ms) antes de reportar eventos.

## Mensagens: host → dispositivo

| Mensagem | Efeito |
|---|---|
| `{"t":"ping"}` | responder `pong` (e `hello`); também funciona como *heartbeat* |
| `{"t":"text","lines":["VS Code"]}` | limpar o display e exibir até 3 linhas centralizadas (nome do perfil ativo) |
| `{"t":"img","fmt":"xbm1","d":"<base64>"}` | exibir imagem em tela cheia (ícone do perfil ativo) |

### Formato de imagem `xbm1`

- 128×64 pixels, 1 bit por pixel → **1024 bytes**, codificados em base64
  (~1368 caracteres).
- Varredura por linhas; 8 pixels por byte; **bit mais significativo =
  pixel mais à esquerda**; `1` = pixel aceso.
- Com a biblioteca Adafruit SSD1306, basta decodificar o base64 para um
  buffer de 1024 bytes e chamar
  `display.drawBitmap(0, 0, buffer, 128, 64, SSD1306_WHITE)`.

## Sequência típica

```
Firmware                     Host (software)
   |------- hello ---------------->|   (ao conectar USB)
   |<------ img/text --------------|   (ícone/nome do perfil ativo)
   |------- key k=4 down --------->|   (host executa a ação da tecla 4)
   |------- key k=4 up ----------->|
   |------- key k=17 down -------->|   (tecla de modo: host troca o perfil)
   |<------ img/text --------------|   (display atualizado para o novo perfil)
```

Observação de arquitetura: **toda a lógica de atalhos fica no host**. O
firmware só reporta teclas e desenha o que o host mandar. Isso permite
perfis ilimitados, ações complexas (comandos de terminal, Home Assistant)
e reconfiguração sem regravar o firmware.

## Heartbeat e modo híbrido

O host envia `ping` a cada **3 segundos** enquanto conectado. O firmware
considera o host **presente** se recebeu qualquer mensagem válida nos
últimos **10 segundos**; caso contrário, entra no **modo autônomo**:
atua como teclado Bluetooth (BLE HID) com atalhos fixos gravados no
firmware. Os eventos de tecla continuam sendo emitidos pela serial em
ambos os modos (assim o software "pega" o dispositivo imediatamente ao
abrir). A implementação de referência está em `firmware/`.

### Esqueleto do lado do firmware (Arduino, pseudocódigo)

```cpp
void loop() {
  // 1. Varre a matriz de teclas com debounce; em cada mudança:
  //    Serial.printf("{\"t\":\"key\",\"k\":%d,\"e\":\"%s\"}\n", k, down ? "down" : "up");
  // 2. Lê linhas da Serial; usa ArduinoJson para decodificar:
  //    - "ping" -> responde pong + hello
  //    - "text" -> display.clearDisplay(); imprime as linhas; display.display();
  //    - "img"  -> base64-decode de d para buf[1024]; drawBitmap; display.display();
}
```
