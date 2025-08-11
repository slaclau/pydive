import logging

import gi

from pydive.gas import GasBlend, air
from pydive.gui.dive_point_view import DivePoint, DivePointView
from pydive.gui.dive_table_view import DiveTableView
from pydive.gui.gas_blend_view import GasBlendView, GasChoice
from pydive.gui.gas_blender import GasBlenderDialog

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk

logger = logging.getLogger(__name__)


@Gtk.Template(resource_path="/io/github/slaclau/pydive/gtk/main.ui")
class PyDiveWindow(Adw.ApplicationWindow):
    __gtype_name__ = "PyDiveWindow"

    dive_table_view: DiveTableView = Gtk.Template.Child()
    text_view: Gtk.TextView = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.actions = {}

        for action in ["show_gas_blender"]:
            gaction = Gio.SimpleAction.new(action, None)
            gaction.connect("activate", getattr(self, f"_on_{action}_activate"))
            self.actions[action] = gaction
            self.add_action(gaction)
        logger.debug("actions added")

        def get_decompressed_dive(view):
            dive = view.dive
            dive.decompress()
            return dive

        self.dive_table_view.connect(
            "dive-changed",
            lambda view: self.text_view.get_buffer().set_text(
                get_decompressed_dive(view).markdown
            ),
        )

        logger.debug("window created")

    def _on_show_gas_blender_activate(self, obj, pspec):
        logger.debug("show_gas_blender activated")
        dialog = GasBlenderDialog()
        dialog.present(self)
