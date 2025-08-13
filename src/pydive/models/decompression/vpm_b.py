import logging
from math import exp, log, ceil, floor
from typing import TYPE_CHECKING

from pydive.gas import Gas, Nitrogen, Helium, air
from pydive.models.decompression.buhlmann import (
    BuhlmannZHL16C,
    BuhlmannCompoundCompartment,
    BuhlmannCompartment,
)
from pydive.models.decompression.model import DecompressionModel
from pydive.utils import Polynomial

if TYPE_CHECKING:
    import pydive.dive

ARRAY_LENGTH = 16

logger = logging.getLogger(__name__)


class DecompressionStepException(Exception):
    """Thrown when the decompression step is too large."""

    def __init__(self, value):
        self.value = value
        super(DecompressionStepException, self).__init__()

    def __str__(self):
        return repr(self.value)


class VPMBCompartment(BuhlmannCompartment):
    surface_tension_gamma = 0.18137175
    skin_compression_gamma_c = 2.6040525
    water_vapour_pressure = 0.0493
    critical_volume_parameter_lambda = 199.58

    desaturation_time = None

    def __init__(self, gas: Gas, a: float, b: float, half_life: float):
        super().__init__(gas, a, b, half_life)
        self.crushing_pressure_history = [0]

    def apply_dive_step(self, step: "pydive.dive.DiveStep"):
        super().apply_dive_step(step)

    def undo_last_step(self):
        super().undo_last_step()
        self.crushing_pressure_history.pop(-1)

    @property
    def max_crushing_pressure(self):
        return max(self.crushing_pressure_history)

    @property
    def initial_allowable_gradient(self):
        return (
            2.0
            * self.surface_tension_gamma
            * (self.skin_compression_gamma_c - self.surface_tension_gamma)
        ) / (self.regenerated_radius * self.skin_compression_gamma_c)

    @property
    def bottom_allowable_gradient(self):
        if self.desaturation_time is None:
            return self.initial_allowable_gradient
        b = self.initial_allowable_gradient + (
            self.critical_volume_parameter_lambda * self.surface_tension_gamma
        ) / (self.skin_compression_gamma_c * self.desaturation_time)
        c = (
            self.surface_tension_gamma**2
            * self.critical_volume_parameter_lambda
            * self.adjusted_crushing_pressure
        )
        c = c / (self.skin_compression_gamma_c**2 * self.desaturation_time)

        rtn = 0.5 * (b + (b**2 - 4 * c) ** 0.5)
        return rtn

    def allowable_gradient(self, first_stop, depth):
        if first_stop is None:
            rtn = self.bottom_allowable_gradient
        else:
            pressure = depth / 10 + 1
            first_stop_pressure = first_stop / 10 + 1
            b = self.bottom_allowable_gradient**3 / (
                first_stop_pressure + self.bottom_allowable_gradient
            )
            c = pressure * b

            roots = Polynomial([1, 0, -b, -c]).roots()
            assert len(roots) == 1
            rtn = roots[0]
        logger.debug(
            f"allowable {self.gas.name} gradient is {rtn:.3f} @ {depth:.0f} m where radius is {self.regenerated_radius:.3f} and bottom gradient is {self.bottom_allowable_gradient:.3f}"
        )
        return rtn


