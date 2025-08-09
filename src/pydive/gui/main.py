import importlib.resources
import logging
import os
import sys

import gi
from gi.repository import Gio

from pydive.gui.app import PyDiveApp

logger = logging.getLogger(__name__)


def main():
    app = PyDiveApp()

    resource = None

    if os.path.isfile(
        importlib.resources.files("pydive").joinpath("data/resources.gresource")
    ):
        resource = Gio.resource_load(
            str(
                importlib.resources.files("pydive").joinpath("data/resources.gresource")
            )
        )
        logger.debug("Loading gresource from package directory")
    if resource is None:
        logger.warning("No gresource located, unable to determine install type")
        sys.exit(1)
    else:
        Gio.Resource._register(resource)

    app.run(sys.argv)


if __name__ == "__main__":
    logging.basicConfig()
    main()
