/*
 * NanoFC Quad-X Dual-Joystick Transmitter Firmware (No OLED)
 * Target: Classic Arduino Nano (ATmega328P, 5V, 16 MHz)
 * Required Library: RF24 (by TMRh20)
 *
 * Wiring:
 *   nRF24L01: CE -> D7, CSN -> D8, SCK -> D13, MOSI -> D11, MISO -> D12, VCC -> 3.3V
 *   Left Joystick  (Mode 2): Y (Throttle) -> A1, X (Yaw)   -> A2, Button -> D2
 *   Right Joystick (Mode 2): Y (Pitch)    -> A0, X (Roll)  -> A3, Button -> D3
 *   LED: D4 (TX link status)
 */

#include <SPI.h>
#include <RF24.h>
#include <nRF24L01.h>

RF24 radio(7, 8);
const byte address[6] = "00001";

// Left Stick (Throttle + Yaw)
#define JOY1_X       A2   // Yaw
#define JOY1_Y       A1   // Throttle
#define BTN1_PIN     2

// Right Stick (Roll + Pitch)
#define JOY2_X       A3   // Roll
#define JOY2_Y       A0   // Pitch
#define BTN2_PIN     3

#define PIN_TX_LED   4

// Set true for any axis that moves in the opposite direction
#define INVERT_THR   false
#define INVERT_YAW   false
#define INVERT_ROLL  false
#define INVERT_PITCH false

struct JoystickData {
  uint16_t throttle;
  uint16_t yaw;
  uint16_t roll;
  uint16_t pitch;
  uint8_t  btn1;
  uint8_t  btn2;
};

JoystickData data;
unsigned long lastTxMs = 0;

uint16_t readAxis(uint8_t pin, bool invert) {
  int val = analogRead(pin);
  return invert ? (uint16_t)(1023 - val) : (uint16_t)val;
}

void setup() {
  Serial.begin(115200);
  pinMode(BTN1_PIN, INPUT_PULLUP);
  pinMode(BTN2_PIN, INPUT_PULLUP);
  pinMode(PIN_TX_LED, OUTPUT);

  if (!radio.begin()) {
    Serial.println(F("NRF NOT DETECTED!"));
    while (1) {
      digitalWrite(PIN_TX_LED, !digitalRead(PIN_TX_LED));
      delay(200);
    }
  }

  radio.setChannel(76);
  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_250KBPS);
  radio.setAutoAck(true);
  radio.setPayloadSize(sizeof(JoystickData));
  radio.setRetries(5, 15);
  radio.openWritingPipe(address);
  radio.stopListening();

  Serial.println(F("DUAL-JOYSTICK TRANSMITTER READY"));
}

void loop() {
  if (millis() - lastTxMs >= 20) { // 50 Hz
    lastTxMs = millis();

    data.throttle = readAxis(JOY1_Y, INVERT_THR);
    data.yaw      = readAxis(JOY1_X, INVERT_YAW);
    data.roll     = readAxis(JOY2_X, INVERT_ROLL);
    data.pitch    = readAxis(JOY2_Y, INVERT_PITCH);
    data.btn1     = (digitalRead(BTN1_PIN) == LOW) ? 1 : 0;
    data.btn2     = (digitalRead(BTN2_PIN) == LOW) ? 1 : 0;

    bool success = radio.write(&data, sizeof(data));
    digitalWrite(PIN_TX_LED, success ? HIGH : LOW);

    Serial.print(F("THR:")); Serial.print(map(data.throttle, 0, 1023, 1000, 2000));
    Serial.print(F(" YAW:")); Serial.print(map(data.yaw, 0, 1023, 1000, 2000));
    Serial.print(F(" ROL:")); Serial.print(map(data.roll, 0, 1023, 1000, 2000));
    Serial.print(F(" PIT:")); Serial.print(map(data.pitch, 0, 1023, 1000, 2000));
    Serial.println(success ? F(" | TX OK") : F(" | TX FAILED"));
  }
}
