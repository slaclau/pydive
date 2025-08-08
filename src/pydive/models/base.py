import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pydive.dive


class Model(abc.ABC):
    name: str
    dive: "pydive.dive.Dive"

    def __init__(self, dive: "pydive.dive.Dive"):
        self.dive = dive

    def apply_dive_step(self, step):
        raise NotImplementedError

    def undo_last_step(self):
        raise NotImplementedError
