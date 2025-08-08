import logging
import math
from typing import TYPE_CHECKING

import plotly.express as px

from pydive.models.decompression.model import DecompressionModel
from pydive.gas import Gas, Nitrogen, Helium, air

if TYPE_CHECKING:
    import pydive.dive

logger = logging.getLogger(__name__)


class BuhlmannCompartment:
    gas: Gas
    a: float
    b: float
    half_life: float
    history: list[float]

    water_vapour_pressure = 0.0627

    def __init__(self, gas: Gas, a: float, b: float, half_life: float):
        self.gas = gas
        self.a = a
        self.b = b
        self.half_life = half_life

        self.inert_gas_pressure: float = air.fraction(self.gas) * (
            1 - self.water_vapour_pressure
        )
        self.history = [self.inert_gas_pressure]

    @property
    def time_constant(self):
        return math.log(2) / self.half_life

    def __repr__(self):
        return f"{self.gas.formula} - a: {self.a}, b: {self.b}, half-life: {self.half_life} mins"

    def apply_dive_step(self, step: "pydive.dive.DiveStep"):
        gas_fraction = step.gas.fraction(self.gas)
        alveolar_pressure = gas_fraction * (
            step.start_pressure - self.water_vapour_pressure
        )
        rate = gas_fraction * step.pressure_rate
        duration = step.minutes
        k = math.log(2) / self.half_life
        inert_gas_pressure = self.inert_gas_pressure
        self.inert_gas_pressure = (
            alveolar_pressure
            + rate * (duration - 1 / k)
            - (alveolar_pressure - inert_gas_pressure - rate / k)
            * math.exp(-k * duration)
        )
        self.history.append(self.inert_gas_pressure)

    def undo_last_step(self):
        self.history.pop(-1)
        self.inert_gas_pressure = self.history[-1]


class BuhlmannCompoundCompartment:
    compartments: list[BuhlmannCompartment]

    history: list[float]

    def __init__(self, *args):
        self.compartments = []
        for arg in args:
            self.compartments.append(BuhlmannCompartment(*arg))

        self.history = [self.pressure_limit()]

    def __repr__(self):
        return self.compartments.__repr__()

    def apply_dive_step(self, step):
        for compartment in self.compartments:
            compartment.apply_dive_step(step)
        self.history.append(self.pressure_limit(1))

    def undo_last_step(self):
        for compartment in self.compartments:
            compartment.undo_last_step()
        self.history.pop(-1)

    @property
    def inert_gas_pressure(self):
        return sum(
            [compartment.inert_gas_pressure for compartment in self.compartments]
        )

    @property
    def a(self):
        return (
            sum(
                [
                    compartment.a * compartment.inert_gas_pressure
                    for compartment in self.compartments
                ]
            )
            / self.inert_gas_pressure
        )

    @property
    def b(self):
        return (
            sum(
                [
                    compartment.b * compartment.inert_gas_pressure
                    for compartment in self.compartments
                ]
            )
            / self.inert_gas_pressure
        )

    def pressure_limit(self, gradient_factor=1):
        return (self.inert_gas_pressure - self.a * gradient_factor) / (
            gradient_factor / self.b + 1 - gradient_factor
        )

    def loading(self, depth):
        ambient_pressure = depth / 10 + 1
        max_pressure = ambient_pressure / self.b + self.a
        return max(
            (self.inert_gas_pressure - ambient_pressure)
            / (max_pressure - ambient_pressure),
            0,
        )


