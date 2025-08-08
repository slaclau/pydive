import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk


class PyDiveApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(application_id="io.github.slaclau.pydive", **kwargs)

    def do_startup(self):
        Adw.Application.do_startup(self)
        logging.getLogger("pydive.gui").setLevel(logging.DEBUG)

    def do_activate(self):
        self.set_accels_for_action("win.show-help", ["F1"])

        win = self.props.active_window

        if not win:
            from pydive.gui.window import PyDiveWindow

            win = PyDiveWindow(application=self)
        win.present()
