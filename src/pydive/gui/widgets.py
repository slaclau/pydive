import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GObject


class IntEntryBuffer(Gtk.EntryBuffer):
    def __init__(self):
        super().__init__()

    def do_insert_text(self, position, new_text, length):
        if new_text.isdigit():
            return Gtk.EntryBuffer.do_insert_text(
                self, position, new_text, len(new_text)
            )

        return position


class IntEntryColumn(Gtk.ColumnViewColumn):
    def __init__(self, attribute: str, **kwargs):
        super().__init__(**kwargs)
        self.attribute = attribute

        def entry_bind_function(_, item: Gtk.ListItem):
            entry = Gtk.Entry(buffer=IntEntryBuffer())
            entry.set_text(str(item.get_item().__getattribute__(self.attribute)))
            item.set_child(entry)

            item.get_item().bind_property(
                self.attribute,
                entry,
                "text",
                GObject.BindingFlags.BIDIRECTIONAL,
                lambda _, val: str(val),
                lambda _, val: int(val),
            )

        factory = Gtk.SignalListItemFactory()
        factory.connect("bind", entry_bind_function)
        self.set_factory(factory)


class IntLabelColumn(Gtk.ColumnViewColumn):
    def __init__(self, attribute: str, **kwargs):
        super().__init__(**kwargs)
        self.attribute = attribute

        def label_bind_function(_, item: Gtk.ListItem):
            label = Gtk.Label(label=item.get_item().__getattribute__(self.attribute))
            item.set_child(label)

            item.get_item().bind_property(
                self.attribute,
                label,
                "label",
                GObject.BindingFlags.DEFAULT,
                lambda _, val: str(val),
                lambda _, val: int(val),
            )

        factory = Gtk.SignalListItemFactory()
        factory.connect("bind", label_bind_function)
        self.set_factory(factory)


class LabelColumn(Gtk.ColumnViewColumn):
    def __init__(self, attribute: str, **kwargs):
        super().__init__(**kwargs)
        self.attribute = attribute

        def label_bind_function(_, item: Gtk.ListItem):
            label = Gtk.Label(label=item.get_item().__getattribute__(self.attribute))
            item.set_child(label)

            item.get_item().bind_property(
                self.attribute,
                label,
                "label",
                GObject.BindingFlags.DEFAULT,
            )

        factory = Gtk.SignalListItemFactory()
        factory.connect("bind", label_bind_function)
        self.set_factory(factory)


class DeleteColumn(Gtk.ColumnViewColumn):
    def __init__(self, list: Gio.ListStore):
        super().__init__()

        def delete_bind_function(_, item: Gtk.ListItem):
            button = Gtk.Button(icon_name="trash-symbolic")
            item.set_child(button)

            found, position = list.find(item.get_item())

            def delete_function(_):
                list.remove(position)
                if position < list.get_n_items():
                    next_item = list[position]
                    if hasattr(next_item, "update"):
                        next_item.update()

            if found:
                button.connect("clicked", delete_function)
            else:
                raise IndexError

        factory = Gtk.SignalListItemFactory()
        factory.connect("bind", delete_bind_function)
        self.set_factory(factory)
