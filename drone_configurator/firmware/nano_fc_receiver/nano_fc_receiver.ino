/*
 * NanoFC Quad-X Receiver & Flight Controller Firmware
 * Target: Classic Arduino Nano (ATmega328P, 5V, 16 MHz)
 * Required Libraries: Servo, Wire, EEPROM (+ RF24 if ENABLE_NRF24)
 * (No ArduinoJson required: uses zero-heap C JSON parser & Flash F() serializer)
 *
 * SRAM-optimized for ATmega328P (2 KB SRAM):
 * - Outgoing JSON uses Serial.print(F(...)) -> 0 bytes SRAM.
 * - Incoming JSON uses zero-allocation C field helpers -> 0 bytes heap.
 * - Wire.setWireTimeout(3000, true) prevents I2C lockups if MPU6050 is unplugged.
 */

#include <Wire.h>
#include <Servo.h>
#include <EEPROM.h>
#include "config.h"

#ifdef ENABLE_NRF24
#include <SPI.h>
#include <RF24.h>
RF24 radio(PIN_NRF_CE, PIN_NRF_CSN);
const byte RX_ADDR[6] = "00001"; // Matches your TX Nano address
struct JoystickData {
  uint16_t throttle;
  uint16_t yaw;
  uint16_t roll;
  uint16_t pitch;
  uint8_t  btn1;
  uint8_t  btn2;
};
#endif

// ---- Data Structures persisted in EEPROM ----
struct AxisPID { float p, i, d; };

struct FCConfig {
  uint16_t magic;
  bool angleLoopEnabled;
  AxisPID rateRoll, ratePitch, rateYaw;
  AxisPID angleRoll, anglePitch, angleYaw;
  uint16_t motorMinUs, motorIdleUs, motorMaxUs, motorTestMaxUs;
  uint16_t radioTimeoutMs;
  float gyroOffset[3];
  float accelOffset[3];
  bool gyroCalibrated;
  bool accelCalibrated;
};

FCConfig cfg;

// ---- Runtime State ----
Servo esc[4];
uint16_t motorOutUs[4] = {1000, 1000, 1000, 1000};
bool armed = false;
bool mpuConnected = false;
bool rxConnected = false;

// Motor test safety state
bool motorTestActive = false;
uint8_t motorTestIdx = 0;
uint16_t motorTestPwm = 1000;
unsigned long motorTestDeadlineMs = 0;

// Telemetry streaming state (starts false so boot does not flood PC serial buffer before 'hello')
bool streamEnabled = false;
uint16_t streamIntervalMs = 50; // 20 Hz default
unsigned long lastTelemetryMs = 0;
unsigned long lastLoopUs = 0;
uint16_t loopHz = 250;

// IMU & Attitude state
float ax = 0, ay = 0, az = 1.0f;
float gx = 0, gy = 0, gz = 0;
float imuTempC = 25.0f;
float rollDeg = 0.0f, pitchDeg = 0.0f;

// Radio state
uint16_t rxRoll = 1500, rxPitch = 1500, rxThr = 1000, rxYaw = 1500;
unsigned long lastRxPacketMs = 0;
uint8_t prevArmBtn = 0;
unsigned long lastArmToggleMs = 0;

// PID controller state
float iRoll = 0, iPitch = 0, iYaw = 0;
float prevErrRoll = 0, prevErrPitch = 0, prevErrYaw = 0;

void resetPIDState() {
  iRoll = iPitch = iYaw = 0.0f;
  prevErrRoll = prevErrPitch = prevErrYaw = 0.0f;
}

// Serial line buffer (fixed-size to avoid SRAM fragmentation)
char rxBuf[280];
uint16_t rxPos = 0;
bool rxLineReady = false;

void bufferSerialBytes() {
  while (Serial.available() > 0 && !rxLineReady) {
    char c = (char)Serial.read();
    if (c == '\n') {
      rxBuf[rxPos] = '\0';
      if (rxPos > 0) rxLineReady = true;
      rxPos = 0;
    } else if (c != '\r' && rxPos < sizeof(rxBuf) - 1) {
      rxBuf[rxPos++] = c;
    }
  }
}

