import cv2
import numpy as np
import os

# Набор ASCII‑символов — от тёмных к светлым
ASCII_CHARS = "@%#*+=-:. "

def frame_to_ascii(frame, width=100):
    # Конвертация кадра в оттенки серого
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    height, orig_width = gray.shape

    # Пропорциональное изменение размера
    aspect_ratio = height / orig_width
    new_height = int(aspect_ratio * width * 0.55)  # корректировка высоты
    resized = cv2.resize(gray, (width, new_height))

    # Конвертация каждого пикселя в символ
    ascii_str = ""
    for row in resized:
        for pixel in row:
            ascii_str += ASCII_CHARS[min(len(ASCII_CHARS) - 1, int(pixel) * len(ASCII_CHARS) // 256)]

        ascii_str += "\n"
    return ascii_str

def main():
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Ошибка: не удалось открыть камеру")
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            ascii_art = frame_to_ascii(frame)
            os.system("cls" if os.name == "nt" else "clear")
            print(ascii_art)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()

if __name__ == "__main__":
    main()
