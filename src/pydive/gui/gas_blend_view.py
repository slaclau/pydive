import dataclasses
import math

import gi

from pydive.gas import GasBlend, Helium, Oxygen
from pydive.gui.widgets import DeleteColumn, IntEntryColumn, IntLabelColumn, LabelColumn

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GObject, Gtk


class GasChoice(GObject.Object):
    gas: GasBlend

    def __init__(self, gas):
        super().__init__()
        self.gas = gas

    @GObject.Property(type=int)
    def oxygen(self):
        return round(100 * self.gas.fraction(Oxygen))

    @oxygen.setter
    def oxygen(self, value):
        helium = self.helium
        nitrogen = 100 - value - helium
        self.gas.set_blend(
            oxygen=value / 100, helium=helium / 100, nitrogen=nitrogen / 100
        )
        self.emit_notifies()

    @GObject.Property(type=int)
    def helium(self):
        return round(100 * self.gas.fraction(Helium))

    @helium.setter
    def helium(self, value):
        oxygen = self.oxygen
        nitrogen = 100 - value - oxygen
        self.gas.set_blend(
            oxygen=oxygen / 100, helium=value / 100, nitrogen=nitrogen / 100
        )
        self.emit_notifies()

    def emit_notifies(self):
        self.emit("notify::name", self.find_property("name"))
        self.emit("notify::deco-mod", self.find_property("deco-mod"))
        self.emit("notify::bottom-mod", self.find_property("bottom-mod"))
        self.emit("notify::mnd", self.find_property("mnd"))

    @GObject.Property(type=str)
    def name(self):
        return self.gas.__repr__()

    @GObject.Property(type=str)
    def deco_mod(self):
        depth = self.gas.max_operating_depth
        depth = math.floor(depth / 3) * 3
        return f"{depth:.0f} m"

    @GObject.Property(type=str)
    def bottom_mod(self):
        depth = self.gas.max_operating_depth_at(1.4)
        return f"{depth:.0f} m"

    @GObject.Property(type=str)
    def mnd(self):
        depth = self.gas.max_narcotic_depth
        return f"{depth:.0f} m"


@Gtk.Template(resource_path="/io/github/slaclau/pydive/gtk/gas_blend_column_view.ui")
class GasBlendColumnView(Gtk.ColumnView):
    __gtype_name__ = "GasBlendColumnView"

    gases: Gio.ListStore

    def __init__(self):
        super().__init__()
        self.gases = Gio.ListStore.new(GasChoice)

        self.set_model(Gtk.NoSelection(model=self.gases))

        self.append_column(DeleteColumn(self.gases))
        self.append_column(LabelColumn("name", title="Gas"))
        self.append_column(IntEntryColumn("oxygen", title="Oxygen (%)", expand=True))
        self.append_column(IntEntryColumn("helium", title="Helium (%)", expand=True))
        self.append_column(LabelColumn("deco_mod", title="MOD (deco) (m)"))
        self.append_column(LabelColumn("bottom_mod", title="MOD (m)"))
        self.append_column(LabelColumn("mnd", title="MND (m)"))


@Gtk.Template(resource_path="/io/github/slaclau/pydive/gtk/gas_blend_view.ui")
class GasBlendView(Gtk.Box):
    __gtype_name__ = "GasBlendView"

    gas_blend_column_view: GasBlendColumnView = Gtk.Template.Child()

    def __init__(self):
        super().__init__()

    @property
    def gases(self):
        return self.gas_blend_column_view.gases

    @Gtk.Template.Callback()
    def add_gas(self, _):
        gas = GasChoice(GasBlend(oxygen=0.21, nitrogen=0.79))
        self.gases.append(gas)