// ---- Helpers ----
int freeRamBytes() {
  extern int __heap_start, *__brkval;
  int v;
  return (int)&v - (__brkval == 0 ? (int)&__heap_start : (int)__brkval);
}

void loadDefaultConfig() {
  cfg.magic = EEPROM_MAGIC;
  cfg.angleLoopEnabled = true;
  cfg.rateRoll  = {1.30f, 0.04f, 18.0f};
  cfg.ratePitch = {1.30f, 0.04f, 18.0f};
  cfg.rateYaw   = {3.00f, 0.02f, 0.0f};
  cfg.angleRoll  = {4.50f, 0.00f, 0.0f};
  cfg.anglePitch = {4.50f, 0.00f, 0.0f};
  cfg.angleYaw   = {0.00f, 0.00f, 0.0f};
  cfg.motorMinUs = 1000;
  cfg.motorIdleUs = 1080;
  cfg.motorMaxUs = 2000;
  cfg.motorTestMaxUs = MOTOR_TEST_CAP_US;
  cfg.radioTimeoutMs = 500;
  for (int i = 0; i < 3; i++) {
    cfg.gyroOffset[i] = 0.0f;
    cfg.accelOffset[i] = 0.0f;
  }
  cfg.gyroCalibrated = false;
  cfg.accelCalibrated = false;
}

void saveConfigEEPROM() {
  EEPROM.put(0, cfg);
}

void loadConfigEEPROM() {
  FCConfig tmp;
  EEPROM.get(0, tmp);
  if (tmp.magic == EEPROM_MAGIC) {
    cfg = tmp;
  } else {
    loadDefaultConfig();
    saveConfigEEPROM();
  }
}

void setMotorUs(uint8_t idx, uint16_t pwm) {
  if (motorOutUs[idx] != pwm) {
    motorOutUs[idx] = pwm;
    esc[idx].writeMicroseconds(pwm);
  }
}

void stopAllMotors() {
  motorTestActive = false;
  for (int i = 0; i < 4; i++) {
    setMotorUs(i, cfg.motorMinUs);
  }
}

bool initMPU6050() {
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(0x6B);
  Wire.write(0x00);
  if (Wire.endTransmission() != 0) return false;

  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(0x1B); Wire.write(0x08);
  Wire.endTransmission();
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(0x1C); Wire.write(0x08);
  Wire.endTransmission();
  return true;
}

bool readMPU6050(float dt) {
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint8_t)MPU6050_ADDR, (uint8_t)14, (uint8_t)true) != 14) return false;

  int16_t rawAx = (Wire.read() << 8) | Wire.read();
  int16_t rawAy = (Wire.read() << 8) | Wire.read();
  int16_t rawAz = (Wire.read() << 8) | Wire.read();
  int16_t rawT  = (Wire.read() << 8) | Wire.read();
  int16_t rawGx = (Wire.read() << 8) | Wire.read();
  int16_t rawGy = (Wire.read() << 8) | Wire.read();
  int16_t rawGz = (Wire.read() << 8) | Wire.read();

  ax = (rawAx / 8192.0f) - cfg.accelOffset[0];
  ay = (rawAy / 8192.0f) - cfg.accelOffset[1];
  az = (rawAz / 8192.0f) - cfg.accelOffset[2];
  imuTempC = (rawT / 340.0f) + 36.53f;
  gx = (rawGx / 65.5f) - cfg.gyroOffset[0];
  gy = (rawGy / 65.5f) - cfg.gyroOffset[1];
  gz = (rawGz / 65.5f) - cfg.gyroOffset[2];

  float accRoll  = atan2(ay, az) * 57.2958f;
  float accPitch = atan2(-ax, sqrt(ay * ay + az * az)) * 57.2958f;
  rollDeg  = 0.98f * (rollDeg + gx * dt) + 0.02f * accRoll;
  pitchDeg = 0.98f * (pitchDeg + gy * dt) + 0.02f * accPitch;
  return true;
}

