import logging

import gi

from pydive.gas import GasBlend, Oxygen, Helium
from pydive.models.gas_consumption import Cylinder

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, GObject

logger = logging.getLogger(__name__)


@Gtk.Template(resource_path="/io/github/slaclau/pydive/gtk/gas_blender.ui")
class GasBlenderDialog(Adw.PreferencesDialog):
    __gtype_name__ = "GasBlenderDialog"


@Gtk.Template(resource_path="/io/github/slaclau/pydive/gtk/gas_blender_widget.ui")
class GasBlenderWidget(Adw.Bin):
    __gtype_name__ = "GasBlenderWidget"

    initial_gas: "GasConfigurator" = Gtk.Template.Child()
    desired_gas: "GasConfigurator" = Gtk.Template.Child()
    topup_gas_1: "GasConfigurator" = Gtk.Template.Child()
    topup_gas_2: "GasConfigurator" = Gtk.Template.Child()
    topup_gas_3: "GasConfigurator" = Gtk.Template.Child()

    initial_volume_adjustment: "Gtk.SpinButton" = Gtk.Template.Child()
    initial_pressure_adjustment: "Gtk.SpinButton" = Gtk.Template.Child()
    desired_pressure_adjustment: "Gtk.SpinButton" = Gtk.Template.Child()

    buffer: Gtk.TextBuffer = Gtk.Template.Child()

    def __init__(self):
        self.topup_gas_1.set_gas(GasBlend(oxygen=1))
        self.topup_gas_2.set_gas(GasBlend(helium=1))

        self.initial_gas.connect("gas-changed", self.on_gas_changed)
        self.desired_gas.connect("gas-changed", self.on_gas_changed)
        self.topup_gas_1.connect("gas-changed", self.on_gas_changed)
        self.topup_gas_2.connect("gas-changed", self.on_gas_changed)
        self.topup_gas_3.connect("gas-changed", self.on_gas_changed)

        self.initial_volume_adjustment.connect("value-changed", self.on_gas_changed)
        self.initial_pressure_adjustment.connect("value-changed", self.on_gas_changed)
        self.desired_pressure_adjustment.connect("value-changed", self.on_gas_changed)

        self.on_gas_changed(None)

    def on_gas_changed(self, obj):
        logger.debug(f"on_gas_changed called with object {obj}")

        start_cylinder = Cylinder(
            self.initial_gas.gas,
            self.initial_volume_adjustment.get_value(),
            self.initial_pressure_adjustment.get_value(),
        )
        desired_cylinder = Cylinder(
            self.desired_gas.gas,
            self.initial_volume_adjustment.get_value(),
            self.desired_pressure_adjustment.get_value(),
        )

        try:
            blend = desired_cylinder.compute_blend(
                [self.topup_gas_1.gas, self.topup_gas_2.gas, self.topup_gas_3.gas],
                start=start_cylinder,
            )

            self.buffer.set_text("")

            for gas, volume, result in blend:
                string = f"Add {gas.__repr__()} to cylinder to {result.pressure:.0f} bar\n  to obtain {result.gas.__repr__()}\n"
                self.buffer.insert(self.buffer.get_end_iter(), string)
        except ValueError as e:
            self.buffer.set_text(str(e))

        return True


@Gtk.Template(resource_path="/io/github/slaclau/pydive/gtk/gas_configurator.ui")
class GasConfigurator(Adw.PreferencesGroup):
    __gtype_name__ = "GasConfigurator"

    gas: GasBlend

    oxygen_adjustment: Gtk.Adjustment = Gtk.Template.Child()
    helium_adjustment: Gtk.Adjustment = Gtk.Template.Child()
    nitrogen_adjustment: Gtk.Adjustment = Gtk.Template.Child()

    @GObject.Signal(name="gas-changed")
    def gas_changed(self):
        logger.debug("gas-changed")

    def __init__(self):
        super().__init__()
        self._update_nitrogen_adjustment()
        self._update_gas_blend()

    def set_gas(self, gas: GasBlend):
        self.oxygen_adjustment.set_value(100 * gas.fraction(Oxygen))
        self.helium_adjustment.set_value(100 * gas.fraction(Helium))

    @Gtk.Template.Callback()
    def on_oxygen_changed(self, adjustment):
        logger.debug(f"on_oxygen_changed called with {adjustment}")
        self.helium_adjustment.set_upper(100 - adjustment.get_value())
        self._update_nitrogen_adjustment()
        self._update_gas_blend()

    @Gtk.Template.Callback()
    def on_helium_changed(self, adjustment):
        logger.debug(f"on_helium_changed called with {adjustment}")
        self.oxygen_adjustment.set_upper(100 - adjustment.get_value())
        self._update_nitrogen_adjustment()
        self._update_gas_blend()

    def _update_nitrogen_adjustment(self):
        self.nitrogen_adjustment.set_value(
            100
            - self.oxygen_adjustment.get_value()
            - self.helium_adjustment.get_value()
        )

    def _update_gas_blend(self):
        oxygen_fraction = round(self.oxygen_adjustment.get_value() / 100, 2)
        helium_fraction = round(self.helium_adjustment.get_value() / 100, 2)
        nitrogen_fraction = round(self.nitrogen_adjustment.get_value() / 100, 2)

        self.gas = GasBlend(
            oxygen=oxygen_fraction, helium=helium_fraction, nitrogen=nitrogen_fraction
        )
        logger.debug(f"updated gas blend to {self.gas}")
        self.set_description(self.gas.__repr__())
        self.emit("gas-changed")
