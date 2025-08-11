import gi

from pydive.gui.gas_blend_view import GasChoice
from pydive.gui.widgets import DeleteColumn, IntEntryColumn, IntLabelColumn

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GObject, Gtk


class DivePoint(GObject.GObject):
    _duration: int
    _depth: int
    _runtime: int = 0

    def __init__(self, list_model, depth, duration, gas):
        super().__init__()
        self.list_model: Gio.ListStore = list_model

        self.connect("notify::duration", lambda item, _: self.update())

        self.depth = depth
        self.duration = duration
        self.gas = gas

    def update(self):
        found, from_pos = self.list_model.find(self)
        if not found:
            self.runtime = self.duration
        elif from_pos == 0:
            self.list_model[0].runtime = self.list_model[0].duration
        elif from_pos > 0:
            self.list_model[from_pos].runtime = (
                self.list_model[from_pos - 1].runtime
                + self.list_model[from_pos].duration
            )
        for i in range(from_pos + 1, len(self.list_model)):
            self.list_model[i].runtime = (
                self.list_model[i - 1].runtime + self.list_model[i].duration
            )

    @GObject.Property(type=int)
    def depth(self):
        return self._depth

    @depth.setter
    def depth(self, value):
        self._depth = value
        self.emit("changed")

    @GObject.Property(type=int)
    def duration(self):
        return self._duration

    @duration.setter
    def duration(self, value):
        self._duration = value
        self.emit("changed")

    @GObject.Property(type=int)
    def runtime(self):
        return self._runtime

    @runtime.setter
    def runtime(self, value):
        self._runtime = value

    @GObject.Property(type=object)
    def gas(self):
        return self._gas

    @gas.setter
    def gas(self, value):
        self._gas = value
        self.emit("changed")

    @GObject.Signal
    def changed(self):
        pass


@Gtk.Template(resource_path="/io/github/slaclau/pydive/gtk/dive_point_column_view.ui")
class DivePointColumnView(Gtk.ColumnView):
    __gtype_name__ = "DivePointColumnView"

    available_gases: Gio.ListStore
    dive_points: Gio.ListStore

    def __init__(self):
        super().__init__()
        self.dive_points = Gio.ListStore.new(DivePoint)

        self.set_model(Gtk.NoSelection(model=self.dive_points))

        self.append_column(DeleteColumn(self.dive_points))
        self.append_column(IntEntryColumn("depth", title="Depth (m)"))
        self.append_column(IntEntryColumn("duration", title="Duration (min)"))
        self.append_column(IntLabelColumn("runtime", title="Runtime (min)"))

        def gas_bind_function(_, item: Gtk.ListItem):
            drop_down_factory = Gtk.SignalListItemFactory()

            def bind_function(_, item: Gtk.ListItem):
                gas_choice = item.get_item()
                assert isinstance(gas_choice, GasChoice)
                label_text = gas_choice.name
                label = Gtk.Label(label=label_text, halign=Gtk.Align.START)
                item.set_child(label)

            drop_down_factory.connect("bind", bind_function)
            drop_down = Gtk.DropDown(
                model=self.available_gases, factory=drop_down_factory
            )
            item.set_child(drop_down)

        gas_factory = Gtk.SignalListItemFactory()
        gas_factory.connect("bind", gas_bind_function)
        gas_column = Gtk.ColumnViewColumn(expand=True, title="Gas", factory=gas_factory)
        self.append_column(gas_column)


@Gtk.Template(resource_path="/io/github/slaclau/pydive/gtk/dive_point_view.ui")
class DivePointView(Gtk.Box):
    __gtype_name__ = "DivePointView"

    dive_point_column_view: DivePointColumnView = Gtk.Template.Child()

    def __init__(self):
        super().__init__()

    @property
    def dive_points(self):
        return self.dive_point_column_view.dive_points

    @property
    def available_gases(self):
        return self.dive_point_column_view.available_gases

    @available_gases.setter
    def available_gases(self, value):
        self.dive_point_column_view.available_gases = value

    @Gtk.Template.Callback()
    def add_dive_point(self, _):
        dive_point = DivePoint(self.dive_points, 0, 0, self.available_gases[0])
        dive_point.connect("changed", lambda _: self.emit("points-changed"))
        self.dive_points.append(dive_point)
        dive_point.update()

    @GObject.Signal
    def points_changed(self):
        print("points changed")