// ---- Zero-SRAM-Allocation JSON Serializers ----
void printAxisPID(const AxisPID& a) {
  Serial.print(F("{\"p\":")); Serial.print(a.p, 3);
  Serial.print(F(",\"i\":")); Serial.print(a.i, 3);
  Serial.print(F(",\"d\":")); Serial.print(a.d, 3);
  Serial.print('}');
}

void printPIDObject() {
  Serial.print(F("{\"angle_loop_enabled\":"));
  Serial.print(cfg.angleLoopEnabled ? F("true") : F("false"));
  Serial.print(F(",\"rate\":{\"roll\":")); printAxisPID(cfg.rateRoll);
  Serial.print(F(",\"pitch\":")); printAxisPID(cfg.ratePitch);
  Serial.print(F(",\"yaw\":")); printAxisPID(cfg.rateYaw);
  Serial.print(F("},\"angle\":{\"roll\":")); printAxisPID(cfg.angleRoll);
  Serial.print(F(",\"pitch\":")); printAxisPID(cfg.anglePitch);
  Serial.print(F(",\"yaw\":")); printAxisPID(cfg.angleYaw);
  Serial.print(F("}}"));
}

void sendError(long id, const char* cmd, const __FlashStringHelper* code, const __FlashStringHelper* msg) {
  Serial.print(F("{\"type\":\"err\""));
  if (id >= 0) { Serial.print(F(",\"id\":")); Serial.print(id); }
  Serial.print(F(",\"cmd\":\"")); Serial.print(cmd);
  Serial.print(F("\",\"ok\":false,\"code\":\"")); Serial.print(code);
  Serial.print(F("\",\"msg\":\"")); Serial.print(msg);
  Serial.println(F("\"}"));
}

void sendAckPrefix(long id, const char* cmd) {
  Serial.print(F("{\"type\":\"ack\",\"id\":"));
  Serial.print(id);
  Serial.print(F(",\"cmd\":\""));
  Serial.print(cmd);
  Serial.print(F("\",\"ok\":true,\"data\":"));
}

void runCalibration(const char* target) {
  const int SAMPLES = 150;
  float sum[3] = {0, 0, 0};
  for (int i = 0; i < SAMPLES; i++) {
    readMPU6050(0.005f);
    if (strcmp(target, "gyro") == 0) {
      sum[0] += gx + cfg.gyroOffset[0];
      sum[1] += gy + cfg.gyroOffset[1];
      sum[2] += gz + cfg.gyroOffset[2];
    } else {
      sum[0] += ax + cfg.accelOffset[0];
      sum[1] += ay + cfg.accelOffset[1];
      sum[2] += (az + cfg.accelOffset[2]) - 1.0f;
    }
    if (i % 30 == 0 || i == SAMPLES - 1) {
      int pct = ((i + 1) * 100) / SAMPLES;
      Serial.print(F("{\"type\":\"cal_progress\",\"target\":\""));
      Serial.print(target);
      Serial.print(F("\",\"pct\":"));
      Serial.print(pct);
      Serial.print(F(",\"stage\":\""));
      Serial.print(pct >= 100 ? F("done") : F("sampling"));
      Serial.print(F("\",\"msg\":\""));
      Serial.print(pct >= 100 ? F("Calibration complete") : F("Sampling offsets..."));
      Serial.println(F("\"}"));
    }
    delay(5);
  }
  if (strcmp(target, "gyro") == 0) {
    for (int k = 0; k < 3; k++) cfg.gyroOffset[k] = sum[k] / SAMPLES;
    cfg.gyroCalibrated = true;
  } else {
    for (int k = 0; k < 3; k++) cfg.accelOffset[k] = sum[k] / SAMPLES;
    cfg.accelCalibrated = true;
  }
}

