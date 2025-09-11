import math

max_sp = 127


def joystick_to_diff_control(x, y, dead_zone):
	x = float(x / max_sp)
	y = float(y / max_sp)
	# convert to polar
	r = math.hypot(x, y)
	t = math.atan2(y, x)

	# rotate by 45 degrees
	t += math.pi / 4

	# back to cartesian
	left = r * math.cos(t)
	right = r * math.sin(t)

	# rescale to new coordinates
	left = left * math.sqrt(2)
	right = right * math.sqrt(2)

	# clamp t abs(1)
	left = int(left*127)
	right = int(right*127)
	left = max(-127, min(left, 127))
	right = max(-127, min(right, 127))
	if abs(left) < dead_zone:
		left = 0
	if abs(right) < dead_zone:
		right = 0
	return -left, right

def map_to_motor_speed(joystick_value, dead_zone, min_motor_speed, curve_exponent=2.0):
    """
    Преобразует линейное значение с джойстика в нелинейную скорость мотора.

    :param joystick_value: Входное значение от -127 до 127.
    :param dead_zone: Мертвая зона джойстика (значения ниже игнорируются).
    :param min_motor_speed: Минимальная скорость, с которой мотор начинает уверенно вращаться.
    :param curve_exponent: Коэффициент кривизны (e.g., 1.5 - мягче, 2.0 - квадратичная, 3.0 - кубическая).
    :return: Нелинейное значение скорости для мотора.
    """
    if abs(joystick_value) < dead_zone:
        return 0

    abs_val = abs(joystick_value)
    sign = 1 if joystick_value > 0 else -1

    # 1. Нормализуем входное значение из диапазона [dead_zone, 127] в [0, 1]
    normalized_input = (abs_val - dead_zone) / (127.0 - dead_zone)
    if normalized_input > 1.0: normalized_input = 1.0

    # 2. Применяем степенную кривую
    curved_input = math.pow(normalized_input, curve_exponent)

    # 3. Масштабируем результат в выходной диапазон [min_motor_speed, 127]
    output_range = 127 - min_motor_speed
    mapped_speed = min_motor_speed + (curved_input * output_range)

    return int(mapped_speed * sign)
	
def joystick_to_ptz(x, y, dead_zone):
	cmd = ''
	if x < dead_zone * -1:
		cmd = 'l'
	elif x > dead_zone:
		cmd = 'r'
	# reverse updown due to dualshock analog stick value reverse
	if y < dead_zone * -1:
		cmd += 'u'
	elif y > dead_zone:
		cmd += 'd'
	return cmd
