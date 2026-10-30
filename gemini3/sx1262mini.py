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
        self.current_pkt_len = 4  # Длина пакета по умолчанию (для авто-перезапуска RX)
        self.dio1.irq(trigger=Pin.IRQ_RISING, handler=self._irq_handler)

    def _irq_handler(self, pin):
        self.irq_flag = True

    def write_cmd(self, op, data=()):
        while self.busy.value(): pass
        self.cs(0)
        self.spi.write(bytes((op,)) + bytes(data))
        self.cs(1)

    def read_cmd(self, op, num_bytes):
        while self.busy.value(): pass
        self.cs(0)
        self.spi.write(bytes((op, 0x00)))
        res = self.spi.read(num_bytes)
        self.cs(1)
        return res

    def init(self, freq=868.0, sf=5, bw_khz=500.0, power_dbm=14):
        """Полная инициализация чипа с человеческими параметрами"""
        # Аппаратный сброс чипа
        self.rst(0); time.sleep_ms(10); self.rst(1); time.sleep_ms(20)
        
        self.write_cmd(0x97, bytes((0x02,)) + (5000*64//1000).to_bytes(3,'big')) # TCXO 1.8V
        self.write_cmd(0x80, [0x00]) # STDBY_RC
        self.write_cmd(0x9D, [0x01]) # DIO2 контролирует RF-переключатель
        self.write_cmd(0x96, [0x01]) # DC-DC регулятор
        self.write_cmd(0x8A, [0x01]) # Режим LoRa
        self.write_cmd(0x98, [0xD7, 0xDB]) # Калибровка частоты
        self.write_cmd(0x95, [0x04, 0x07, 0x00, 0x01]) # PA Config
        self.write_cmd(0x8F, [0x00, 0x00]) # Базовые адреса Tx/Rx буферов = 0
        
        # Применяем стартовые настройки радиоэфира через удобные методы
        self.set_frequency(freq)
        self.set_tx_power(power_dbm)
        self.set_lora_modem(sf, bw_khz)

    # --- МЕТОДЫ УПРАВЛЕНИЯ ПАРАМЕТРАМИ НА ЛЕТУ ---

    def set_frequency(self, mhz):
        """Изменение частоты на лету (например, 868.0 или 915.0)"""
        factor = int(mhz * (1 << 20))
        self.write_cmd(0x86, factor.to_bytes(4, 'big'))

    def set_tx_power(self, dbm):
        """Изменение мощности передатчика на лету (от -9 до +22 дБм)"""
        dbm = max(-9, min(22, dbm))
        self.write_cmd(0x8E, [dbm, 0x04])

    def set_lora_modem(self, sf, bw_khz):
        """
        Изменение скорости на лету. 
        sf (Spreading Factor): от 5 до 12 (меньше = быстрее, больше = дальше)
        bw_khz (Bandwidth): 125.0, 250.0 или 500.0 (больше = быстрее)
        """
        # Перевод килогерц в регистровые значения SX1262
        bw_map = {125.0: 0x04, 250.0: 0x05, 500.0: 0x06}
        bw_val = bw_map.get(bw_khz, 0x06) # По умолчанию 500кГц, если передано не то
        
        # Запись параметров модуляции (SF, BW, CR=4/5, LowDataRateOptimize=0)
        self.write_cmd(0x8B, [sf, bw_val, 0x01, 0x00])

    # --- МЕТОДЫ ПРИЕМА И ПЕРЕДАЧИ ---

    def send(self, pkt):
        """Отправка пакета любой длины (длина вычисляется автоматически)"""
        self.write_cmd(0x80, [0x00])
        # Конфигурируем размер под конкретный пакет (Implicit Header)
        self.write_cmd(0x8C, [0, 8, 1, len(pkt), 1, 0])
        self.write_cmd(0x0E, [0x00] + list(pkt))
        self.write_cmd(0x02, [0xFF, 0xFF])
        self.write_cmd(0x08, [0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00])
        self.irq_flag = False
        self.write_cmd(0x83, [0x00, 0x00, 0x00])
        
        t0 = time.ticks_ms()
        while not self.irq_flag:
            if time.ticks_diff(time.ticks_ms(), t0) > 100:
                self.write_cmd(0x02, [0xFF, 0xFF])
                return False
        self.write_cmd(0x02, [0xFF, 0xFF])
        return True

    def start_rx(self, pkt_len=4):
        """Включение режима постоянного приема с указанной длиной пакета"""
        self.current_pkt_len = pkt_len # Запоминаем для авто-продления RX
        self.write_cmd(0x80, [0x00])
        self.write_cmd(0x8C, [0, 8, 1, pkt_len, 1, 0]) 
        self.write_cmd(0x02, [0xFF, 0xFF])
        self.write_cmd(0x08, [0x00, 0x02, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00])
        self.irq_flag = False
        self.write_cmd(0x82, [0xFF, 0xFF, 0xFF])

    def recv(self):
        """Опрос буфера приема. Возвращает bytes или None"""
        if not self.irq_flag:
            return None
        self.irq_flag = False
        
        irq_status = self.read_cmd(0x12, 2)
        self.write_cmd(0x02, [0xFF, 0xFF])
        
        if irq_status[1] & 0x02:
            rx_buffer_status = self.read_cmd(0x13, 2)
            pkt_len = rx_buffer_status[0]
            offset = rx_buffer_status[1]
            
            while self.busy.value(): pass
            self.cs(0)
            self.spi.write(bytes((0x1E, offset, 0x00)))
            packet = self.spi.read(pkt_len)
            self.cs(1)
            
            # Перезапускаем RX с сохраненными настройками длины
            self.start_rx(self.current_pkt_len)
            return packet
        
        self.start_rx(self.current_pkt_len)
        return None

