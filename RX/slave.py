# slave.py (Приемник)
from machine import Pin, SPI, PWM
import time, struct
from sx1262mini import SX1262Mini

# Инициализация ШИМ-каналов (частота 50 Гц для аналоговых серво SG90)
esc = PWM(Pin('A0'), freq=50)
servo1 = PWM(Pin('A1'), freq=50)
servo2 = PWM(Pin('B0'), freq=50)
servo3 = PWM(Pin('B1'), freq=50)

pwms = (esc, servo1, servo2, servo3)

def set_pwm_from_normalized(pwm_channel, value):
    """
    Тайминги для сервоприводов SG90:
    0.0 -> 500 000 нс (0.5 мс) - Крайнее левое положение
    1.0 -> 2 400 000 нс (2.4 мс) - Крайнее правое положение
    """
    pulse_ns = int(500000 + (value * 1900000))
    pwm_channel.duty_ns(pulse_ns)
    return pulse_ns

spi = SPI(1, baudrate=8_000_000, polarity=0, phase=0)
lora = SX1262Mini(spi=spi, cs='A4', rst='A3', busy='A2', dio1='B9')
lora.init(868.0)

lora.start_rx()
print("Приемник ожидает пакеты данных LoRa...")

last_print = time.ticks_ms()

while True:
    packet = lora.recv()
    
    if packet is not None:
        if len(packet) == 16:
            data = struct.unpack('<4f', packet)
            
            # Применяем значения к ШИМ-выходам
            p0 = set_pwm_from_normalized(esc, data[0])
            p1 = set_pwm_from_normalized(servo1, data[1])
            p2 = set_pwm_from_normalized(servo2, data[2])
            p3 = set_pwm_from_normalized(servo3, data[3])
            
            # Вывод логов в консоль раз в 500 мс
            if time.ticks_diff(time.ticks_ms(), last_print) > 500:
                print(f"ПАКЕТ ПОЛУЧЕН! Норм: {[round(x, 2) for x in data]}")
                print(f" -> Наносекунды ШИМ: ESC={p0}, С1={p1}, С2={p2}, С3={p3}")
                last_print = time.ticks_ms()
        else:
            print(f" Предупреждение: получен пакет неверной длины ({len(packet)} байт)")
    
    # Минимальная защита CPU (в режиме быстрого опроса)
    time.sleep_us(100)