// ---- Zero-Allocation C JSON Field Helpers ----
const char* findJsonKey(const char* src, const char* key) {
  if (!src) return nullptr;
  char pat[28];
  snprintf(pat, sizeof(pat), "\"%s\":", key);
  const char* p = strstr(src, pat);
  if (!p) return nullptr;
  p += strlen(pat);
  while (*p == ' ' || *p == '\t') p++;
  return p;
}

long jsonGetLong(const char* src, const char* key, long fallback) {
  const char* p = findJsonKey(src, key);
  if (!p) return fallback;
  return strtol(p, nullptr, 10);
}

float jsonGetFloat(const char* src, const char* key, float fallback) {
  const char* p = findJsonKey(src, key);
  if (!p) return fallback;
  return (float)strtod(p, nullptr);
}

bool jsonGetBool(const char* src, const char* key, bool fallback) {
  const char* p = findJsonKey(src, key);
  if (!p) return fallback;
  if (strncmp(p, "true", 4) == 0) return true;
  if (strncmp(p, "false", 5) == 0) return false;
  return fallback;
}

bool jsonGetStr(const char* src, const char* key, char* out, size_t outLen) {
  const char* p = findJsonKey(src, key);
  if (!p || *p != '"') return false;
  p++;
  size_t i = 0;
  while (*p && *p != '"' && i + 1 < outLen) {
    out[i++] = *p++;
  }
  out[i] = '\0';
  return true;
}

void parseAxisPID(const char* block, const char* axisKey, AxisPID& target) {
  const char* ax = findJsonKey(block, axisKey);
  if (!ax) return;
  target.p = jsonGetFloat(ax, "p", target.p);
  target.i = jsonGetFloat(ax, "i", target.i);
  target.d = jsonGetFloat(ax, "d", target.d);
}

