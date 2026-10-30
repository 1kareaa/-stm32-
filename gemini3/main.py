from machine import ADC, Pin, SPI
import time
from sx1262mini import SX1262Mini

# Настройка АЦП и радио
adcs = tuple(ADC(Pin(p)) for p in ('A0', 'A1', 'B0', 'B1'))
spi = SPI(1, baudrate=8_000_000, polarity=0, phase=0)
lora = SX1262Mini(spi=spi, cs='A4', rst='A3', busy='A2', dio1='B9')

# === ТУТ НАСТРАИВАЕМ ПАРАМЕТРЫ ОДНОЙ СТРОЧКОЙ ===
# На демо можно менять: sf (5-12), bw_khz (125.0, 250.0, 500.0), power_dbm (-9...22)
lora.init(freq=868.0, sf=5, bw_khz=500.0, power_dbm=14)

# Границы АЦП для калибровки
BOUNDS = ((25800, 40500), (27800, 44200), (15800, 58300), (10000, 59000))

print("Передатчик готов...")

while True:
    bytes_list = []
    for i in range(4):
        raw = adcs[i].read_u16()
        lo, hi = BOUNDS[i]
        val = (raw - lo) / (hi - lo) if hi > lo else 0.0
        val = max(0.0, min(1.0, val))
        bytes_list.append(int(val * 255))
    
    # Отправляем 4 байта в эфир
    lora.send(bytes(bytes_list))
    time.sleep_ms(10)

