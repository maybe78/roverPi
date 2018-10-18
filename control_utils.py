import math

class Steering:
    def joystick_to_diff_control(self, x, y, minJoystick, maxJoystick, minSpeed, maxSpeed):
        if x == 0 and y == 0:
            return (0, 0)
        # First Compute the angle in deg & in radians
        z = math.sqrt(x * x + y * y)
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
            rawLeft = mov
            rawRight = turn
        else:
            rawRight = mov
            rawLeft = turn
        # Reverse polarity
        if y < 0:
            rawLeft = 0 - rawLeft
            rawRight = 0 - rawRight
        # keep in range
        rightSpeed = self.ardmap(rawRight, minJoystick, maxJoystick, minSpeed, maxSpeed)
        leftSpeed = self.ardmap(rawLeft, minJoystick, maxJoystick, minSpeed, maxSpeed)
        return (rightSpeed, leftSpeed)

    def ardmap(x, in_min, in_max, out_min, out_max):
        return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)