import copy
import logging

import plotly.express as px
import pandas as pd

from pydive.models.decompression.buhlmann import BuhlmannZHL16C
from pydive.models.decompression.model import DecompressionModel
from pydive.models.base import Model
from pydive.models.oxygen_toxicity import PulmonaryOxygenToxicity, CNSOxygenToxicity
from pydive.models.gas_consumption import GasConsumptionModel
from pydive.gas import GasBlend

logger = logging.getLogger(__name__)


class DiveStep:
    gas: GasBlend
    start_depth: float
    rate: float
    duration: float

    def __init__(self, start_depth, gas, rate, duration):
        logger.debug(
            f"Create DiveStep with {gas!r} @ {start_depth} m - {duration / 60:.1f} mins at {rate} m/min"
        )
        self.start_depth = start_depth
        self.gas = gas
        self.rate = rate
        self.duration = duration

    @property
    def depth_change(self):
        return self.rate * self.duration / 60

    @property
    def start_pressure(self):
        return self.start_depth / 10 + 1

    @property
    def pressure_rate(self):
        return self.rate / 10

    @property
    def minutes(self):
        return self.duration / 60

    def __repr__(self):
        return f"{self.gas!r} @ {self.start_depth} m - {self.start_depth + self.depth_change} for {self.duration / 60:.1f} mins at {self.rate} m/min"


class Dive:
    default_descent_rate = 10  # m/mins
    default_ascent_rate = 10  # m/mins
    steps: list[DiveStep]
    bottom_gas: GasBlend
    deco_gases: dict[float, GasBlend]

    decompression_model: DecompressionModel
    in_decompression: bool = False
    decompression_steps: list[DiveStep]

    models: dict[str, Model]

    @property
    def gas(self):
        if not (self.steps + self.decompression_steps):
            return self.bottom_gas
        return (self.steps + self.decompression_steps)[-1].gas

    @property
    def depth(self):
        return sum(
            [step.depth_change for step in self.steps + self.decompression_steps]
        )

    @property
    def duration(self):
        return sum([step.duration for step in self.steps + self.decompression_steps])

    def __init__(self, gas, model=None):
        if model is None:
            model = BuhlmannZHL16C
        self.decompression_model = model(self)
        self.models = {
            "decompression": self.decompression_model,
            "pulmonary": PulmonaryOxygenToxicity(self),
            "cns": CNSOxygenToxicity(self),
            "consumption": GasConsumptionModel(self),
        }
        self.bottom_gas = gas
        self.deco_gases = {}
        self.steps = []
        self.decompression_steps = []

    def apply_step(self, step: DiveStep):
        if not self.in_decompression:
            self.steps.append(step)
        else:
            self.decompression_steps.append(step)

        for model in self.models.values():
            model.apply_dive_step(step)
        return step

    def undo_last_step(self):
        if not self.in_decompression:
            self.steps.pop(-1)
        else:
            self.decompression_steps.pop(-1)
        for model in self.models.values():
            model.undo_last_step()

    def undo_steps(self, n):
        for i in range(0, n):
            self.undo_last_step()

    def descend(self, to, rate=None):
        if rate is None:
            rate = self.default_descent_rate
        logger.info(f"descend to {to} m at {rate} m/min")
        return self.apply_step(
            DiveStep(self.depth, self.gas, rate, (to - self.depth) / rate * 60)
        )

    def stay(self, duration):
        logger.info(f"stay at current depth for {duration} mins")
        return self.apply_step(DiveStep(self.depth, self.gas, 0, duration * 60))

    def ascend(self, to, rate=None):
        if rate is None:
            rate = self.default_ascent_rate
        logger.info(f"ascend to {to} m at {rate} m/min")
        return self.apply_step(
            DiveStep(self.depth, self.gas, -rate, (self.depth - to) / rate * 60)
        )

    def switch_gas(self, gas: GasBlend, switch_time=0):
        return self.apply_step(DiveStep(self.depth, gas, 0, switch_time * 60))
        return self.apply_step(DiveStep(self.depth, gas, 0, switch_time * 60))

    @property
    def df(self):  # pragma: no cover
        depths = [0]
        times = [0]
        current_depth = 0
        current_time = 0
        for step in self.steps + self.decompression_steps:
            current_depth = current_depth + step.depth_change
            current_time = current_time + step.duration

            depths.append(current_depth)
            times.append(current_time)

        df = pd.DataFrame({"depth": depths, "time": times})

        df.time = pd.to_datetime(df.time, unit="s")

        return df

    @property
    def markdown(self):
        step_types = []
        depths = []
        durations = []
        runtimes = []
        gases = []

        current_time = 0

        for step in self.steps + self.decompression_steps:
            if step.rate > 0:
                step_types.append("➘")
            elif step.rate < 0:
                step_types.append("➚")
            elif step in self.decompression_steps:
                step_types.append("■")
                # Maybe use ⇄ for gas switch
            else:
                step_types.append("➙")
            depths.append(step.start_depth + step.depth_change)
            durations.append(step.duration)
            current_time = current_time + step.duration
            runtimes.append(current_time)
            gases.append(step.gas.__repr__())

        df = pd.DataFrame(
            {
                "Step Type": step_types,
                "Depth": depths,
                "Duration": pd.to_timedelta(durations, unit="s"),
                "Runtime": pd.to_timedelta(runtimes, unit="s"),
                "Gas": gases,
            }
        )

        return df.to_markdown(index=False)

    def plot_profile(self):  # pragma: no cover
        fig = px.scatter(self.df, x="time", y="depth")
        fig.layout.yaxis.autorange = "reversed"
        fig.layout.xaxis.tickformat = "%M:%S"
        return fig

    def clone(self):
        return copy.deepcopy(self)

    def reset(self):
        logger.info("resetting")
        while self.decompression_steps:
            logger.debug(f"undoing {self.decompression_steps[-1]}")
            self.undo_last_step()
        self.in_decompression = False
        self.decompression_model.first_stop = None

    def reinterpolate_dive(self, interval=6, deco=True):
        new_dive = Dive(self.steps[0].gas, model=self.decompression_model.__class__)
        new_dive.decompression_model.first_stop = self.decompression_model.first_stop

        if deco:
            steps = self.steps + self.decompression_steps
        else:
            steps = self.steps
        for step in steps:
            if step in self.decompression_steps:
                new_dive.in_decompression = True
            time_left = step.duration
            while time_left > interval:
                time_left -= interval
                new_dive.apply_step(
                    DiveStep(new_dive.depth, step.gas, step.rate, interval)
                )
            new_dive.apply_step(
                DiveStep(new_dive.depth, step.gas, step.rate, time_left)
            )
        return new_dive

    def custom_df(self, column_functions: dict[str, callable]):
        df_dict = {"time": []}
        for column in column_functions:
            df_dict[column] = []

        new_dive = Dive(self.steps[0].gas)
        new_dive.decompression_model.first_stop = self.decompression_model.first_stop

        current_time = 0
        for step in self.steps + self.decompression_steps:
            new_dive.apply_step(step)
            df_dict["time"].append(current_time)
            for column, column_function in column_functions.items():
                df_dict[column].append(column_function(new_dive))
            current_time += step.duration
        df = pd.DataFrame(df_dict)
        return df
