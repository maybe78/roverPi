import math

min_j = -1
max_j = 1
min_sp = -127
max_sp = 127


class Steering:
    @staticmethod
    def joystick_to_diff_control(x, y):
        left_speed = right_speed = 0
        if x != 0 and y != 0:
            z = math.sqrt(x*x + y*y)
            rad = math.acos(math.fabs(x) / z)
            angle = rad * 180 / math.pi
            # Now angle indicates the measure of turn
            tcoeff = -1 + (angle / 90) * 2
            turn = tcoeff * math.fabs(math.fabs(y) - math.fabs(x))
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
            right_speed = Steering.ard_map(raw_right, min_j, max_j, min_sp, max_sp)
            left_speed = Steering.ard_map(raw_left, min_j, max_j, min_sp, max_sp)
        return left_speed, right_speed

    @staticmethod
    def ard_map(x, in_min, in_max, out_min, out_max):
        return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)




