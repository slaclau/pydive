import logging

from pydive.gas import Gas, Helium, Nitrogen, air
from pydive.models.decompression.buhlmann import (
    BuhlmannCompartment,
    BuhlmannCompoundCompartment,
    BuhlmannZHL16C,
)
from pydive.models.decompression.model import DecompressionModel
from pydive.utils import Polynomial

logger = logging.getLogger(__name__)


class VPMBCompartment(BuhlmannCompartment):
    level: int
    boyle = True

    water_vapour_pressure = 0.0493
    gamma = 0.18137175
    gamma_c = 2.6040525
    critical_volume_lambda = 199.58

    first_stop = None
    desat_time = None

    def __init__(self, gas: Gas, a: float, b: float, half_life: float):
        super().__init__(gas, a, b, half_life)
        self.crushing_pressure_history = [0]

    @property
    def critical_radius(self):
        radii = {Nitrogen: 0.55, Helium: 0.45}
        levels = [1.0, 1.05, 1.12, 1.22, 1.35]
        return radii[self.gas] * levels[self.level]

    @property
    def regenerated_radius(self):
        return self.critical_radius

    @property
    def initial_allowable_gradient(self):
        return (2 * self.gamma * (self.gamma_c - self.gamma)) / (
            self.regenerated_radius * self.gamma_c
        )

    @property
    def bottom_allowable_gradient(self):
        if self.desat_time is None:
            return self.initial_allowable_gradient
        b = self.initial_allowable_gradient + (
            self.critical_volume_lambda * self.gamma
        ) / (self.gamma_c * self.desat_time)
        c = self.gamma**2 * self.critical_volume_lambda * self.max_crushing_pressure
        c = c / (self.gamma_c**2 * self.desat_time)

        return 0.5 * (b + (b**2 - 4 * c) ** 0.5)

    def allowable_gradient(self, ambient_pressure):
        if not self.boyle or self.first_stop is None:
            return self.bottom_allowable_gradient
        bottom_gradient = self.bottom_allowable_gradient
        first_stop_pressure = self.first_stop / 10 + 1

        b = bottom_gradient**3 / (first_stop_pressure + bottom_gradient)
        c = ambient_pressure * b

        roots = Polynomial([1, 0, -b, -c]).roots()
        assert len(roots) == 1
        return roots[0]

    @property
    def max_crushing_pressure(self):
        return max(self.crushing_pressure_history)

    def apply_dive_step(self, step):
        super().apply_dive_step(step)

    def undo_last_step(self):
        super().undo_last_step()
        self.crushing_pressure_history.pop(-1)


class VPMBCompoundCompartment(BuhlmannCompoundCompartment):
    compartments: list[VPMBCompartment]

    other_gases_pressure = 0.1359888
    gradient_of_impermeability = 8.30865

    @property
    def level(self):
        levels = [compartment.level for compartment in self.compartments]
        assert len(set(levels)) == 1
        return levels[0]

    @level.setter
    def level(self, value):
        for compartment in self.compartments:
            compartment.level = value

    @property
    def first_stop(self):
        return self._first_stop

    @first_stop.setter
    def first_stop(self, value):
        self._first_stop = value
        for compartment in self.compartments:
            compartment.first_stop = value

    def __init__(self, *args):
        self.compartments = []
        for arg in args:
            self.compartments.append(VPMBCompartment(*arg))
            self.crushing_onset_tension_history = [0]

    def allowable_gradient(self, ambient_pressure):
        if self.inert_gas_pressure > 0:
            return (
                sum(
                    [
                        c.allowable_gradient(ambient_pressure) * c.inert_gas_pressure
                        for c in self.compartments
                    ]
                )
                / self.inert_gas_pressure
            )
        return min([c.allowable_gradient(ambient_pressure) for c in self.compartments])

    def tolerable_ambient_pressure(self, ambient_pressure):
        return (
            self.inert_gas_pressure
            + self.other_gases_pressure
            - self.allowable_gradient(ambient_pressure)
        )

    def apply_dive_step(self, step):
        super().apply_dive_step(step)
        tension = self.inert_gas_pressure + self.other_gases_pressure
        depth = step.start_depth + step.depth_change
        ambient_pressure = depth / 10 + 1
        gradient = ambient_pressure - tension
        if gradient <= self.gradient_of_impermeability:
            for compartment in self.compartments:
                compartment.crushing_pressure_history.append(gradient)
            crushing_onset_tension = tension
        else:
            crushing_onset_tension = self.crushing_onset_tension_history[-1]
            max_depth = max([step.end_depth for step in self.dive.steps])
            if max_depth > depth:
                for compartment in self.compartments:
                    compartment.crushing_pressure_history.append(
                        compartment.crushing_pressure_history[-1]
                    )
            else:
                for compartment in self.compartments:
                    crushing_pressure = pressure - compartment.inner_pressure(
                        crushing_onset_tension
                    )
                compartment.crushing_pressure_history.append(crushing_pressure)

        self.crushing_onset_tension_history.append(crushing_onset_tension)

    def undo_last_step(self):
        super().undo_last_step()
        self.crushing_onset_tension_history.pop(-1)

    def _update_desat_times(self, deco_time):
        assert len(self.compartments) == 2

        def get_compartment(gas):
            return [c for c in self.compartments if c.gas == gas][0]

        def inspired(gas):
            compartment = get_compartment(gas)
            return (1 - compartment.water_vapour_pressure) * air.fraction(gas)

        def inert_gas_pressure(gas):
            return get_compartment(gas).inert_gas_pressure

        if inert_gas_pressure(Nitrogen) > inspired(Nitrogen):

            surface_phase = sum(
                [
                    (c.inert_gas_pressure - inspired(c.gas)) / c.time_constant
                    for c in self.compartments
                ]
            ) / sum([c.inert_gas_pressure - inspired(c.gas) for c in self.compartments])

        elif (inert_gas_pressure(Nitrogen) <= inspired(Nitrogen)) and (
            inert_gas_pressure(Helium) + inert_gas_pressure(Nitrogen)
            >= inspired(Nitrogen)
        ):
            decay_time_to_zero_gradient = (
                1.0
                / (
                    get_compartment(Nitrogen).time_constant
                    - get_compartment(Helium).time_constant
                )
                * log(
                    (inspired(Nitrogen) - inert_gas_pressure(Nitrogen))
                    / inert_gas_pressure(Helium)
                )
            )

            integral_gradient_x_time = inert_gas_pressure(Helium) / get_compartment(
                Helium
            ).time_constant * (
                1
                - math.exp(
                    -get_compartment(Helium).time_constant * decay_time_to_zero_gradient
                )
            ) + (
                inert_gas_pressure(Nitrogen) - inspired(Nitrogen)
            ) / get_compartment(
                Nitrogen
            ).time_constant * (
                1
                - math.exp(
                    -get_compartment(Nitrogen).time_constant
                    * decay_time_to_zero_gradient
                )
            )

            surface_phase = integral_gradient_x_time / (
                inert_gas_pressure(Helium)
                + inert_gas_pressure(Nitrogen)
                - inspired(Nitrogen)
            )

        else:
            surface_phase = 0

        for compartment in self.compartments:
            compartment.desat_time = deco_time / 60 + surface_phase


