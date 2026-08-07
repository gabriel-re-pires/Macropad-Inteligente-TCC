// =========================================================================
// Firmware do macropad ESP32-C3 — TCC UEMG
//
// Arquitetura híbrida:
//   * MODO ESTENDIDO (host presente): eventos de tecla vão pela USB serial
//     (JSON Lines, ver docs/PROTOCOLO.md) e o software no PC executa as
//     ações; o display mostra o ícone/nome do perfil enviado pelo host.
//   * MODO AUTÔNOMO (sem host): o dispositivo atua como teclado Bluetooth
//     (BLE HID) com os atalhos fixos definidos em config.h.
//
// O host envia "ping" a cada 3 s; a ausência de mensagens por
// HOST_TIMEOUT_MS caracteriza o modo autônomo.
//
// O modo autônomo é opcional: comente ENABLE_BLE em config.h para
// compilar só com o modo estendido (ver firmware/README.md).
//
// Bibliotecas (Gerenciador de Bibliotecas do Arduino IDE):
//   - Adafruit SSD1306 (+ Adafruit GFX)
//   - ArduinoJson (v7)
// E, apenas com ENABLE_BLE ligado:
//   - NimBLE-Arduino (1.4.x)
//   - ESP32-BLE-Keyboard (instalada por ZIP — ver firmware/README.md)
//
// Placa: "ESP32C3 Dev Module", USB CDC On Boot: "Enabled".
// =========================================================================

#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ArduinoJson.h>
#include <Wire.h>

// Traz BleKeyboard.h (com USE_NIMBLE) quando o modo autônomo está ligado.
#include "config.h"

constexpr char FW_VERSION[] = "1.0.0";

Adafruit_SSD1306 display(OLED_W, OLED_H, &Wire, -1);
#ifdef ENABLE_BLE
BleKeyboard bleKeyboard(BLE_DEVICE_NAME, "UEMG", 100);
#endif

// ------------------------------------------------------------------ estado
bool keyState[KEY_COUNT] = {false};
uint32_t keyChangedAt[KEY_COUNT] = {0};
uint32_t lastHostMessageAt = 0;
bool hostWasActive = false;

// Linha de entrada da serial (a mensagem "img" chega a ~1,5 KB).
constexpr size_t LINE_BUFFER_SIZE = 2048;
char lineBuffer[LINE_BUFFER_SIZE];
size_t lineLength = 0;

uint8_t imageBuffer[OLED_W * OLED_H / 8];  // 1024 bytes (1 bpp)

// ===================================================================== setup

void setup() {
  Serial.begin(115200);

  for (uint8_t r = 0; r < KEY_ROWS; r++) {
    pinMode(ROW_PINS[r], OUTPUT);
    digitalWrite(ROW_PINS[r], HIGH);
  }
  for (uint8_t c = 0; c < KEY_COLS; c++) {
    pinMode(COL_PINS[c], INPUT_PULLUP);
  }

  Wire.begin(OLED_SDA, OLED_SCL);
  if (display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    showStatusScreen();
  }

#ifdef ENABLE_BLE
  bleKeyboard.begin();
#endif
  sendHello();
}

// ====================================================================== loop

void loop() {
  scanKeys();
  readSerial();
  updateHostPresence();
}

// ============================================================ varredura

void scanKeys() {
  for (uint8_t r = 0; r < KEY_ROWS; r++) {
    digitalWrite(ROW_PINS[r], LOW);
    delayMicroseconds(30);  // estabilização da linha
    for (uint8_t c = 0; c < KEY_COLS; c++) {
      uint8_t index = r * KEY_COLS + c;
      bool pressed = (digitalRead(COL_PINS[c]) == LOW);
      if (pressed != keyState[index] &&
          millis() - keyChangedAt[index] >= DEBOUNCE_MS) {
        keyState[index] = pressed;
        keyChangedAt[index] = millis();
        onKeyEvent(index, pressed);
      }
    }
    digitalWrite(ROW_PINS[r], HIGH);
  }
}

void onKeyEvent(uint8_t index, bool pressed) {
  // Sempre reporta pela serial: se o software acabou de abrir, ele já
  // recebe eventos mesmo antes do primeiro ping.
  Serial.printf("{\"t\":\"key\",\"k\":%u,\"e\":\"%s\"}\n", index,
                pressed ? "down" : "up");

#ifdef ENABLE_BLE
  // Modo autônomo: replica o atalho fixo via teclado Bluetooth.
  if (!hostActive() && bleKeyboard.isConnected()) {
    const FallbackKey &fb = FALLBACK_KEYS[index];
    if (pressed) {
      if (fb.media != nullptr) {
        bleKeyboard.press(*fb.media);
      } else if (fb.key != 0) {
        if (fb.mod1 != 0) bleKeyboard.press(fb.mod1);
        if (fb.mod2 != 0) bleKeyboard.press(fb.mod2);
        bleKeyboard.press(fb.key);
      }
    } else {
      bleKeyboard.releaseAll();
    }
  }
#endif
}

