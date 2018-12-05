import math

max_sp = 127


class Steering:
    def __init__(self):
        pass

    @staticmethod
    def joystick_to_diff_control(x, y):
        left_speed = right_speed = 0
        if x != 0 and y != 0:
            z = math.sqrt(x*x + y*y)
            rad = math.acos(math.fabs(x) / z)
            angle = rad * 180 / math.pi
            # Now angle indicates the measure of turn
            t_coefficient = -1 + (angle / 90) * 2
            turn = t_coefficient * math.fabs(math.fabs(y) - math.fabs(x))
            turn = round(turn * 100, 0) / 100
            # And max of y or x is the movement
            mov = max(math.fabs(y), math.fabs(x))
            # First and third quadrant
            if (x >= 0 and y >= 0) or (x < 0 and y < 0):
                raw_left = mov
                raw_right = turn
            else:
                raw_right = mov
                raw_left = turn
            # Reverse polarity
            if y < 0:
                raw_left = 0 - raw_left
                raw_right = 0 - raw_right
            # keep in range
            left_speed = int(max(min(raw_left, max_sp), max_sp * -1))
            right_speed = int(max(min(raw_right, max_sp), -max_sp * -1))
        return left_speed, right_speed