void handleJsonCommand(const char* line) {
  char cmd[24] = "";
  if (!jsonGetStr(line, "cmd", cmd, sizeof(cmd))) {
    sendError(-1, "", F("BAD_JSON"), F("Missing cmd"));
    return;
  }
  long id = jsonGetLong(line, "id", -1L);
  const char* data = findJsonKey(line, "data");
  if (!data) data = line;

  if (strcmp(cmd, "hello") == 0) {
    sendAckPrefix(id, cmd);
    Serial.print(F("{\"device\":\"" FC_DEVICE_NAME "\",\"mcu\":\"" FC_MCU_NAME
                   "\",\"fw_version\":\"" FC_FW_VERSION "\",\"protocol_version\":\"" FC_PROTOCOL_VER
                   "\",\"layout\":\"" FC_LAYOUT_NAME "\"}"));
    Serial.println('}');
    return;
  }

  if (strcmp(cmd, "get_config") == 0) {
    sendAckPrefix(id, cmd);
    Serial.print(F("{\"pid\":"));
    printPIDObject();
    Serial.print(F(",\"motor\":{\"min_us\":")); Serial.print(cfg.motorMinUs);
    Serial.print(F(",\"idle_us\":")); Serial.print(cfg.motorIdleUs);
    Serial.print(F(",\"max_us\":")); Serial.print(cfg.motorMaxUs);
    Serial.print(F(",\"test_max_us\":")); Serial.print(cfg.motorTestMaxUs);
    Serial.print(F(",\"esc_cal\":true},\"radio\":{\"timeout_ms\":"));
    Serial.print(cfg.radioTimeoutMs);
    Serial.println(F("}}}"));
    return;
  }

  if (strcmp(cmd, "set_pid") == 0) {
    cfg.angleLoopEnabled = jsonGetBool(data, "angle_loop_enabled", cfg.angleLoopEnabled);
    const char* rate = findJsonKey(data, "rate");
    if (rate) {
      parseAxisPID(rate, "roll", cfg.rateRoll);
      parseAxisPID(rate, "pitch", cfg.ratePitch);
      parseAxisPID(rate, "yaw", cfg.rateYaw);
    }
    const char* ang = findJsonKey(data, "angle");
    if (ang) {
      parseAxisPID(ang, "roll", cfg.angleRoll);
      parseAxisPID(ang, "pitch", cfg.anglePitch);
      parseAxisPID(ang, "yaw", cfg.angleYaw);
    }
    sendAckPrefix(id, cmd);
    Serial.print(F("{\"pid\":"));
    printPIDObject();
    Serial.println(F("}}"));
    return;
  }

  if (strcmp(cmd, "reset_pid") == 0) {
    loadDefaultConfig();
    sendAckPrefix(id, cmd);
    Serial.print(F("{\"pid\":"));
    printPIDObject();
    Serial.println(F("}}"));
    return;
  }

  if (strcmp(cmd, "save_eeprom") == 0) {
    saveConfigEEPROM();
    sendAckPrefix(id, cmd);
    Serial.println(F("{\"saved\":true}}"));
    return;
  }

  if (strcmp(cmd, "cal_start") == 0) {
    if (armed) { sendError(id, cmd, F("ARMED"), F("Disarm before calibrating")); return; }
    if (!mpuConnected) { sendError(id, cmd, F("NO_MPU"), F("MPU6050 not detected")); return; }
    char target[12] = "gyro";
    jsonGetStr(data, "target", target, sizeof(target));
    sendAckPrefix(id, cmd);
    Serial.println(F("{\"started\":true}}"));
    runCalibration(target);
    return;
  }

  if (strcmp(cmd, "motor_test") == 0) {
    if (armed) { sendError(id, cmd, F("ARMED"), F("Cannot test motors while armed")); return; }
    if (!jsonGetBool(data, "confirm", false)) { sendError(id, cmd, F("NO_CONFIRM"), F("Confirmation required")); return; }
    int m = (int)jsonGetLong(data, "motor", 0);
    int pwm = (int)jsonGetLong(data, "pwm", 1000);
    if (m < 1 || m > 4) { sendError(id, cmd, F("BAD_MOTOR"), F("Motor must be 1..4")); return; }
    if (pwm < cfg.motorMinUs || pwm > cfg.motorTestMaxUs) {
      sendError(id, cmd, F("PWM_LIMIT"), F("PWM exceeds safe motor test cap"));
      return;
    }
    motorTestActive = true;
    motorTestIdx = m - 1;
    motorTestPwm = pwm;
    motorTestDeadlineMs = millis() + MOTOR_TEST_WD_MS;
    sendAckPrefix(id, cmd);
    Serial.print(F("{\"motor\":")); Serial.print(m);
    Serial.print(F(",\"pwm\":")); Serial.print(pwm);
    Serial.println(F("}}"));
    return;
  }

  if (strcmp(cmd, "motor_stop") == 0) {
    stopAllMotors();
    sendAckPrefix(id, cmd);
    Serial.println(F("{\"stopped\":true}}"));
    return;
  }

  if (strcmp(cmd, "set_motor_cfg") == 0) {
    cfg.motorMinUs = constrain((int)jsonGetLong(data, "min_us", cfg.motorMinUs), 900, 1200);
    cfg.motorIdleUs = constrain((int)jsonGetLong(data, "idle_us", cfg.motorIdleUs), 1000, 1300);
    cfg.motorMaxUs = constrain((int)jsonGetLong(data, "max_us", cfg.motorMaxUs), 1700, 2100);
    cfg.motorTestMaxUs = constrain((int)jsonGetLong(data, "test_max_us", cfg.motorTestMaxUs), cfg.motorMinUs, 1400);
    sendAckPrefix(id, cmd);
    Serial.print(F("{\"motor\":{\"min_us\":")); Serial.print(cfg.motorMinUs);
    Serial.print(F(",\"idle_us\":")); Serial.print(cfg.motorIdleUs);
    Serial.print(F(",\"max_us\":")); Serial.print(cfg.motorMaxUs);
    Serial.print(F(",\"test_max_us\":")); Serial.print(cfg.motorTestMaxUs);
    Serial.println(F("}}}"));
    return;
  }

  if (strcmp(cmd, "set_radio_cfg") == 0) {
    cfg.radioTimeoutMs = constrain((int)jsonGetLong(data, "timeout_ms", cfg.radioTimeoutMs), 100, 5000);
    sendAckPrefix(id, cmd);
    Serial.print(F("{\"timeout_ms\":")); Serial.print(cfg.radioTimeoutMs);
    Serial.println(F("}}"));
    return;
  }

  if (strcmp(cmd, "set_stream") == 0) {
    streamEnabled = jsonGetBool(data, "enabled", true);
    int rate = constrain((int)jsonGetLong(data, "rate_hz", 20), 5, 50);
    streamIntervalMs = 1000 / rate;
    sendAckPrefix(id, cmd);
    Serial.print(F("{\"rate_hz\":")); Serial.print(rate);
    Serial.println(F("}}"));
    return;
  }

  sendError(id, cmd, F("UNKNOWN_CMD"), F("Unsupported command"));
}