// ========================================================== serial (host)

void readSerial() {
  while (Serial.available() > 0) {
    char ch = (char)Serial.read();
    if (ch == '\n') {
      lineBuffer[lineLength] = '\0';
      handleLine(lineBuffer);
      lineLength = 0;
    } else if (lineLength < LINE_BUFFER_SIZE - 1) {
      lineBuffer[lineLength++] = ch;
    } else {
      lineLength = 0;  // linha longa demais: descarta
    }
  }
}

void handleLine(const char *line) {
  if (line[0] != '{') return;  // ignora lixo/eco

  JsonDocument doc;
  if (deserializeJson(doc, line) != DeserializationError::Ok) return;
  const char *type = doc["t"];
  if (type == nullptr) return;

  lastHostMessageAt = millis();

  if (strcmp(type, "ping") == 0) {
    Serial.println("{\"t\":\"pong\"}");
    sendHello();
  } else if (strcmp(type, "text") == 0) {
    showTextScreen(doc["lines"]);
  } else if (strcmp(type, "img") == 0) {
    showImageScreen(doc["d"]);
  }
}

void sendHello() {
  Serial.printf(
      "{\"t\":\"hello\",\"fw\":\"%s\",\"keys\":%u,"
      "\"screen\":{\"w\":%d,\"h\":%d}}\n",
      FW_VERSION, KEY_COUNT, OLED_W, OLED_H);
}

bool hostActive() {
  return lastHostMessageAt != 0 &&
         (millis() - lastHostMessageAt) < HOST_TIMEOUT_MS;
}

void updateHostPresence() {
  bool active = hostActive();
  if (active != hostWasActive) {
    hostWasActive = active;
    if (!active) {
      showStatusScreen();  // host saiu: informa o modo autônomo
    }
  }
}

// ================================================================= display

void showStatusScreen() {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(2);
  display.setCursor(10, 8);
  display.print("macropad");
  display.setTextSize(1);
  display.setCursor(10, 34);
  display.print("Aguardando host...");
  display.setCursor(10, 48);
#ifdef ENABLE_BLE
  display.print(bleKeyboard.isConnected() ? "BLE: conectado"
                                          : "BLE: pareavel");
#else
  display.print("Modo USB apenas");
#endif
  display.display();
}

void showTextScreen(JsonArrayConst lines) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  uint8_t count = 0;
  for (JsonVariantConst v : lines) {
    if (count >= 3) break;
    count++;
  }
  uint8_t size = (count <= 1) ? 2 : 1;
  display.setTextSize(size);
  int16_t lineHeight = 8 * size + 4;
  int16_t y = (OLED_H - count * lineHeight + 4) / 2;
  uint8_t i = 0;
  for (JsonVariantConst v : lines) {
    if (i >= 3) break;
    const char *text = v.as<const char *>();
    if (text == nullptr) continue;
    int16_t bx, by;
    uint16_t bw, bh;
    display.getTextBounds(text, 0, 0, &bx, &by, &bw, &bh);
    int16_t x = (OLED_W - (int16_t)bw) / 2;
    display.setCursor(x > 0 ? x : 0, y);
    display.print(text);
    y += lineHeight;
    i++;
  }
  display.display();
}

void showImageScreen(const char *base64Data) {
  if (base64Data == nullptr) return;
  size_t written = base64Decode(base64Data, imageBuffer, sizeof(imageBuffer));
  if (written != sizeof(imageBuffer)) return;  // payload inválido
  display.clearDisplay();
  // Formato "xbm1" do protocolo = formato nativo do drawBitmap
  // (varredura por linhas, MSB primeiro, 1 = pixel aceso).
  display.drawBitmap(0, 0, imageBuffer, OLED_W, OLED_H, SSD1306_WHITE);
  display.display();
}

// ================================================================== base64

int8_t base64Value(char ch) {
  if (ch >= 'A' && ch <= 'Z') return ch - 'A';
  if (ch >= 'a' && ch <= 'z') return ch - 'a' + 26;
  if (ch >= '0' && ch <= '9') return ch - '0' + 52;
  if (ch == '+') return 62;
  if (ch == '/') return 63;
  return -1;  // '=' ou caractere inválido
}

size_t base64Decode(const char *input, uint8_t *output, size_t maxOut) {
  size_t outLength = 0;
  uint32_t accumulator = 0;
  uint8_t bits = 0;
  for (const char *p = input; *p != '\0'; p++) {
    int8_t value = base64Value(*p);
    if (value < 0) continue;
    accumulator = (accumulator << 6) | (uint32_t)value;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      if (outLength < maxOut) {
        output[outLength++] = (uint8_t)(accumulator >> bits);
      } else {
        return 0;  // estouro: payload maior que o esperado
      }
    }
  }
  return outLength;
}
