# Firmware do macropad (ESP32-C3)

Firmware de referência que implementa o contrato de
[docs/PROTOCOLO.md](../docs/PROTOCOLO.md) e o **modo híbrido**:

- **Modo estendido** — com o software aberto no PC (mesmo em segundo
  plano na bandeja): as teclas são reportadas pela USB serial e o
  software executa as ações; o display mostra o ícone/nome do perfil.
- **Modo autônomo** — sem o software (ou em outro computador/tablet):
  o macropad funciona como **teclado Bluetooth (BLE HID)**, reconhecido
  nativamente pelo sistema, com os atalhos fixos de `config.h`
  (mídia/volume e Ctrl+C/V/X/Z/A/S por padrão).

A detecção é automática: o software envia `ping` a cada 3 s; ficando
10 s sem mensagens, o firmware assume que o host saiu e passa a replicar
as teclas via BLE (e volta sozinho quando o software reabre).

## O que ajustar antes de gravar

Tudo em **`macropad_firmware/config.h`**:

1. `ROW_PINS` / `COL_PINS` — GPIOs da matriz 3×6 conforme o PCB de vocês
   (convenção: diodos linha→coluna; linhas em nível baixo na varredura,
   colunas com pull-up). Se o PCB usa outra orientação de diodo, inverta
   linhas/colunas.
2. `OLED_SDA` / `OLED_SCL` — GPIOs do I2C do display (endereço padrão 0x3C).
3. `FALLBACK_KEYS` — os 18 atalhos do modo autônomo BLE.

O índice das teclas (0 = superior esquerda, 17 = inferior direita) deve
corresponder à grade mostrada no software.

## Gravação

Depois de compilado uma vez, o firmware pode ser gravado **pelo próprio
configurador** (botão *Gravar firmware…*), sem abrir a Arduino IDE — útil
para regravar o dispositivo na apresentação ou em outra máquina. Ver a
seção *Gravar o firmware* do [README principal](../README.md).

A Arduino IDE continua sendo o caminho durante o desenvolvimento do
firmware, e é ela quem produz os binários descritos em
[Publicar uma versão](#publicar-uma-versão).

## Compilação (Arduino IDE)

1. Instale o suporte a ESP32 (Gestor de Placas → "esp32" da Espressif).
2. Placa: **ESP32C3 Dev Module** · **USB CDC On Boot: Enabled** (essencial —
   sem isso o `Serial` não sai pela USB).
3. Bibliotecas (Gerenciador de Bibliotecas):
   - **Adafruit SSD1306** (instala junto a Adafruit GFX)
   - **ArduinoJson** (v7)
   - **NimBLE-Arduino**
4. **ESP32-BLE-Keyboard** — a versão original (T-vK) não compila para o
   C3 com Bluedroid; use o fork com NimBLE:
   <https://github.com/T-vK/ESP32-BLE-Keyboard> (release ≥ 0.3.2) e
   mantenha o `#define USE_NIMBLE` (já presente no .ino; se a sua versão
   da lib exigir, descomente `#define USE_NIMBLE` dentro de
   `BleKeyboard.h`).

## Teste rápido

1. Grave o firmware e abra o software no PC → o status deve mudar para
   "Conectado" e o display mostrar o perfil ativo.
2. Feche o software (Sair na bandeja) → em ~10 s o display volta a
   "Aguardando host..." e, pareado via Bluetooth, as teclas enviam os
   atalhos fixos.
3. Sem display ou sem BLE por enquanto? O firmware continua funcional
   pela serial — o software é tolerante à ausência dessas partes.

## Publicar uma versão

O configurador grava uma **imagem única** (bootloader + tabela de
partições + aplicação), o que o dispensa de conhecer o layout de
partições escolhido na compilação. A Arduino IDE, porém, exporta os três
arquivos separados — `tools/merge_firmware.py` os funde:

1. Atualize `FW_VERSION` no `.ino` (é ele quem aparece no aplicativo e
   nomeia o arquivo gerado).
2. Na Arduino IDE: **Sketch → Exportar Binário Compilado**.
3. Na raiz do projeto:

   ```powershell
   .venv\Scripts\python tools\merge_firmware.py
   ```

   Sem argumentos o script procura a exportação dentro de `firmware/`;
   passe a pasta se ela estiver em outro lugar. O resultado é
   `dist\firmware-<versao>.bin`.
4. Anexe esse arquivo ao *release* do GitHub. O nome precisa casar com
   `firmware*.bin` — é assim que o aplicativo o encontra entre os anexos.

Para testar antes de publicar, use **Arquivo .bin no computador** no
diálogo de gravação; a exportação crua (`*.ino.bin`) também serve, e vai
para 0x10000 preservando o bootloader já gravado no chip.

## Observações

- O ESP32-C3 **não tem USB HID nativo** (o periférico USB é apenas
  Serial/JTAG) — por isso o fallback de teclado usa BLE, não USB.
- Texto no display: o software converte acentos para ASCII antes de
  enviar (a fonte da Adafruit GFX não tem acentuação).
- Logs de depuração: evite `Serial.print` de texto livre após o boot —
  o canal é compartilhado com o protocolo (o host ignora linhas que não
  sejam JSON, mas é desperdício de banda).
