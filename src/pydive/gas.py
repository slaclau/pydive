import abc
import itertools

from anyio import sleep_until
from black.brackets import max_delimiter_priority_in_atom


class Gas(abc.ABC):
    name: str
    formula: str

    virial_coefficients: list[float]

    @staticmethod
    def get_gas_type(gas):
        if isinstance(gas, type(Gas)):
            gas_type = gas
        else:
            if gas not in gas_name_map():
                raise ValueError(f"unknown gas {gas}")
            gas_type = gas_name_map()[gas]
        return gas_type

    @classmethod
    def virial_m1(cls, pressure):
        return sum(
            [
                cls.virial_coefficients[i] * pressure ** (i + 1)
                for i in range(0, len(cls.virial_coefficients))
            ]
        )


class Oxygen(Gas):
    name = "oxygen"
    formula = "O2"

    virial_coefficients = [-7.18092073703e-04, +2.81852572808e-06, -1.50290620492e-09]


class Nitrogen(Gas):
    name = "nitrogen"
    formula = "N2"

    virial_coefficients = [-2.19260353292e-04, +2.92844845532e-06, -2.07613482075e-09]


class Helium(Gas):
    name = "helium"
    formula = "He"

    virial_coefficients = [+4.87320026468e-04, -8.83632921053e-08, +5.33304543646e-11]


_gas_name_map: dict[str, type(Gas)] = {}


def gas_name_map():
    global _gas_name_map
    if _gas_name_map == {}:
        _gas_name_map = {G.name: G for G in Gas.__subclasses__()}
    return _gas_name_map


class GasBlend:
    max_pO2 = 1.6
    min_pO2 = 0.16

    max_pNarc = 4.0

    def __init__(self, **kwargs):
        self.blend: dict[type(Gas), float] = {}
        self.set_blend(**kwargs)

    def set_blend(self, **kwargs):
        total_fraction = sum(kwargs.values())
        if not abs(total_fraction - 1) < 0.01:
            raise ValueError(
                f"Gas fractions should sum to 1 but instead sum to {total_fraction}"
            )
        for gas, fraction in kwargs.items():
            if gas not in gas_name_map():
                raise ValueError(f"unknown gas {gas}")
            if fraction > 0:
                self.blend[gas_name_map()[gas]] = fraction / total_fraction

    def __str__(self):
        rtn = "Gas blend"
        for gas in gas_name_map().values():
            if gas in self.blend:
                rtn += f"\n  {gas.name}: {self.blend[gas]:.0%}"
        return rtn

    @property
    def is_nitrox(self):
        for gas in self.blend:
            if gas != Oxygen and gas != Nitrogen:
                return False
        return True

    @property
    def is_trimix(self):
        for gas in self.blend:
            if gas != Oxygen and gas != Nitrogen and gas != Helium:
                return False
        return True

    def __repr__(self):
        if len(self.blend) == 1:
            return list(self.blend.keys())[0].name.title()
        if self.blend == air.blend or (
            self.fraction(Oxygen) == 0.21 and self.fraction(Nitrogen) == 0.79
        ):
            return "air"
        if self.is_nitrox:
            return f"EAN{100 * self.fraction(Oxygen):.0f}"
        elif self.is_trimix:
            return (
                f"Tx{100 * self.fraction(Oxygen):.0f}/{100 * self.fraction(Helium):.0f}"
            )
        else:
            raise ValueError("Unknown blend type\n" + self.__str__())

    def fraction(self, gas):
        gas_type = Gas.get_gas_type(gas)
        if gas_type not in self.blend:
            return 0
        return self.blend[gas_type]

    @property
    def max_operating_depth(self):
        return self.max_operating_depth_at(self.max_pO2)

    def max_operating_depth_at(self, max_pO2):
        return 10 * (max_pO2 / self.fraction(Oxygen) - 1)

    @property
    def min_operating_depth(self):
        return self.min_operating_depth_at(self.min_pO2)

    def min_operating_depth_at(self, min_pO2):
        value = 10 * (min_pO2 / self.fraction(Oxygen) - 1)
        if value < 0:
            return 0
        return value

    @property
    def max_narcotic_depth(self):
        return self.max_narcotic_depth_at(self.max_pNarc)

    def max_narcotic_depth_at(self, max_pNarc):
        return 10 * (max_pNarc / (self.fraction(Oxygen) + self.fraction(Nitrogen)) - 1)

    def partial_pressure(self, gas, depth):
        return (depth / 10 + 1) * self.fraction(gas)

    def compressibility(self, pressure):
        rtn = 1 + sum(
            [self.fraction(gas) * gas.virial_m1(pressure) for gas in self.blend]
        )
        return rtn

    @property
    def virial_coefficients(self):
        coefficients = [
            [
                self.fraction(gas) * coefficient
                for coefficient in gas.virial_coefficients
            ]
            for gas in self.blend
        ]

        return [sum(gas) for gas in itertools.zip_longest(*coefficients, fillvalue=0)]


air = GasBlend(oxygen=0.2098, nitrogen=0.7902)

if __name__ == "__main__":
    O2 = GasBlend(oxygen=1)
    air = GasBlend(oxygen=0.21, nitrogen=0.79)
    trimix_10_70 = GasBlend(oxygen=0.1, helium=0.7, nitrogen=0.2)
    print(O2)
    print(air)

    print(trimix_10_70.partial_pressure(Oxygen, 100))