class BuhlmannBase(DecompressionModel):
    name = "Buhlmann basic model"
    compartments = list[BuhlmannCompoundCompartment]

    supported_gas: list[Gas]

    low_gf = 0.3
    high_gf = 0.7

    def gf(self, depth):
        if self.first_stop is None:
            gf = self.low_gf
        elif depth > self.first_stop:
            gf = self.low_gf
        else:
            gf = (self.first_stop - depth) / self.first_stop * (
                self.high_gf - self.low_gf
            ) + self.low_gf
        logger.debug(f"GF at {depth} m is {gf} ({self.low_gf}/{self.high_gf})")
        return gf

    @property
    def n_compartments(self):
        return len(self.compartments)

    def apply_dive_step(self, step: "pydive.dive.DiveStep"):
        logger.debug(f"applying [{step}] to Buhlmann model")
        for compartment in self.compartments:
            compartment.apply_dive_step(step)

    def undo_last_step(self):
        logger.debug("undoing last step from Buhlmann model")
        for compartment in self.compartments:
            compartment.undo_last_step()

    @property
    def df(self):
        df = self.dive.df

        for idx, compartment in enumerate(self.compartments):
            for sub_compartment in compartment.compartments:
                df[f"{sub_compartment.gas.formula}_{idx + 1}"] = sub_compartment.history
            df[f"limit_{idx + 1}"] = compartment.history

        return df

    def plot_profile(self):  # pragma: no cover
        df = self.df
        df["pressure"] = df.depth / 10 + 1
        df = df.drop(columns="depth")
        fig = px.line(df, x="time", y=df.columns)
        fig.layout.xaxis.tickformat = "%M:%S"
        return fig

    def ceilings(self, depth=None):
        if depth is None:
            depth = self.dive.depth
        gf = self.gf(depth)
        ceilings = [
            max(compartment.pressure_limit(gf) * 10 - 10, 0)
            for compartment in self.compartments
        ]
        return ceilings

    def ceiling(self, depth=None):
        if depth is None:
            depth = self.dive.depth
        ceiling = max(self.ceilings(depth))
        logger.debug(
            f"ceiling is {ceiling} m at {self.dive.depth} m using GF {self.gf(depth)}"
        )
        return ceiling

    @property
    def can_surface(self):
        gf = self.high_gf
        ceiling = (
            max([compartment.pressure_limit(gf) for compartment in self.compartments])
            * 10
        ) - 10
        return ceiling <= 0

    def loading(self, depth):
        return max([compartment.loading(depth) for compartment in self.compartments])

    def __repr__(self):
        return f"{self.loading(self.dive.depth):.0%}"


class BuhlmannZHL16C(BuhlmannBase):
    name = "Buhlmann ZHL-16C"

    supported_gas = [Nitrogen, Helium]

    N2_a = [
        1.1696,
        1.0,
        0.8618,
        0.7562,
        0.62,
        0.5043,
        0.441,
        0.4,
        0.375,
        0.35,
        0.3295,
        0.3065,
        0.2835,
        0.261,
        0.248,
        0.2327,
    ]

    N2_b = [
        0.5578,
        0.6514,
        0.7222,
        0.7825,
        0.8126,
        0.8434,
        0.8693,
        0.8910,
        0.9092,
        0.9222,
        0.9319,
        0.9403,
        0.9477,
        0.9544,
        0.9602,
        0.9653,
    ]

    N2_half_life = [
        5.0,
        8.0,
        12.5,
        18.5,
        27.0,
        38.3,
        54.3,
        77.0,
        109.0,
        146.0,
        187.0,
        239.0,
        305.0,
        390.0,
        498.0,
        635.0,
    ]

    He_a = [
        1.6189,
        1.383,
        1.1919,
        1.0458,
        0.922,
        0.8205,
        0.7305,
        0.6502,
        0.595,
        0.5545,
        0.5333,
        0.5189,
        0.5181,
        0.5176,
        0.5172,
        0.5119,
    ]

    He_b = [
        0.4770,
        0.5747,
        0.6527,
        0.7223,
        0.7582,
        0.7957,
        0.8279,
        0.8553,
        0.8757,
        0.8903,
        0.8997,
        0.9073,
        0.9122,
        0.9171,
        0.9217,
        0.9267,
    ]

    He_half_life = [
        1.88,
        3.02,
        4.72,
        6.99,
        10.21,
        14.48,
        20.53,
        29.11,
        41.20,
        55.19,
        70.69,
        90.34,
        115.29,
        147.42,
        188.24,
        240.03,
    ]

    def __init__(self, dive):
        super().__init__(dive)
        self.compartments = [
            BuhlmannCompoundCompartment(
                [Nitrogen, a, b, half_life], [Helium, a1, b1, half_life1]
            )
            for a, b, half_life, a1, b1, half_life1 in zip(
                self.N2_a,
                self.N2_b,
                self.N2_half_life,
                self.He_a,
                self.He_b,
                self.He_half_life,
            )
        ]
