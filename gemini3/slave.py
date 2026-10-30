from machine import Pin, SPI, PWM
import time
from sx1262mini import SX1262Mini

# Настройка ШИМ (сервоприводы и ESC)
pwms = tuple(PWM(Pin(p), freq=50) for p in ('A8', 'A9', 'A10', 'A11'))

# Настройка радио
spi = SPI(1, baudrate=8_000_000, polarity=0, phase=0)
lora = SX1262Mini(spi=spi, cs='A4', rst='A3', busy='A2', dio1='A1')

# === НАСТРОЙКА ДОЛЖНА СОВПАДАТЬ С ПЕРЕДАТЧИКОМ ===
lora.init(freq=868.0, sf=5, bw_khz=500.0)

# Запуск постоянного приема 4-байтовых пакетов
lora.start_rx(pkt_len=4)
print("Приемник ожидает данные...")

while True:
    packet = lora.recv()
    
    if packet and len(packet) == 4:
        # Распаковываем и сразу выводим в ШИМ (шаг 0-255 переводим в наносекунды)
        for i in range(4):
            ns = int(500000 + (packet[i] / 255) * 1900000)
            pwms[i].duty_ns(ns)
            
    time.sleep_us(100)

