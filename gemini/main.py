# main.py (Передатчик)
from machine import ADC, Pin, SPI
import time, struct
from sx1262mini import SX1262Mini

# ── Периферия микроконтроллера ──
adcs = tuple(ADC(Pin(p)) for p in ('A0', 'A1', 'B0', 'B1'))
led = Pin('C13', Pin.OUT)

# ── Инициализация SPI и Радио ──
spi = SPI(1, baudrate=8_000_000, polarity=0, phase=0)
lora = SX1262Mini(spi=spi, cs='A4', rst='A3', busy='A2', dio1='B9')
lora.init(868.0)

# Мигнем — радио готово
led.value(1); time.sleep_ms(50); led.value(0)

def read_pots():
    return [adc.read_u16() for adc in adcs]

def calibrate(sec=10):
    mins, maxs = [65535] * 4, [0] * 4
    t0 = time.time()
    while time.time() - t0 < sec:
        vals = read_pots()
        for i in range(4):
            if vals[i] < mins[i]: mins[i] = vals[i]
            if vals[i] > maxs[i]: maxs[i] = vals[i]
        time.sleep(0.02)
    return mins, maxs

def norm(v, lo, hi):
    return (v - lo) / (hi - lo) if hi > lo else 0.0

# ── Калибровка потенциометров ──
print("Старт калибровки (10 сек)...")
mins, maxs = calibrate(10)
led.value(1) # Постоянный свет LED — калибровка закончена

for i in range(4):
    print(f"Канал {i}: min={mins[i]}, max={maxs[i]}")

# ── Основной цикл передачи ──
while True:
    vals = read_pots()
    norms = [norm(vals[i], mins[i], maxs[i]) for i in range(4)]
    
    # Упаковка 4 float (16 байт)
    pkt = struct.pack('<4f', *norms)
    
    # Отправка через библиотеку
    ok = lora.send(pkt)
    
    print(f"Отправлено: {[round(n, 3) for n in norms]} -> {'OK' if ok else 'FAIL'}")
    time.sleep(0.2)

