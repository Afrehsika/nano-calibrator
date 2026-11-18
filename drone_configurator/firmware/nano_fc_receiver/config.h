#pragma once

// ============================================================================
// Confirmed Hardware Configuration: Classic Arduino Nano (ATmega328P, 5V/16MHz)
// Frame: Quad-X | ESCs: Standard PWM (1000 - 2000 us)
// ============================================================================

#define FC_DEVICE_NAME     "NanoFC-QuadX"
#define FC_MCU_NAME        "ATmega328P"
#define FC_FW_VERSION      "1.0.0"
#define FC_PROTOCOL_VER    "1.0"
#define FC_LAYOUT_NAME     "Quad-X"

#define SERIAL_BAUD        115200

// Quad-X Motor PWM Pins (Standard Servo/ESC PWM)
#define PIN_MOTOR_1        3   // Front-Left  (CW)
#define PIN_MOTOR_2        5   // Front-Right (CCW)
#define PIN_MOTOR_3        6   // Rear-Right  (CW)
#define PIN_MOTOR_4        9   // Rear-Left   (CCW)

// nRF24L01 SPI Pins (MOSI=11, MISO=12, SCK=13 are hardware SPI)
#define PIN_NRF_CE         7
#define PIN_NRF_CSN        8

// MPU6050 I2C Pins: SDA = A4, SCL = A5
#define MPU6050_ADDR       0x68

// Status LED (Avoid D13 since it is SPI SCK for nRF24L01)
#define PIN_STATUS_LED     4

// Optional Battery Voltage Divider on A0 (uncomment if resistor divider is wired)
// #define ENABLE_VBAT_MONITOR
#define PIN_VBAT           A0
#define VBAT_SCALE         0.01465f  // Adjust for your resistor divider

// nRF24L01 RF24 library (uncommented to match your TX Nano)
#define ENABLE_NRF24

// Safety Limits
#define MOTOR_HARD_MIN_US  1000
#define MOTOR_HARD_MAX_US  2000
#define MOTOR_TEST_CAP_US  1250
#define MOTOR_TEST_WD_MS   2500      // Auto-stop motor test after 2.5s without refresh

#define EEPROM_MAGIC       0x4E46    // 'NF'

