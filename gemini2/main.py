# main.py (Передатчик)
from machine import ADC, Pin, SPI
import time, struct
from sx1262mini import SX1262Mini

adcs = tuple(ADC(Pin(p)) for p in ('A0', 'A1', 'B0', 'B1'))
led = Pin('C13', Pin.OUT, value=0)

spi = SPI(1, baudrate=8_000_000, polarity=0, phase=0)
lora = SX1262Mini(spi=spi, cs='A4', rst='A3', busy='A2', dio1='B9')
lora.init(868.0)

CH_BOUNDS = (
    (25800, 40500),  # Канал 0 (ESC)
    (27800, 44200),  # Канал 1 (Серво 1)
    (15800, 58300),  # Канал 2 (Серво 2)
    (10000, 59000)   # Канал 3 (Серво 3)
)

def read_and_normalize():
    norms = []
    raws = []
    for i in range(4):
        raw = adcs[i].read_u16()
        raws.append(raw)
        lo, hi = CH_BOUNDS[i]
        val = (raw - lo) / (hi - lo) if hi > lo else 0.0
        
        # Жесткое ограничение рамок [0.0, 1.0]
        if val < 0.0: val = 0.0
        elif val > 1.0: val = 1.0
        norms.append(val)
    return norms, raws

led.value(1); time.sleep_ms(100); led.value(0)
print("Передатчик запущен в Low-Latency режиме...")

last_print = time.ticks_ms()

while True:
    norms, raws = read_and_normalize()
    pkt = struct.pack('<4f', *norms)
    ok = lora.send(pkt)
    
    # Выводим инфо раз в 500 мс, чтобы видеть статус работы потенциометров
    if time.ticks_diff(time.ticks_ms(), last_print) > 500:
        print(f"Сырые АЦП: {raws} | Отправка: {[round(n,2) for n in norms]} -> {'OK' if ok else 'FAIL'}")
        last_print = time.ticks_ms()

