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
