/*
 * NanoFC Quad-X Joystick Transmitter Firmware (No OLED)
 * Target: Classic Arduino Nano (ATmega328P, 5V, 16 MHz)
 * Required Library: RF24 (by TMRh20)
 *
 * Wiring:
 *   nRF24L01: CE -> D7, CSN -> D8, SCK -> D13, MOSI -> D11, MISO -> D12, VCC -> 3.3V
 *   Joystick: X -> A2, Y -> A1
 *   Button:   D2 -> GND (INPUT_PULLUP)
 *   LED:      D4 (TX link status)
 */

#include <SPI.h>
#include <RF24.h>
#include <nRF24L01.h>

RF24 radio(7, 8);
const byte address[6] = "00001";

#define BUTTON_PIN   2
#define JOYSTICK_X   A2
#define JOYSTICK_Y   A1
#define PIN_TX_LED   4

#define MIN_THROTTLE 1000
#define MAX_THROTTLE 2000

struct JoystickData {
  uint16_t x;
  uint16_t y;
  uint8_t button;
};

JoystickData data;
unsigned long lastTxMs = 0;

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(PIN_TX_LED, OUTPUT);

  if (!radio.begin()) {
    Serial.println(F("NRF NOT DETECTED!"));
    while (1) {
      digitalWrite(PIN_TX_LED, !digitalRead(PIN_TX_LED));
      delay(200);
    }
  }

  radio.openWritingPipe(address);
  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_250KBPS);
  radio.setRetries(5, 15);
  radio.stopListening();

  Serial.println(F("TRANSMITTER READY"));
}

void loop() {
  if (millis() - lastTxMs >= 20) { // 50 Hz
    lastTxMs = millis();

    data.x = analogRead(JOYSTICK_X);
    data.y = analogRead(JOYSTICK_Y);
    data.button = (digitalRead(BUTTON_PIN) == LOW) ? 1 : 0;

    bool success = radio.write(&data, sizeof(data));
    digitalWrite(PIN_TX_LED, success ? HIGH : LOW);

    int throttle = map(data.y, 0, 1023, MIN_THROTTLE, MAX_THROTTLE);
    Serial.print(F("X: ")); Serial.print(data.x);
    Serial.print(F(" | Y: ")); Serial.print(data.y);
    Serial.print(F(" | THR: ")); Serial.print(throttle);
    Serial.print(F(" | BTN: ")); Serial.print(data.button);
    Serial.println(success ? F(" | TX OK") : F(" | TX FAILED"));
  }
}