class VPMBCompoundCompartment(BuhlmannCompoundCompartment):
    compartments: list[VPMBCompartment]
    crushing_onset_tension_history = [0]

    pressure_other_gases = 102 / 760.0 * 10.1325 / 10
    gradient_onset_of_impermeability = 8.2 * 1.01325  # bar

    def __init__(self, *args):
        self.compartments = []
        for arg in args:
            self.compartments.append(VPMBCompartment(*arg))

    @property
    def crushing_onset_tension(self):
        return self.crushing_onset_tension_history[-1]

    def apply_dive_step(self, step: "pydive.dive.DiveStep"):
        super().apply_dive_step(step)
        pressure = step.dive.depth / 10 + 1
        tension = self.inert_gas_pressure + self.pressure_other_gases
        gradient = pressure - tension
        if gradient <= self.gradient_onset_of_impermeability:
            for compartment in self.compartments:
                compartment.crushing_pressure_history.append(gradient)
            self.crushing_onset_tension_history.append(tension)
        else:
            self.crushing_onset_tension_history.append(self.crushing_onset_tension)
            if step.rate <= 0:
                for compartment in self.compartments:
                    compartment.crushing_pressure_history.append(
                        compartment.crushing_pressure_history[-1]
                    )

            else:
                for compartment in self.compartments:
                    inner_pressure = compartment.inner_pressure(
                        self.crushing_onset_tension
                    )
                    compartment.crushing_pressure_history.append(
                        pressure - inner_pressure
                    )

    def allowable_gradient(self, first_stop, depth):
        return (
            sum(
                [
                    c.allowable_gradient(first_stop, depth) * c.inert_gas_pressure
                    for c in self.compartments
                ]
            )
            / self.inert_gas_pressure
        )

    def tolerated_ambient_pressure(self, first_stop, depth):
        return (
            self.inert_gas_pressure
            + self.pressure_other_gases
            - self.allowable_gradient(first_stop, depth)
        )

    def _update_desaturation_times(self, deco_time):
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
                - exp(
                    -get_compartment(Helium).time_constant * decay_time_to_zero_gradient
                )
            ) + (
                inert_gas_pressure(Nitrogen) - inspired(Nitrogen)
            ) / get_compartment(
                Nitrogen
            ).time_constant * (
                1
                - exp(
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
            compartment.desaturation_time = deco_time / 60 + surface_phase


class VPMB(BuhlmannZHL16C):
    name = "VPM-B model"
    compartments = list[VPMBCompoundCompartment]

    cva = True

    regeneration_time_constant = 20160 * 60
    conservatism_level = 2
    units_factor = 10.1325
    water_vapor_pressure = 0.493

    start_of_deco_zone = 0
    time_start_of_deco_zone = None

    ascend_before_ceiling_check = False
    gas_switch_time = 0
    switch_only_at_required_stop = True

    def critical_radius(self, gas: type[Nitrogen | Helium]):
        radii = {Nitrogen: 0.55, Helium: 0.45}
        conservatism_levels = [1.0, 1.05, 1.12, 1.22, 1.35]
        return radii[gas] * conservatism_levels[self.conservatism_level]

    def do_to_sub_compartment(self, func):
        for compartment in self.compartments:
            for sub_compartment in compartment.compartments:
                func(sub_compartment)

    def __init__(self, dive):
        DecompressionModel.__init__(self, dive)
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

    def nuclear_regeneration(self, dive_time):
        """
        Purpose: This subprogram calculates the regeneration of VPM critical
        radii that takes place over the dive time.  The regeneration time constant
        has a time scale of weeks so this will have very little impact on dives of
        normal length, but will have a major impact for saturation dives.
        """

        def set_crushing_pressure(compartment):
            crushing_pressure = compartment.max_crushing_pressure

            ending_radius = 1.0 / (
                crushing_pressure
                / (
                    2.0
                    * (
                        compartment.skin_compression_gamma_c
                        - compartment.surface_tension_gamma
                    )
                )
                + 1.0 / compartment.adjusted_critical_radius
            )

            # A "regenerated" radius for each nucleus is now calculated based on the
            # regeneration time constant.  This means that after application of
            # crushing pressure and reduction in radius, a nucleus will slowly grow
            # back to its original initial radius over a period of time.  This
            # phenomenon is probabilistic in nature and depends on absolute temperature.
            # It is independent of crushing pressure.

            compartment.regenerated_radius = compartment.adjusted_critical_radius + (
                ending_radius - compartment.adjusted_critical_radius
            ) * exp(-dive_time / self.regeneration_time_constant)

            # In order to preserve reference back to the initial critical radii after
            # regeneration, an "adjusted crushing pressure" for the nuclei in each
            # compartment must be computed.  In other words, this is the value of
            # crushing pressure that would have reduced the original nucleus to the
            # to the present radius had regeneration not taken place.  The ratio
            # for adjusting crushing pressure is obtained from algebraic manipulation
            # of the standard VPM equations.  The adjusted crushing pressure, in lieu
            # of the original crushing pressure, is then applied in the VPM Critical
            # Volume Algorithm and the VPM Repetitive Algorithm.

            crush_pressure_adjust_ratio = (
                ending_radius
                * (
                    compartment.adjusted_critical_radius
                    - compartment.regenerated_radius
                )
            ) / (
                compartment.regenerated_radius
                * (compartment.adjusted_critical_radius - ending_radius)
            )

            adj_crush_pressure = crushing_pressure * crush_pressure_adjust_ratio

            compartment.adjusted_crushing_pressure = adj_crush_pressure

        self.do_to_sub_compartment(set_crushing_pressure)

    def _update_desaturation_times(self):
        for compartment in self.compartments:
            compartment._update_desaturation_times(self.deco_phase_volume_time)

    def calculate_start_of_deco_zone(self):
        """
        Purpose: This subroutine uses the Bisection Method to find the depth at
        which the leading compartment just enters the decompression zone.
        Source:  "Numerical Recipes in Fortran 77", Cambridge University Press,
        1992.

        Side Effects: Sets
        `self.Depth_Start_of_Deco_Zone`

        or

        Raises a RootException

        Returns: None
        """
        rtn = 0
        for compartment in self.compartments:
            depth_change = self.dive.depth / 2
            target_depth = self.dive.depth - depth_change
            while depth_change >= 10**-2:
                depth_change /= 2
                steps = self.ascend_check_switch(target_depth)
                if (
                    compartment.inert_gas_pressure + compartment.pressure_other_gases
                    > target_depth / 10 + 1
                ):  # in deco zone
                    target_depth += depth_change
                else:
                    target_depth -= depth_change
                self.dive.undo_steps(len(steps))
            rtn = max(target_depth, rtn)
        return rtn

    @property
    def deepest_possible_stop(self):
        interval = 3
        rtn = (
            floor((self.start_of_deco_zone - self.last_stop) / interval) * interval
            + self.last_stop
        )
        return rtn

    def ceiling(self, depth=None):
        if depth is None:
            depth = self.dive.depth
        """
        Purpose: This subprogram calculates the ascent ceiling (the safe ascent
        depth) in each compartment, based on the allowable gradients, and then
        finds the deepest ascent ceiling across all compartments.

        Side Effects: Sets
        `self.Ascent_Ceiling_Depth`

        Returns: None
        """

        # Since there are two sets of allowable gradients being tracked, one for
        # helium and one for nitrogen, a "weighted allowable gradient" must be
        # computed each time based on the proportions of helium and nitrogen in
        # each compartment.  This proportioning follows the methodology of
        # Buhlmann/Keller.  If there is no helium and nitrogen in the compartment,
        # such as after extended periods of oxygen breathing, then the minimum value
        # across both gases will be used.  It is important to note that if a
        # compartment is empty of helium and nitrogen, then the weighted allowable
        # gradient formula cannot be used since it will result in division by zero.
        rtn = 0
        for compartment in self.compartments:
            #     The tolerated ambient pressure cannot be less than zero absolute, i.e.,
            #     the vacuum of outer space!
            tolerated_ambient_pressure = compartment.tolerated_ambient_pressure(
                self.first_stop, depth
            )
            if tolerated_ambient_pressure < 0.0:
                tolerated_ambient_pressure = 0.0

            #     The Ascent Ceiling Depth is computed in a loop after all of the individual
            #     compartment ascent ceilings have been calculated.  It is important that
            #     the Ascent Ceiling Depth (max ascent ceiling across all compartments) only
            #     be extracted from the compartment values and not be compared against some
            #     initialization value.  For example, if MAX(Ascent_Ceiling_Depth . .) was
            #     compared against zero, this could cause a program lockup because sometimes
            #     the Ascent Ceiling Depth needs to be negative (but not less than zero
            #     absolute ambient pressure) in order to decompress to the last stop at zero
            #     depth.

            ceiling = 10 * (tolerated_ambient_pressure - 1)
            rtn = max(ceiling, rtn)

        return rtn

    def critical_volume_loop(self):
        """
        Purpose:
        If the Critical Volume
        Algorithm is toggled "off" in the program settings, there will only be
        one pass through this loop.  Otherwise, there will be two or more passes
        through this loop until the deco schedule is "converged" - that is when a
        comparison between the phase volume time of the present iteration and the
        last iteration is less than or equal to one minute.  This implies that
        the volume of released gas in the most recent iteration differs from the
        "critical" volume limit by an acceptably small amount.  The critical
        volume limit is set by the Critical Volume Parameter Lambda in the program
        settings (default setting is 7500 fsw-min with adjustability range from
        from 6500 to 8300 fsw-min according to Bruce Wienke).
        """
        i = 0
        while True:
            if self.dive.depth != self.start_of_deco_zone:
                self.ascend_check_switch(self.start_of_deco_zone)
            last_deco_phase_volume_time = self.deco_phase_volume_time
            i += 1
            # CALCULATE INITIAL ASCENT CEILING BASED ON ALLOWABLE SUPERSATURATION
            # GRADIENTS AND SET FIRST DECO STOP.  CHECK TO MAKE SURE THAT SELECTED STEP
            # SIZE WILL NOT ROUND UP FIRST STOP TO A DEPTH THAT IS BELOW THE DECO ZONE.
            ascent_ceiling = self.ceiling()
            self.dive.undo_last_step()
            if ascent_ceiling <= 0.0:
                deco_stop_depth = 0.0
            else:
                interval = 3
                deco_stop_depth = (
                    ceil((ascent_ceiling - self.last_stop) / interval) * interval
                    + self.last_stop
                )

            if deco_stop_depth > self.start_of_deco_zone:
                raise DecompressionStepException(
                    "ERROR! STEP SIZE IS TOO LARGE TO DECOMPRESS"
                )

            # PERFORM A SEPARATE "PROJECTED ASCENT" OUTSIDE OF THE MAIN PROGRAM TO MAKE
            # SURE THAT AN INCREASE IN GAS LOADINGS DURING ASCENT TO THE FIRST STOP WILL
            # NOT CAUSE A VIOLATION OF THE DECO CEILING.  IF SO, ADJUST THE FIRST STOP
            # DEEPER BASED ON STEP SIZE UNTIL A SAFE ASCENT CAN BE MADE.
            # Note: this situation is a possibility when ascending from extremely deep
            # dives or due to an unusual gas mix selection.
            # CHECK AGAIN TO MAKE SURE THAT ADJUSTED FIRST STOP WILL NOT BE BELOW THE
            # DECO ZONE.

            # TODO: Should this be implemented??
            if deco_stop_depth > self.start_of_deco_zone:
                raise DecompressionStepException(
                    "ERROR! STEP SIZE IS TOO LARGE TO DECOMPRESS"
                )

            #     HANDLE THE SPECIAL CASE WHEN NO DECO STOPS ARE REQUIRED - ASCENT CAN BE
            #     MADE DIRECTLY TO THE SURFACE
            #     Write ascent data to output file and exit the Critical Volume Loop.

            if deco_stop_depth == 0.0:
                return

            # ASSIGN VARIABLES FOR ASCENT FROM START OF DECO ZONE TO FIRST STOP.  SAVE
            # FIRST STOP DEPTH FOR LATER USE WHEN COMPUTING THE FINAL ASCENT PROFILE

            # self.Starting_Depth = self.Depth_Start_of_Deco_Zone
            # self.First_Stop_Depth = self.Deco_Stop_Depth
            self.first_stop = deco_stop_depth
            stops = []
            while True:
                switch_depth = self._next_switch
                ascent_time = sum(
                    [step.minutes for step in self.ascend_check_switch(deco_stop_depth)]
                )
                if self.dive.depth == 0:
                    break

                stop = self.find_stop_length(60 * (ascent_time - floor(ascent_time)))
                stops.append(stop)

                deco_stop_depth = self._next_stop(self.dive.depth)

            # COMPUTE TOTAL PHASE VOLUME TIME AND MAKE CRITICAL VOLUME COMPARISON
            # The deco phase volume time is computed from the run time.  The surface
            # phase volume time is computed in a subroutine based on the surfacing gas
            # loadings from previous deco loop block.  Next the total phase volume time
            # (in-water + surface) for each compartment is compared against the previous
            # total phase volume time.  The schedule is converged when the difference is
            # less than or equal to 1 minute in any one of the ARRAY_LENGTH compartments.

            # Note:  the "phase volume time" is somewhat of a mathematical concept.
            # It is the time divided out of a total integration of supersaturation
            # gradient x time (in-water and surface).  This integration is multiplied
            # by the excess bubble number to represent the amount of free-gas released
            # as a result of allowing a certain number of excess bubbles to form.
            self.deco_phase_volume_time = (
                self.dive.duration - self.time_start_of_deco_zone
            )

            self._update_desaturation_times()
            if not self.cva:
                break
            if self.deco_phase_volume_time - last_deco_phase_volume_time <= 1:
                break
            self.dive.reset()
            self.dive.in_decompression = True
        return stops

    def decompression_loop(self):
        # First, calculate the regeneration of critical radii that takes place over
        # the dive time.  The regeneration time constant has a time scale of weeks
        # so this will have very little impact on dives of normal length, but will
        # have major impact for saturation dives.
        self.nuclear_regeneration(self.dive.duration)

        def set_start_ascent_pressure(compartment: VPMBCompartment):
            compartment.start_of_ascent_inert_gas_pressure = (
                compartment.inert_gas_pressure
            )

        self.do_to_sub_compartment(set_start_ascent_pressure)

        self.start_of_deco_time = self.dive.duration

        #     INPUT PARAMETERS TO BE USED FOR STAGED DECOMPRESSION AND SAVE IN ARRAYS.
        #     ASSIGN INITIAL PARAMETERS TO BE USED AT START OF ASCENT
        #     The user has the ability to change mix, ascent rate, and step size in any
        #     combination at any depth during the ascent.

        # CALCULATE THE DEPTH WHERE THE DECOMPRESSION ZONE BEGINS FOR THIS PROFILE
        # BASED ON THE INITIAL ASCENT PARAMETERS AND WRITE THE DEEPEST POSSIBLE
        # DECOMPRESSION STOP DEPTH TO THE OUTPUT FILE
        # Knowing where the decompression zone starts is very important.  Below
        # that depth there is no possibility for bubble formation because there
        # will be no supersaturation gradients.  Deco stops should never start
        # below the deco zone.  The deepest possible stop deco stop depth is
        # defined as the next "standard" stop depth above the point where the
        # leading compartment enters the deco zone.  Thus, the program will not
        # base this calculation on step sizes larger than 10 fsw or 3 msw.  The
        # deepest possible stop depth is not used in the program, per se, rather
        # it is information to tell the diver where to start putting on the brakes
        # during ascent.  This should be prominently displayed by any deco program.

        self.start_of_deco_zone = self.calculate_start_of_deco_zone()

        #     TEMPORARILY ASCEND PROFILE TO THE START OF THE DECOMPRESSION ZONE, SAVE
        #     VARIABLES AT THIS POINT, AND INITIALIZE VARIABLES FOR CRITICAL VOLUME LOOP
        #     The iterative process of the VPM Critical Volume Algorithm will operate
        #     only in the decompression zone since it deals with excess gas volume
        #     released as a result of supersaturation gradients (not possible below the
        #     decompression zone).
        self.dive.in_decompression = True

        self.ascend_check_switch(self.start_of_deco_zone)
        self.time_start_of_deco_zone = self.dive.duration
        self.deco_phase_volume_time = 0.0

        def set_inert_gas_pressure_start_of_deco_zone(compartment: VPMBCompartment):
            compartment.inert_gas_pressure_start_of_deco_zone = (
                compartment.inert_gas_pressure
            )

        self.do_to_sub_compartment(set_inert_gas_pressure_start_of_deco_zone)

        return self.critical_volume_loop()

    def calculate_decompression_profile(self):
        def set_critical_radius(compartment):
            compartment.initial_critical_radius = self.critical_radius(compartment.gas)
            compartment.adjusted_critical_radius = compartment.initial_critical_radius
            logger.debug(
                f"set compartment initial and adjusted critical radii to {compartment.initial_critical_radius}"
            )

        self.do_to_sub_compartment(set_critical_radius)
        for stop in self.decompression_loop():
            yield stop