void sendTelemetry() {
  Serial.print(F("{\"type\":\"telemetry\",\"status\":{\"armed\":"));
  Serial.print(armed ? F("true") : F("false"));
  Serial.print(F(",\"mode\":\"")); Serial.print(cfg.angleLoopEnabled ? F("STABILIZE") : F("ACRO"));
  Serial.print(F("\",\"rx\":")); Serial.print(rxConnected ? F("true") : F("false"));
  Serial.print(F(",\"mpu\":")); Serial.print(mpuConnected ? F("true") : F("false"));
#ifdef ENABLE_VBAT_MONITOR
  Serial.print(F(",\"bat_v\":")); Serial.print(analogRead(PIN_VBAT) * VBAT_SCALE, 2);
#endif
  Serial.print(F(",\"hz\":")); Serial.print(loopHz);
  Serial.print(F(",\"ram\":")); Serial.print(freeRamBytes());
  bufferSerialBytes();

  Serial.print(F("},\"imu\":{\"ax\":")); Serial.print(ax, 3);
  Serial.print(F(",\"ay\":")); Serial.print(ay, 3);
  Serial.print(F(",\"az\":")); Serial.print(az, 3);
  Serial.print(F(",\"gx\":")); Serial.print(gx, 2);
  Serial.print(F(",\"gy\":")); Serial.print(gy, 2);
  Serial.print(F(",\"gz\":")); Serial.print(gz, 2);
  Serial.print(F(",\"roll\":")); Serial.print(rollDeg, 2);
  Serial.print(F(",\"pitch\":")); Serial.print(pitchDeg, 2);
  Serial.print(F(",\"yaw_rate\":")); Serial.print(gz, 2);
  Serial.print(F(",\"temp\":")); Serial.print(imuTempC, 1);
  Serial.print(F(",\"mpu\":")); Serial.print(mpuConnected ? F("true") : F("false"));
  Serial.print(F(",\"gcal\":")); Serial.print(cfg.gyroCalibrated ? F("true") : F("false"));
  Serial.print(F(",\"acal\":")); Serial.print(cfg.accelCalibrated ? F("true") : F("false"));
  Serial.print(F(",\"ts\":")); Serial.print(millis());
  bufferSerialBytes();

  Serial.print(F("},\"rx\":{\"roll\":")); Serial.print(rxRoll);
  Serial.print(F(",\"pitch\":")); Serial.print(rxPitch);
  Serial.print(F(",\"thr\":")); Serial.print(rxThr);
  Serial.print(F(",\"yaw\":")); Serial.print(rxYaw);
  Serial.print(F(",\"rx\":")); Serial.print(rxConnected ? F("true") : F("false"));
  Serial.print(F(",\"age_ms\":")); Serial.print(millis() - lastRxPacketMs);

  Serial.print(F("},\"motors\":{\"m\":["));
  for (int i = 0; i < 4; i++) {
    if (i > 0) Serial.print(',');
    Serial.print(motorOutUs[i]);
  }
  Serial.print(F("],\"test\":"));
  Serial.print(motorTestActive ? F("true") : F("false"));
  if (motorTestActive) {
    Serial.print(F(",\"test_m\":")); Serial.print(motorTestIdx + 1);
  }
  Serial.println(F("}}"));
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  pinMode(PIN_STATUS_LED, OUTPUT);
  Wire.begin();
  Wire.setClock(400000);
  Wire.setWireTimeout(3000, true); // Prevent I2C hang if MPU6050 is disconnected

  loadConfigEEPROM();

  esc[0].attach(PIN_MOTOR_1, MOTOR_HARD_MIN_US, MOTOR_HARD_MAX_US);
  esc[1].attach(PIN_MOTOR_2, MOTOR_HARD_MIN_US, MOTOR_HARD_MAX_US);
  esc[2].attach(PIN_MOTOR_3, MOTOR_HARD_MIN_US, MOTOR_HARD_MAX_US);
  esc[3].attach(PIN_MOTOR_4, MOTOR_HARD_MIN_US, MOTOR_HARD_MAX_US);
  for (int i = 0; i < 4; i++) {
    motorOutUs[i] = cfg.motorMinUs;
    esc[i].writeMicroseconds(cfg.motorMinUs);
  }

  mpuConnected = initMPU6050();

#ifdef ENABLE_NRF24
  radio.begin();
  radio.setChannel(76);
  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_250KBPS);
  radio.setAutoAck(true);
  radio.openReadingPipe(1, RX_ADDR);
  radio.startListening();
