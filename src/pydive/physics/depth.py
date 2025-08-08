class Depth(float):
    def to_pressure(self, surface_pressure=1):
        return self / 10 + surface_pressure
