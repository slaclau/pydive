import logging

import numpy as np

from pydive.gas import GasBlend, air
from pydive.models.base import Model

logger = logging.getLogger(__name__)


class GasConsumptionModel(Model):
    name = "Gas consumption"

    consumption: dict[GasBlend, float]

    models: dict[GasBlend, "SingleGasConsumptionModel"]

    def __init__(self, dive):
        super().__init__(dive)
        self.consumption = {}
        self.models = {}

    def apply_dive_step(self, step):
        if step.gas not in self.models:
            self.models[step.gas] = SingleGasConsumptionModel(step.gas)

        for gas in self.models:
            self.models[gas].apply_dive_step(step)
            self.consumption[gas] = self.models[gas].consumption

    def undo_last_step(self):
        for gas in self.models:
            self.models[gas].undo_last_step()
            self.consumption[gas] = self.models[gas].consumption

    def __str__(self):
        rtn = []
        for gas in self.consumption:
            rtn.append(f"{self.consumption[gas]:.0f} l of {gas.__repr__()}")

        return ", ".join(rtn)


class SingleGasConsumptionModel:
    gas: GasBlend
    history: list[float]
    consumption: float = 0

    sac = 20  # surface l/min

    def __init__(self, gas):
        self.gas = gas
        self.history = []

    def apply_dive_step(self, step):
        if step.gas != self.gas:
            self.history.append(self.consumption)
            return

        gas = self.gas

        depth = (step.start_depth + step.depth_change) / 2
        pressure = depth / 10 + 1
        Z = gas.compressibility(pressure)
        Z1 = gas.compressibility(1)

        consumption = self.sac * step.minutes * Z / Z1 * pressure

        self.consumption += consumption
        self.history.append(self.consumption)

    def undo_last_step(self):
        if self.history:
            self.history.pop(-1)
        self.consumption = self.history[-1] if self.history else 0


class Cylinder:
    gas: GasBlend
    volume: float
    pressure: float

    @property
    def surface_volume(self):
        return (
            self.pressure
            * self.volume
            * self.gas.compressibility(1)
            / self.gas.compressibility(self.pressure)
        )

    def __init__(self, gas, volume, pressure=1):
        self.gas = gas
        self.volume = volume
        self.pressure = pressure

    def add_gas(self, surface_volume):
        surface_volume = self.surface_volume + surface_volume

        virial_coefficients = self.gas.virial_coefficients

        coefficients = [
            1,
            virial_coefficients[0]
            - self.volume * self.gas.compressibility(1) / surface_volume,
        ] + virial_coefficients[1:]

        poly = np.polynomial.Polynomial(coefficients)

        roots = poly.roots()
        real_roots = roots[np.isreal(roots)]
        if len(real_roots) != 1:
            raise Exception
        self.pressure = real_roots[0].real

    def add_other_gas(self, blend, surface_volume):
        gas_volumes = {
            gas: self.surface_volume * self.gas.fraction(gas) for gas in self.gas.blend
        }

        for gas in blend.blend:
            if gas in self.gas.blend:
                gas_volumes[gas] += surface_volume * blend.fraction(gas)
            else:
                gas_volumes[gas] = surface_volume * blend.fraction(gas)

        total_volume = sum(gas_volumes.values())
        gas_fractions = {
            gas.name: round(volume / total_volume, 3)
            for gas, volume in gas_volumes.items()
        }
        new_gas = GasBlend(**gas_fractions)

        self.gas = new_gas
        self.pressure = 0
        self.add_gas(total_volume)

    def consume_gas(self, surface_volume):
        self.add_gas(-surface_volume)

    def volume_of(self, gas):
        return self.surface_volume * self.gas.fraction(gas)

    def __repr__(self):
        return f"{self.volume} l cylinder of {self.gas.__repr__()} @ {self.pressure:.0f} bar"

    def compute_blend(self, gases: list[GasBlend], start=None):
        for blend in gases:
            for gas in blend.blend:
                if gas not in self.gas.blend:
                    gases.remove(blend)
                    logger.debug(
                        f"removed {blend.__repr__()} from available gases as contains unused gas {gas}"
                    )
                    break

        if start is None:
            start = Cylinder(air, self.volume)
        elif self.volume != start.volume:
            raise ValueError("Start cylinder should have the same volume")

        for gas in start.gas.blend:
            if gas not in self.gas.blend:
                raise ValueError(f"Unwanted gas {gas.name} in initial blend")

        volumes_needed = [
            self.volume_of(gas) - start.volume_of(gas) for gas in self.gas.blend
        ]

        coefficients = np.array(
            [[blend.fraction(gas) for blend in gases] for gas in self.gas.blend],
            dtype=np.dtype(float),
        )

        res = np.linalg.solve(
            coefficients, np.array(volumes_needed, dtype=np.dtype(float))
        )

        for val, gas in zip(res, gases):
            if val == 0:
                logger.debug(f"No {gas.__repr__()} needed")
                continue
            if val < 0:
                raise ValueError("Impossible to blend this gas")
            start.add_other_gas(gas, val)
            yield gas, val, start