#endif

  lastLoopUs = micros();
}

unsigned long lastMpuRetryMs = 0;

float applyDeadband(int16_t delta, int16_t db) {
  if (abs(delta) <= db) return 0.0f;
  return (float)(delta > 0 ? delta - db : delta + db);
}

void runFlightMixer(float dt) {
  if (rxThr < 1060) {
    resetPIDState();
    for (int i = 0; i < 4; i++) setMotorUs(i, cfg.motorIdleUs);
    return;
  }

  float rollStick  = applyDeadband((int16_t)rxRoll - 1500, 10) / 500.0f;
  float pitchStick = applyDeadband((int16_t)rxPitch - 1500, 10) / 500.0f;
  float yawStick   = applyDeadband((int16_t)rxYaw - 1500, 10) / 500.0f;

  float targetRateRoll, targetRatePitch;
  if (cfg.angleLoopEnabled) {
    float targetAngleRoll  = rollStick * 30.0f;   // +/- 30 deg max
    float targetAnglePitch = pitchStick * 30.0f;
    targetRateRoll  = (targetAngleRoll  - rollDeg)  * cfg.angleRoll.p;
    targetRatePitch = (targetAnglePitch - pitchDeg) * cfg.anglePitch.p;
  } else {
    targetRateRoll  = rollStick * 200.0f;         // +/- 200 deg/s in ACRO
    targetRatePitch = pitchStick * 200.0f;
  }
  float targetRateYaw = yawStick * 180.0f;

  float errRoll  = targetRateRoll  - gx;
  float errPitch = targetRatePitch - gy;
  float errYaw   = targetRateYaw   - gz;

  iRoll  = constrain(iRoll  + errRoll  * cfg.rateRoll.i  * dt, -150.0f, 150.0f);
  iPitch = constrain(iPitch + errPitch * cfg.ratePitch.i * dt, -150.0f, 150.0f);
  iYaw   = constrain(iYaw   + errYaw   * cfg.rateYaw.i   * dt, -150.0f, 150.0f);

  float dRoll  = ((errRoll  - prevErrRoll)  / dt) * (cfg.rateRoll.d  * 0.01f);
  float dPitch = ((errPitch - prevErrPitch) / dt) * (cfg.ratePitch.d * 0.01f);
  float dYaw   = ((errYaw   - prevErrYaw)   / dt) * (cfg.rateYaw.d   * 0.01f);
  prevErrRoll = errRoll; prevErrPitch = errPitch; prevErrYaw = errYaw;

  float outRoll  = constrain(errRoll  * cfg.rateRoll.p  + iRoll  + dRoll,  -350.0f, 350.0f);
  float outPitch = constrain(errPitch * cfg.ratePitch.p + iPitch + dPitch, -350.0f, 350.0f);
  float outYaw   = constrain(errYaw   * cfg.rateYaw.p   + iYaw   + dYaw,   -350.0f, 350.0f);

  // Quad-X Mixer: M1=FL(CW), M2=FR(CCW), M3=RR(CW), M4=RL(CCW)
  int m1 = constrain((int)(rxThr + outRoll + outPitch - outYaw), cfg.motorIdleUs, cfg.motorMaxUs);
  int m2 = constrain((int)(rxThr - outRoll + outPitch + outYaw), cfg.motorIdleUs, cfg.motorMaxUs);
  int m3 = constrain((int)(rxThr - outRoll - outPitch - outYaw), cfg.motorIdleUs, cfg.motorMaxUs);
  int m4 = constrain((int)(rxThr + outRoll - outPitch + outYaw), cfg.motorIdleUs, cfg.motorMaxUs);

  setMotorUs(0, (uint16_t)m1);
  setMotorUs(1, (uint16_t)m2);
  setMotorUs(2, (uint16_t)m3);
  setMotorUs(3, (uint16_t)m4);
}

