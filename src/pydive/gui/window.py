import logging

import gi

from pydive.gas import GasBlend, air
from pydive.gui.dive_point_view import DivePoint, DivePointView
from pydive.gui.gas_blend_view import GasBlendView, GasChoice
from pydive.gui.gas_blender import GasBlenderDialog

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk

logger = logging.getLogger(__name__)


@Gtk.Template(resource_path="/io/github/slaclau/pydive/gtk/main.ui")
class PyDiveWindow(Adw.ApplicationWindow):
    __gtype_name__ = "PyDiveWindow"

    gas_blend_view: GasBlendView = Gtk.Template.Child()
    dive_point_view: DivePointView = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.actions = {}

        for action in ["show_gas_blender"]:
            gaction = Gio.SimpleAction.new(action, None)
            gaction.connect("activate", getattr(self, f"_on_{action}_activate"))
            self.actions[action] = gaction
            self.add_action(gaction)
        logger.debug("actions added")

        gases = self.gas_blend_view.gases
        gases.append(GasChoice(GasBlend(oxygen=0.21, nitrogen=0.79)))
        self.dive_point_view.available_gases = gases
        self.dive_point_view.dive_points.append(
            DivePoint(self.dive_point_view.dive_points, 20, 10, gases[0].gas)
        )

        logger.debug("window created")

    def _on_show_gas_blender_activate(self, obj, pspec):
        logger.debug("show_gas_blender activated")
        dialog = GasBlenderDialog()
        dialog.present(self)
