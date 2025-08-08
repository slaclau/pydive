import importlib
import math
from _warnings import warn

import pandas as pd

from pydive.gas import Oxygen
from pydive.models.base import Model


class PulmonaryOxygenToxicity(Model):
    name = "Pulmonary oxygen toxicity model"

    otus = 0
    history: list[float]

    def __init__(self, dive):
        super().__init__(dive)
        self.history = []

    def apply_dive_step(self, step):
        pO2i = step.gas.partial_pressure(Oxygen, step.start_depth)
        pO2f = step.gas.partial_pressure(Oxygen, step.start_depth + step.depth_change)

        if pO2i < 0.5 and pO2f < 0.5:
            self.history.append(self.otus)
            return

        if pO2i < 0.5:
            duration = (pO2f - 0.5) / (pO2f - pO2i) * step.minutes
            pO2i = 0.5
        elif pO2f < 0.5:
            duration = (pO2i - 0.5) / (pO2i - pO2f) * step.minutes
            pO2f = 0.5
        else:
            duration = step.minutes

        if step.rate == 0:
            gain = duration * (0.5 / (pO2i - 0.5)) ** (-5 / 6)
        else:
            # print(f"{step!r} i {pO2i} f {pO2f}")
            gain = (
                (3 / 11)
                * duration
                / (pO2f - pO2i)
                * (((pO2f - 0.5) / 0.5) ** (11 / 6) - ((pO2i - 0.5) / 0.5) ** (11 / 6))
            )

        self.otus = self.otus + gain
        self.history.append(self.otus)

    def undo_last_step(self):
        self.history.pop(-1)
        self.otus = self.history[-1]

    def __repr__(self):
        return f"{self.otus:.0f} OTUs"


class CNSOxygenToxicity(Model):
    name = "Central nervous system oxygen toxicity model"

    fraction = 0
    history: list[float]

    def __init__(self, dive):
        super().__init__(dive)
        self.history = []

    cns_time_table = pd.read_csv(
        importlib.resources.files("pydive") / "models" / "cns.csv"
    )

    def apply_dive_step(self, step):
        pO2i = step.gas.partial_pressure(Oxygen, step.start_depth)
        pO2f = step.gas.partial_pressure(Oxygen, step.start_depth + step.depth_change)

        min_pO2 = min(pO2i, pO2f)
        max_pO2 = max(pO2i, pO2f)

        low_pO2 = max(self.cns_time_table.pO2_low.iloc[0], min_pO2)

        if max_pO2 <= self.cns_time_table.pO2_low.iloc[0]:
            self.history.append(self.fraction)
            return
        if max_pO2 > self.cns_time_table.pO2_high.iloc[-1]:
            warn(f"pO2 ({max_pO2}) exceeds table limits")

        if low_pO2 == max_pO2:
            for row in self.cns_time_table.itertuples():
                if row.pO2_low < low_pO2 <= row.pO2_high:
                    tlim = row.slope * low_pO2 + row.intercept

                    inc = step.minutes / tlim
                    self.fraction += inc
                    self.history.append(self.fraction)

                    return
            raise Exception

        time = step.minutes * (max_pO2 - low_pO2) / (max_pO2 - min_pO2)

        inc = 0
        for row in self.cns_time_table.itertuples():
            seg_low_pO2 = min(max(low_pO2, row.pO2_low), row.pO2_high)
            seg_high_pO2 = min(max(max_pO2, row.pO2_low), row.pO2_high)
            seg_time = time * (seg_high_pO2 - seg_low_pO2) / (max_pO2 - low_pO2)

            if seg_time == 0:
                continue
            tlim = row.slope * seg_low_pO2 + row.intercept
            mk = row.slope * (seg_high_pO2 - seg_low_pO2) / seg_time
            inc += 1 / mk * (math.log(abs(tlim + mk * seg_time)) - math.log(abs(tlim)))

        self.fraction += inc

        self.history.append(self.fraction)

    def undo_last_step(self):
        self.history.pop(-1)
        self.fraction = self.history[-1]

    def __repr__(self):
        return f"{self.fraction:.0%}"