void loop() {
  unsigned long nowUs = micros();
  float dt = (nowUs - lastLoopUs) / 1000000.0f;
  if (dt <= 0.0f || dt > 0.1f) dt = 0.004f;
  lastLoopUs = nowUs;

  if (mpuConnected) {
    mpuConnected = readMPU6050(dt);
  } else if (millis() - lastMpuRetryMs >= 500) {
    lastMpuRetryMs = millis();
    mpuConnected = initMPU6050();
  }

#ifdef ENABLE_NRF24
  while (radio.available()) {
    JoystickData pkt;
    radio.read(&pkt, sizeof(pkt));
    rxThr   = constrain(map((long)pkt.throttle, 0, 1023, 1000, 2000), 1000, 2000);
    rxYaw   = constrain(map((long)pkt.yaw,      0, 1023, 1000, 2000), 1000, 2000);
    rxRoll  = constrain(map((long)pkt.roll,     0, 1023, 1000, 2000), 1000, 2000);
    rxPitch = constrain(map((long)pkt.pitch,    0, 1023, 1000, 2000), 1000, 2000);
    lastRxPacketMs = millis();
    rxConnected = true;

    // Toggle Arm/Disarm on Left Stick button (btn1 on D2) rising edge
    if (pkt.btn1 == 1 && prevArmBtn == 0 && (millis() - lastArmToggleMs > 300)) {
      lastArmToggleMs = millis();
      if (armed) {
        armed = false;
        resetPIDState();
        stopAllMotors();
      } else if (rxThr < 1060 && mpuConnected && !motorTestActive) {
        resetPIDState();
        armed = true;
      }
    }
    prevArmBtn = pkt.btn1;
  }
  if (millis() - lastRxPacketMs > cfg.radioTimeoutMs) {
    rxConnected = false;
    rxThr = 1000;
    if (armed) {
      armed = false;
      resetPIDState();
      stopAllMotors();
    }
  }
#endif

  if (armed) {
    runFlightMixer(dt);
  } else if (motorTestActive) {
    if (millis() > motorTestDeadlineMs) {
      stopAllMotors();
    } else {
      for (int i = 0; i < 4; i++) {
        setMotorUs(i, (i == motorTestIdx) ? motorTestPwm : cfg.motorMinUs);
      }
    }
  } else {
    stopAllMotors();
  }

  bufferSerialBytes();
  if (rxLineReady) {
    handleJsonCommand(rxBuf);
    rxLineReady = false;
  }

  if (streamEnabled && rxPos == 0 && !rxLineReady && (millis() - lastTelemetryMs >= streamIntervalMs)) {
    lastTelemetryMs = millis();
    sendTelemetry();
    digitalWrite(PIN_STATUS_LED, !digitalRead(PIN_STATUS_LED));
  }
}
