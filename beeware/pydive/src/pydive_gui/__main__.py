import logging

from pydive_gui.app import main

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main().main_loop()
