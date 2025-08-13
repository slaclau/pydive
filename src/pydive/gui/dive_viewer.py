from plotly.subplots import make_subplots
import pandas as pd

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Adw, Gtk
from gi.repository.WebKit import WebView

import pydive.dive


@Gtk.Template(resource_path="/io/github/slaclau/pydive/gtk/dive_viewer.ui")
class DiveViewer(Adw.Bin):
    __gtype_name__ = "DiveViewer"

    web_view: WebView = Gtk.Template.Child()

    def display_dive(self, dive: pydive.dive.Dive):
        print(dive.markdown)
        self.web_view.load_plain_text(dive.markdown)

        funcs = {
            "depth": lambda dive: dive.depth,
            "gf": lambda dive: dive.decompression_model.gf(dive.depth),
            "ceiling": lambda dive: dive.decompression_model.ceiling(),
            "loading": lambda dive: dive.decompression_model.loading(dive.depth),
            "ceilings": lambda dive: dive.decompression_model.ceilings(),
        }
        df = dive.reinterpolate_dive().custom_df(funcs)
        df = pd.concat(
            [
                df,
                pd.DataFrame(
                    df.ceilings.to_list(),
                    columns=[f"ceiling_{i}" for i in range(0, 16)],
                ),
            ],
            axis=1,
        )

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.update_layout(hovermode="x unified")
        fig.update_yaxes(autorange="reversed")
        fig.add_scatter(x=df.time, y=df.depth, name="Depth")
        fig.add_scatter(x=df.time, y=df.gf, secondary_y=True, name="Gradient Factor")
        fig.add_scatter(x=df.time, y=df.ceiling, name="Ceiling")
        fig.add_scatter(x=df.time, y=df.loading, secondary_y=True, name="Loading")

        for i in range(0, 16):
            fig.add_scatter(
                x=df.time,
                y=df[f"ceiling_{i}"],
                name=f"Ceiling in {i}",
                fill="tozeroy",
                line_color="green",
            )

        self.web_view.load_html(fig.to_html())
