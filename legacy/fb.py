import mmap
import numpy as np

fb = open('/dev/fb0', 'r+b')
screen_size = 320*240*2  # для 320x240, 16-бит цвет
fbmmap = mmap.mmap(fb.fileno(), screen_size)

frame = np.zeros((240, 320), dtype=np.uint16)
# Пример: красный цвет RGB565
RED = 0xF800
frame[120, 160] = RED

fbmmap.seek(0)
fbmmap.write(frame.tobytes())
fbmmap.close()
fb.close()
