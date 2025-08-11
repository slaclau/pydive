import logging

import gi

from pydive.dive import Dive
from pydive.gui.dive_point_view import DivePointView
from pydive.gui.gas_blend_view import GasBlendView

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GObject

logger = logging.getLogger(__name__)


@Gtk.Template(resource_path="/io/github/slaclau/pydive/gtk/dive_table_view.ui")
class DiveTableView(Gtk.Box):
    __gtype_name__ = "DiveTableView"

    gas_blend_view: GasBlendView = Gtk.Template.Child()
    dive_point_view: DivePointView = Gtk.Template.Child()

    dive: Dive

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.gas_blend_view.add_gas(None)
        gases = self.gas_blend_view.gases
        self.dive_point_view.available_gases = gases
        self.dive_point_view.add_dive_point(None)

        self.gas_blend_view.connect(
            "gases-changed", lambda _: self.emit("dive-changed")
        )
        self.dive_point_view.connect(
            "points-changed", lambda _: self.emit("dive-changed")
        )

    def create_dive(self):
        steps = self.dive_point_view.dive_points
        dive = Dive(steps[0].gas.gas)
        for step in steps:
            if step.gas.gas != dive.gas:
                dive.switch_gas(step.gas.gas)
            if step.depth > dive.depth:
                time = dive.descend(step.depth).minutes
            elif step.depth < dive.depth:
                time = dive.ascend(step.depth).minutes
            else:
                time = 0
            assert step.duration >= time
            dive.stay(step.duration - time)
        for gas in self.gas_blend_view.gases:
            dive.deco_gases[gas.switch_depth] = gas.gas
        return dive

    @GObject.Signal
    def dive_changed(self):
        self.dive = self.create_dive()
        logger.debug(f"dive created: {self.dive.markdown}")
