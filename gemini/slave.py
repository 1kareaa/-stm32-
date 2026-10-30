# slave.py (Приемник)
from machine import Pin, SPI
import time, struct
from sx1262mini import SX1262Mini

# ── Периферия микроконтроллера ──
led = Pin('C13', Pin.OUT, value=0)

# ── Инициализация SPI и Радио ──
spi = SPI(1, baudrate=8_000_000, polarity=0, phase=0)
lora = SX1262Mini(spi=spi, cs='A4', rst='A3', busy='A2', dio1='B9')
lora.init(868.0)

# Переводим трансивер в режим постоянного приема
lora.start_rx()
print("Приемник запущен. Ожидание данных...")

# ── Основной цикл приема ──
while True:
    # Опрашиваем буфер библиотеки
    packet = lora.recv()
    
    if packet is not None:
        # Проверяем, что пришло именно 16 байт (4 float)
        if len(packet) == 16:
            # Индикация приема: мигаем светодиодом
            led.value(1)
            
            # Распаковываем бинарные данные back в float
            data = struct.unpack('<4f', packet)
            print(f"Принято каналов 4: {[round(val, 4) for val in data]}")
            
            time.sleep_ms(10)
            led.value(0)
        else:
            print(f"Получен пакет неверной длины: {len(packet)} байт")
            
    # Защита от перегрузки CPU холостым циклом
    time.sleep_ms(1)

