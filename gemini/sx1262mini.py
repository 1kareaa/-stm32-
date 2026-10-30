# sx1262mini.py
from machine import Pin
import time

class SX1262Mini:
    def __init__(self, spi, cs, rst, busy, dio1):
        self.spi = spi
        self.cs = Pin(cs, Pin.OUT, value=1)
        self.rst = Pin(rst, Pin.OUT, value=1)
        self.busy = Pin(busy, Pin.IN)
        self.dio1 = Pin(dio1, Pin.IN)
        self.irq_flag = False
        self.dio1.irq(trigger=Pin.IRQ_RISING, handler=self._irq_handler)

    def _irq_handler(self, pin):
        self.irq_flag = True

    def write_cmd(self, op, data=()):
        while self.busy.value(): 
            pass
        self.cs(0)
        self.spi.write(bytes((op,)) + bytes(data))
        self.cs(1)

    def read_cmd(self, op, num_bytes):
        while self.busy.value(): 
            pass
        self.cs(0)
        self.spi.write(bytes((op, 0x00))) # отправляем op + байт статуса
        res = self.spi.read(num_bytes)
        self.cs(1)
        return res

    def init(self, freq=868.0):
        # Аппаратный сброс чипа
        self.rst(0); time.sleep_ms(10); self.rst(1); time.sleep_ms(20)
        
        self.write_cmd(0x97, bytes((0x02,)) + (5000*64//1000).to_bytes(3,'big')) # TCXO 1.8V
        self.write_cmd(0x80, [0x00]) # STDBY_RC
        self.write_cmd(0x9D, [0x01]) # DIO2 контролирует RF-переключатель (TXEN/RXEN)
        self.write_cmd(0x96, [0x01]) # DC-DC регулятор
        self.write_cmd(0x8A, [0x01]) # Режим LoRa
        self.write_cmd(0x98, [0xD7, 0xDB]) # Калибровка частоты (863-870 МГц)
        self.write_cmd(0x86, int(freq*(1<<20)).to_bytes(4,'big')) # Установка частоты
        self.write_cmd(0x95, [0x04, 0x07, 0x00, 0x01]) # PA Config
        self.write_cmd(0x8E, [14, 0x04]) # Мощность 14 дБм
        self.write_cmd(0x8F, [0x00, 0x00]) # Базовые адреса Tx/Rx буферов = 0
        self.write_cmd(0x8B, [7, 0x04, 0x01, 0x00]) # Модуляция: SF7, BW125, CR4/5

    def send(self, pkt):
        self.write_cmd(0x80, [0x00]) # STDBY_RC
        self.write_cmd(0x8C, [0, 8, 0, len(pkt), 1, 0]) # Параметры пакета (Preamble, Explicit, Len, CRC)
        self.write_cmd(0x0E, [0x00] + list(pkt)) # Запись в Tx-буфер
        self.write_cmd(0x02, [0xFF, 0xFF]) # Очистка IRQ
        self.write_cmd(0x08, [0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]) # DIO1 на TxDone
        self.irq_flag = False
        self.write_cmd(0x83, [0x00, 0x00, 0x00]) # SetTx (таймаут 0 = одиночный)
        
        t0 = time.ticks_ms()
        while not self.irq_flag:
            if time.ticks_diff(time.ticks_ms(), t0) > 2000:
                self.write_cmd(0x02, [0xFF, 0xFF])
                return False
            time.sleep_ms(1)
        self.write_cmd(0x02, [0xFF, 0xFF])
        return True

    def start_rx(self):
        self.write_cmd(0x80, [0x00]) # STDBY_RC
        self.write_cmd(0x8C, [0, 8, 0, 255, 1, 0]) # Буфер на максимум (255) в режиме ожидания
        self.write_cmd(0x02, [0xFF, 0xFF]) # Очистка IRQ
        self.write_cmd(0x08, [0x00, 0x02, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00]) # DIO1 на RxDone
        self.irq_flag = False
        self.write_cmd(0x82, [0xFF, 0xFF, 0xFF]) # SetRx в режиме Continuous (постоянный прием)

    def recv(self):
        if not self.irq_flag:
            return None
        self.irq_flag = False
        
        # Получаем статус прерывания
        irq_status = self.read_cmd(0x12, 2)
        self.write_cmd(0x02, [0xFF, 0xFF]) # Очищаем прерывания на чипе
        
        # Проверяем бит RxDone (заводской флаг 0x02)
        if irq_status[1] & 0x02:
            # Читаем длину и смещение полученных данных
            rx_buffer_status = self.read_cmd(0x13, 2)
            pkt_len = rx_buffer_status[0]
            offset = rx_buffer_status[1]
            
            # Читаем данные из Rx-буфера трансивера
            while self.busy.value(): pass
            self.cs(0)
            self.spi.write(bytes((0x1E, offset, 0x00))) # Команда ReadBuffer + смещение + NOP
            packet = self.spi.read(pkt_len)
            self.cs(1)
            
            # Возвращаем трансивер в режим постоянного прослушивания эфира
            self.write_cmd(0x82, [0xFF, 0xFF, 0xFF])
            return packet
        
        # Перезапуск приемника при ошибках (CRC или таймаут)
        self.write_cmd(0x82, [0xFF, 0xFF, 0xFF])
        return None

