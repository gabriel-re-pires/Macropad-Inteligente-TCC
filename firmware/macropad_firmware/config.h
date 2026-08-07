// =========================================================================
// Configuração do hardware — AJUSTE ESTA SEÇÃO PARA O SEU PCB
// =========================================================================
#pragma once

// --------------------------------------------------------------- modo híbrido
// Comente a linha abaixo para compilar SEM o modo autônomo (teclado
// Bluetooth). O macropad continua completo pela USB — que é como ele
// funciona com o software aberto — e a compilação passa a exigir apenas
// Adafruit SSD1306, Adafruit GFX e ArduinoJson, todas disponíveis no
// Gerenciador de Bibliotecas. Serve para validar o hardware sem depender
// da NimBLE-Arduino e da ESP32-BLE-Keyboard, que se instalam à parte e
// são sensíveis à versão.
#define ENABLE_BLE

#ifdef ENABLE_BLE
// Precisa vir antes do include: a ESP32-BLE-Keyboard usa Bluedroid por
// padrão, que não compila para o C3.
#define USE_NIMBLE
#include <BleKeyboard.h>
#endif

// ---------------------------------------------------------------- teclas
// Matriz 3 linhas x 6 colunas = 18 teclas.
// Índice da tecla = linha * 6 + coluna (tecla 0 = superior esquerda),
// conforme docs/PROTOCOLO.md.
//
// >>> TROQUE os números de GPIO pelos usados no PCB de vocês. <<<
// Convenção elétrica adotada: diodos das teclas orientados LINHA -> COLUNA
// (linha é acionada em LOW; colunas com INPUT_PULLUP).
//
// Evite GPIO 2, 8 e 9 nas LINHAS: são pinos de strapping, lidos no reset
// para decidir o modo de boot. Como a varredura mantém a linha em nível
// baixo, um reset no instante errado faria o chip entrar em modo de
// gravação em vez de rodar o firmware. Nas colunas o risco é menor, já
// que o pull-up as mantém em nível alto.
constexpr uint8_t KEY_ROWS = 3;
constexpr uint8_t KEY_COLS = 6;
constexpr uint8_t KEY_COUNT = KEY_ROWS * KEY_COLS;

constexpr uint8_t ROW_PINS[KEY_ROWS] = {0, 1, 3};          // AJUSTAR
constexpr uint8_t COL_PINS[KEY_COLS] = {4, 5, 6, 7, 10, 20}; // AJUSTAR

constexpr uint32_t DEBOUNCE_MS = 5;

// ---------------------------------------------------------------- display
// OLED 0,96" SSD1306 128x64 via I2C.
constexpr uint8_t OLED_SDA = 8;      // AJUSTAR
constexpr uint8_t OLED_SCL = 9;      // AJUSTAR
constexpr uint8_t OLED_ADDR = 0x3C;  // 0x3C é o padrão da maioria dos módulos
constexpr int16_t OLED_W = 128;
constexpr int16_t OLED_H = 64;

// ------------------------------------------------------------------ host
// O software no PC envia "ping" a cada 3 s; sem mensagens por este tempo,
// o firmware considera o host ausente e ativa o fallback BLE.
constexpr uint32_t HOST_TIMEOUT_MS = 10000;

// ------------------------------------------------------------- modo BLE
#ifdef ENABLE_BLE

// Nome anunciado no pareamento Bluetooth.
#define BLE_DEVICE_NAME "Macropad TCC"

// Atalhos do MODO AUTÔNOMO (sem o software, via teclado Bluetooth).
// Cada tecla pode enviar UMA das opções:
//   - tecla de mídia (campo media, ex.: &KEY_MEDIA_VOLUME_UP)
//   - combinação modificador(es) + tecla (campos mod1/mod2/key)
// Deixe tudo zerado/nullptr para a tecla não fazer nada no modo BLE.
struct FallbackKey {
  const MediaKeyReport *media;  // tecla de mídia, ou nullptr
  uint8_t mod1;                 // ex.: KEY_LEFT_CTRL, ou 0
  uint8_t mod2;                 // ex.: KEY_LEFT_SHIFT, ou 0
  uint8_t key;                  // ex.: 'c' ou KEY_TAB, ou 0
};

const FallbackKey FALLBACK_KEYS[KEY_COUNT] = {
    /*  0 */ {&KEY_MEDIA_PLAY_PAUSE, 0, 0, 0},
    /*  1 */ {&KEY_MEDIA_PREVIOUS_TRACK, 0, 0, 0},
    /*  2 */ {&KEY_MEDIA_NEXT_TRACK, 0, 0, 0},
    /*  3 */ {&KEY_MEDIA_VOLUME_DOWN, 0, 0, 0},
    /*  4 */ {&KEY_MEDIA_VOLUME_UP, 0, 0, 0},
    /*  5 */ {&KEY_MEDIA_MUTE, 0, 0, 0},
    /*  6 */ {nullptr, KEY_LEFT_CTRL, 0, 'c'},
    /*  7 */ {nullptr, KEY_LEFT_CTRL, 0, 'v'},
    /*  8 */ {nullptr, KEY_LEFT_CTRL, 0, 'x'},
    /*  9 */ {nullptr, KEY_LEFT_CTRL, 0, 'z'},
    /* 10 */ {nullptr, KEY_LEFT_CTRL, 0, 'a'},
    /* 11 */ {nullptr, KEY_LEFT_CTRL, 0, 's'},
    /* 12 */ {nullptr, KEY_LEFT_GUI, 0, 'd'},
    /* 13 */ {nullptr, KEY_LEFT_GUI, 0, 'e'},
    /* 14 */ {nullptr, KEY_LEFT_ALT, 0, KEY_TAB},
    /* 15 */ {nullptr, 0, 0, 0},
    /* 16 */ {nullptr, 0, 0, 0},
    /* 17 */ {nullptr, 0, 0, 0},
};

#endif  // ENABLE_BLE
