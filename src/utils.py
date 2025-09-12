# utils.py
import math

max_sp = 127

DEAD_ZONE = 10
# Минимальная скорость, чтобы робот начал двигаться (преодоление трения)
MIN_SPEED_THRESHOLD = 30
# Максимальная скорость при движении прямо (ограничиваем, чтобы не был слишком быстрым)
MAX_SPEED_STRAIGHT = 70
# Коэффициент чувствительности поворота. Больше -> поворачивает резче.
TURN_SENSITIVITY = 0.8
# Экспонента для нелинейного управления (1.0 - линейно, >1.0 - плавнее у центра)
CURVE_EXPONENT = 1.6

def apply_curve_and_deadzone(value, dead_zone, min_speed, max_speed, exponent):
    """Применяет мертвую зону, кривую и масштабирует скорость."""
    if abs(value) < dead_zone:
        return 0

    abs_val = abs(value)
    sign = 1 if value > 0 else -1

    # Нормализуем значение из [dead_zone, 127] в [0, 1]
    normalized = (abs_val - dead_zone) / (127 - dead_zone)
    
    # Применяем экспоненциальную кривую для плавности
    curved = math.pow(normalized, exponent)

    # Масштабируем результат в диапазон [min_speed, max_speed]
    output_range = max_speed - min_speed
    final_speed = min_speed + (curved * output_range)

    return int(final_speed * sign)

def joystick_to_diff_control(x, y, dead_zone):
    """
    Аркадное управление. 
    Ось Y - вперед/назад. 
    Ось X - лево/право.
    """
    
    # 1. Движение вперед/назад (Throttle) управляется осью Y.
    #    Инвертируем, т.к. стик "вверх" обычно дает отрицательное значение.
    forward_raw = -y

    # 2. Поворот (Turn) управляется осью X.
    #    Может понадобиться инверсия, если лево/право перепутаны.
    turn_raw = -x


    # Применяем кривую и пороги
    forward_speed = apply_curve_and_deadzone(forward_raw, dead_zone, MIN_SPEED_THRESHOLD, MAX_SPEED_STRAIGHT, CURVE_EXPONENT)
    turn_speed = apply_curve_and_deadzone(turn_raw, dead_zone, MIN_SPEED_THRESHOLD, 127, CURVE_EXPONENT)
    
    # Применяем чувствительность поворота
    turn_speed *= TURN_SENSITIVITY

    # Смешиваем скорости
    left_speed = forward_speed + turn_speed
    right_speed = forward_speed - turn_speed

    # Ограничиваем значения
    left_speed = max(-127, min(left_speed, 127))
    right_speed = max(-127, min(right_speed, 127))

    # Возвращаем скорости без инверсии правого мотора
    return int(left_speed), int(right_speed)
    
