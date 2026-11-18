# NanoFC Quad-X Flight Controller Configurator

Professional Windows desktop application (PySide6 + PySerial + PyQtGraph + NumPy) and matching Arduino Nano (ATmega328P) firmware for configuring, monitoring, calibrating, and safely testing a custom quadcopter flight controller.

## Hardware Architecture
- **MCU**: Classic Arduino Nano (ATmega328P, 5V, 16 MHz)
- **Frame & ESCs**: Quad-X layout, Standard PWM (1000–2000 µs)
  - Motor 1 (Front-Left, CW): `D3`
  - Motor 2 (Front-Right, CCW): `D5`
  - Motor 3 (Rear-Right, CW): `D6`
  - Motor 4 (Rear-Left, CCW): `D9`
- **IMU**: MPU6050 on I2C (`A4` SDA, `A5` SCL)
- **Radio**: nRF24L01 on SPI (`D11` MOSI, `D12` MISO, `D13` SCK, `D7` CE, `D8` CSN)
- **Status LED**: `D4`
- **Optional Battery Voltage**: `A0` (enable `#define ENABLE_VBAT_MONITOR` in `firmware/nano_fc_receiver/config.h`)

## Running the Desktop Application

```powershell
.\.venv\Scripts\python.exe .\drone_configurator\main.py
```

You can test every feature immediately without hardware by selecting **`SIMULATOR (Virtual Nano FC)`** in the Dashboard port dropdown.

## Running Unit Tests

```powershell
.\.venv\Scripts\python.exe -m pytest .\drone_configurator\tests
```

## Flashing the Arduino Nano Firmware
1. Open `drone_configurator/firmware/nano_fc_receiver/nano_fc_receiver.ino` in the Arduino IDE.
2. Install **ArduinoJson** (and **RF24** if enabling `ENABLE_NRF24` in `config.h`).
3. Select **Board: Arduino Nano** and **Processor: ATmega328P** (or Old Bootloader if applicable).
4. Upload at `115200` baud.

