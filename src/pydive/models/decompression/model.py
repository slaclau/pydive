import dataclasses
import logging
import math
from enum import Enum
from typing import TYPE_CHECKING

from pydive.gas import GasBlend
from pydive.models.base import Model

if TYPE_CHECKING:
    import pydive.dive

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class DecompressionStop:
    depth: float
    duration: float
    gas: GasBlend


class FirstStopAnchor(Enum):
    CEILING_AT_START_OF_DECO = 0
    ROUNDED_CEILING_AT_START_OF_DECO = 1
    FIRST_ACTUAL_STOP = 2


class DecompressionModel(Model):
    name: str
    dive: "pydive.dive.Dive"

    _first_stop: float = None

    # Deco configuration
    last_stop = 6
    first_stop_anchor = FirstStopAnchor.CEILING_AT_START_OF_DECO
    gas_switch_time = 1
    include_ascent_to_stop_in_stop = True
    ascend_before_ceiling_check = True
    switch_only_at_required_stop = False

    def apply_dive_step(self, step):
        raise NotImplementedError

    def undo_last_step(self):
        raise NotImplementedError

    def plot_profile(self):
        raise NotImplementedError

    @property
    def first_stop(self):
        return self._first_stop

    @first_stop.setter
    def first_stop(self, value):
        logger.debug(f"Setting first stop to {value}")
        self._first_stop = value

    def ceiling(self, depth=None):
        raise NotImplementedError

    @property
    def can_surface(self):
        raise NotImplementedError

    def calculate_decompression_profile(self):
        self.dive.in_decompression = True
        if self.can_surface:
            self.dive.ascend(0)
            return
        self.find_first_stop()
        ascent_time = 0
        while self.dive.depth > 0:
            yield self.find_stop_length(ascent_time)
            ascent = self.ascend_check_switch(self._next_stop(self.dive.depth))
            ascent_time = sum([step.duration for step in ascent])

    def ascend_check_switch(self, depth):
        if self.switch_only_at_required_stop:
            steps = [self.dive.ascend(depth)]
            if (
                self._last_switch is not None
                and self.dive.gas != self.dive.deco_gases[self._last_switch]
            ):
                steps.append(
                    self.dive.switch_gas(self.dive.deco_gases[self._last_switch])
                )
        else:
            steps = []
            switch = self._next_switch
            while switch and depth < switch:
                steps.append(self.dive.ascend(switch))
                steps.append(
                    self.dive.switch_gas(
                        self.dive.deco_gases[switch], self.gas_switch_time
                    )
                )
                switch = self._next_switch
            steps.append(self.dive.ascend(depth))
            if depth == switch:
                steps.append(
                    self.dive.switch_gas(
                        self.dive.deco_gases[switch], self.gas_switch_time
                    )
                )
        return steps

    def can_ascend(self, depth):
        if depth == self.dive.depth:
            rtn = True
        elif self.ascend_before_ceiling_check:
            steps = self.ascend_check_switch(depth)
            rtn = self.ceiling(depth) <= depth
            self.dive.undo_steps(len(steps))
        else:
            rtn = self.ceiling(depth) <= depth
        logger.info(f"can ascend to {depth:.0f} m from {self.dive.depth:.0f} m: {rtn}")
        return rtn

    def find_first_stop(self):
        ceiling = self.ceiling()
        if self.first_stop_anchor == FirstStopAnchor.CEILING_AT_START_OF_DECO:
            self.first_stop = ceiling
        current_ceiling = math.ceil(ceiling / 3) * 3
        if self.first_stop_anchor == FirstStopAnchor.ROUNDED_CEILING_AT_START_OF_DECO:
            self.first_stop = current_ceiling
        while self.can_ascend(current_ceiling):
            steps = self.ascend_check_switch(current_ceiling)
            exact_ceiling = self.ceiling()
            new_ceiling = math.ceil(exact_ceiling / 3) * 3
            logger.debug(
                f"ascended to new ceiling of {current_ceiling} and got ceiling of {exact_ceiling}"
            )
            self.dive.undo_steps(len(steps))
            if new_ceiling == current_ceiling:
                break
            current_ceiling = new_ceiling

        next_stop = self._next_stop(current_ceiling)
        if self.can_ascend(next_stop):
            self.ascend_check_switch(next_stop)
        else:
            self.ascend_check_switch(current_ceiling)

        logger.debug(
            f"found first stop at {self.dive.depth} m with ceiling {self.ceiling():.1f} m"
        )
        logger.debug(f"steps to here: {self.dive.decompression_steps}")
        if self.first_stop_anchor == FirstStopAnchor.FIRST_ACTUAL_STOP:
            self.first_stop = current_ceiling

    def find_stop_length(self, ascent_time):
        ascent_time = ascent_time / 60 if self.include_ascent_to_stop_in_stop else 0
        current_stop = self.dive.depth
        next_stop = self._next_stop(current_stop)
        ts = -ascent_time
        dt = 64
        self.dive.stay(ts + dt)
        while not self.can_ascend(next_stop):
            self.dive.undo_last_step()
            ts = ts + dt
            self.dive.stay(ts + dt)
        logger.debug(f"stop length between {ts} and {ts + dt}")

        self.dive.undo_last_step()
        dt = dt / 2
        self.dive.stay(ts + dt)
        while dt > 1:
            if not self.can_ascend(next_stop):
                ts = ts + dt
            dt = dt / 2
            self.dive.undo_last_step()
            self.dive.stay(ts + dt)
            logger.debug(f"stop length between {ts} and {ts + dt}")
        if not self.can_ascend(next_stop):
            ts = ts + dt
            self.dive.undo_last_step()
            self.dive.stay(ts + dt)
        logger.debug(f"stop length is {ts + dt}")
        logger.debug(
            f"ceiling at {self.dive.depth} is {self.ceiling(self.dive.depth)} and would be {self.ceiling(next_stop)} at {next_stop}"
        )
        return DecompressionStop(
            depth=current_stop, duration=ts + dt + ascent_time, gas=self.dive.gas
        )

    @property
    def _next_switch(self):
        switch_depths = [d for d in self.dive.deco_gases if d < self.dive.depth]
        if switch_depths:
            depth = max(switch_depths)
            return depth
        return None

    @property
    def _last_switch(self):
        switch_depths = [d for d in self.dive.deco_gases if d >= self.dive.depth]
        if switch_depths:
            depth = min(switch_depths)
            return depth
        return None

    def _next_stop(self, current_stop):
        last_stop = self.last_stop
        interval = 3
        if current_stop > last_stop:
            rtn = (
                interval * math.ceil((current_stop - last_stop) / interval) + last_stop
            ) - interval
        else:
            rtn = 0
        logger.debug(f"next stop after {current_stop:.0f} m is {rtn:.0f} m")
        return rtn
