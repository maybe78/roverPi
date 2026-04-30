import ydlidar
import numpy as np
import mmap
import time
import signal
import sys

# Размер экрана и fb устройство
WIDTH = 480
HEIGHT = 320
FB_DEVICE = '/dev/fb0'
RMAX = 10.0  # Максимальное расстояние для отображения (метры)

# Цвета в RGB565
BLACK = 0x0000
RED = 0xF800
GREEN = 0x07E0
BLUE = 0x001F
YELLOW = 0xFFE0

# Глобальные переменные для cleanup
laser = None
fbmmap = None
fb = None

def signal_handler(sig, frame):
    """Обработчик сигнала для корректного завершения"""
    print("\nReceived interrupt signal, cleaning up...")
    cleanup()
    sys.exit(0)

def cleanup():
    """Очистка ресурсов"""
    global laser, fbmmap, fb
    try:
        if laser is not None:
            laser.turnOff()
            laser.disconnecting()
            print("Lidar turned off")
    except Exception as e:
        print(f"Error turning off lidar: {e}")

    try:
        if fbmmap is not None:
            fbmmap.close()
        if fb is not None:
            fb.close()
        print("Framebuffer closed")
    except Exception as e:
        print(f"Error closing framebuffer: {e}")

def intensity_to_color(intensity):
    """Преобразование интенсивности в цвет RGB565"""
    # Нормализуем интенсивность (обычно 0-255)
    norm = min(255, max(0, intensity)) / 255.0

    # Создаём градиент от синего через зелёный к красному
    if norm < 0.5:
        # Синий -> Зелёный
        r = 0
        g = int(norm * 2 * 63)
        b = int((1 - norm * 2) * 31)
    else:
        # Зелёный -> Красный
        r = int((norm - 0.5) * 2 * 31)
        g = int((1 - (norm - 0.5) * 2) * 63)
        b = 0

    # Упаковываем в RGB565
    return (r << 11) | (g << 5) | b

def draw_lidar_points(frame, points, center_x, center_y):
    frame.fill(BLACK)
    scale = min(center_x, center_y) / RMAX

    # Рисуем сетку
    for dist in [2, 4, 6, 8]:
        if dist <= RMAX:
            radius = int(dist * scale)
            draw_circle_outline(frame, center_x, center_y, radius, BLUE)

    # Центр
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            if dx*dx + dy*dy <= 9:
                if 0 <= center_x+dx < WIDTH and 0 <= center_y+dy < HEIGHT:
                    frame[center_y+dy, center_x+dx] = GREEN

    valid_points = 0

    for point in points:
        angle_rad = point.angle
        dist = point.range  # БЕЗ деления на 1000 - ПОПРОБУЙТЕ ЭТО!

        # Отладка
        if valid_points < 10:
            print(f"Angle: {np.degrees(angle_rad):.1f}°, Dist: {dist:.3f}m")

        # Убираем строгий фильтр
        if dist > 0 and dist <= RMAX:
            x = int(center_x + dist * scale * np.sin(angle_rad))
            y = int(center_y - dist * scale * np.cos(angle_rad))

            if valid_points < 10:
                print(f"  -> ({x}, {y})")

            point_radius = 1  # было 3, теперь 1 пиксель радиус

            for dy in range(-point_radius, point_radius+1):
                for dx in range(-point_radius, point_radius+1):
                    px = x + dx
                    py = y + dy
                    if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                        frame[py, px] = RED

            valid_points += 1

    print(f"Valid points: {valid_points}/{len(points)}\n")


def draw_circle_outline(frame, cx, cy, radius, color):
    """Рисуем окружность (вспомогательная сетка)"""
    points = 120  # Количество точек для аппроксимации окружности
    for i in range(points):
        angle = 2 * np.pi * i / points
        x = int(cx + radius * np.cos(angle))
        y = int(cy + radius * np.sin(angle))
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            frame[y, x] = color

def main():
    global laser, fbmmap, fb

    # Установка обработчика сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Инициализация лидара (ваши настройки)
    laser = ydlidar.CYdLidar()
    laser.setlidaropt(ydlidar.LidarPropSerialPort, "/dev/ttyUSB0")
    laser.setlidaropt(ydlidar.LidarPropSerialBaudrate, 128000)
    laser.setlidaropt(ydlidar.LidarPropLidarType, ydlidar.TYPE_TRIANGLE)
    laser.setlidaropt(ydlidar.LidarPropDeviceType, ydlidar.YDLIDAR_TYPE_SERIAL)
    laser.setlidaropt(ydlidar.LidarPropScanFrequency, 6.0)
    laser.setlidaropt(ydlidar.LidarPropSampleRate, 9)
    laser.setlidaropt(ydlidar.LidarPropSingleChannel, True)

    # Инициализация и запуск лидара
    ret = laser.initialize()
    if not ret:
        print("Failed to initialize lidar")
        return

    ret = laser.turnOn()
    if not ret:
        print("Failed to start lidar")
        cleanup()
        return

    print("Lidar started successfully")

    # Открытие framebuffer
    fb = open(FB_DEVICE, 'r+b')
    fbmmap = mmap.mmap(fb.fileno(), WIDTH*HEIGHT*2)
    frame = np.zeros((HEIGHT, WIDTH), dtype=np.uint16)

    center_x = WIDTH // 2
    center_y = HEIGHT // 2

    # Создаём объект scan один раз (как в их примере)
    scan = ydlidar.LaserScan()

    frame_count = 0
    start_time = time.time()

    try:
        while True:
            # Получаем данные лидара (как в их animate функции)
            r = laser.doProcessSimple(scan)

            if r and len(scan.points) > 0:
                # Отрисовка точек
                draw_lidar_points(frame, scan.points, center_x, center_y)

                # Запись в framebuffer
                fbmmap.seek(0)
                fbmmap.write(frame.tobytes())

                frame_count += 1

                # Вывод статистики каждые 2 секунды
                if frame_count % 40 == 0:
                    elapsed = time.time() - start_time
                    fps = frame_count / elapsed
                    print(f"Points: {len(scan.points)}, FPS: {fps:.1f}")

            time.sleep(0.03)  # ~30 fps

    except KeyboardInterrupt:
        print("\nKeyboard interrupt received")
    finally:
        cleanup()

if __name__ == "__main__":
    main()