class VPM_B(BuhlmannZHL16C):
    ascend_before_ceiling_check = True
    cva = True

    start_deco_time = None
    deco_time = None

    @property
    def level(self):
        return self._level

    @level.setter
    def level(self, value):
        self._level = value
        for compartment in self.compartments:
            compartment.level = value

    @property
    def first_stop(self):
        return self._first_stop

    @first_stop.setter
    def first_stop(self, value):
        self._first_stop = value
        if value is not None:
            self.dive.ascend(value)
            self.start_deco_time = self.dive.duration
            self.dive.undo_last_step()
        for compartment in self.compartments:
            compartment.first_stop = value

    def __init__(self, dive):
        super().__init__(dive)
        self.compartments = [
            VPMBCompoundCompartment(
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
        self.level = 2

    def ceilings(self, depth=None):
        if depth is None:
            depth = self.dive.depth
        ambient_pressure = depth / 10 + 1
        return [
            c.tolerable_ambient_pressure(ambient_pressure) for c in self.compartments
        ]

    def ceiling(self, depth=None):
        if depth is None:
            depth = self.dive.depth
        ambient_pressure = depth / 10 + 1
        reference_pressure = 0
        rtn_tolerated_ambient_pressure = ambient_pressure
        loop_count = 0
        while abs(rtn_tolerated_ambient_pressure - reference_pressure) > 0.01:
            loop_count += 1
            reference_pressure = rtn_tolerated_ambient_pressure
            rtn_tolerated_ambient_pressure = max(
                [
                    c.tolerable_ambient_pressure(reference_pressure)
                    for c in self.compartments
                ]
            )
        # logger.info(f"found ceiling in {loop_count} iterations")
        return 10 * (rtn_tolerated_ambient_pressure - 1)

    def calculate_decompression_profile(self):
        previous_deco_time = None
        loop_count = 0
        while (
            self.deco_time is None
            or previous_deco_time is None
            or previous_deco_time - self.deco_time > 10
        ):
            previous_deco_time = self.deco_time
            loop_count += 1
            self.dive.reset()
            stops = [
                stop
                for stop in DecompressionModel.calculate_decompression_profile(self)
            ]
            print(self.compartments[0].compartments[0].bottom_allowable_gradient)
            self.deco_time = self.dive.duration - self.start_deco_time
            self._update_desat_times()
            logger.debug(
                f"s time c0 {self.compartments[0].compartments[0].desat_time - self.deco_time / 60}"
            )
            logger.debug(f"cva iteration {loop_count} with deco time {self.deco_time}")
            if not self.cva:
                break
        logger.info(f"cva complete after {loop_count} iterations")

        for stop in stops:
            yield stop

    def _update_desat_times(self):
        for compartment in self.compartments:
            compartment._update_desat_times(self.deco_time)
