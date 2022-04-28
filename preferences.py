"""Class to store preferences in a json file."""
import logging
import os
from json import dumps, loads


class Preferences:
    """Process preferences"""

    def __init__(self) -> None:
        """initialize preferences"""
        self.preference = {
            "mycallsign": "",
            "myclass": "",
            "mysection": "",
            "power": "0",
            "usehamdb": 0,
            "useqrz": 0,
            "usehamqth": 0,
            "lookupusername": "",
            "lookuppassword": "",
            "userigctld": 0,
            "useflrig": 0,
            "CAT_ip": "localhost",
            "CAT_port": 12345,
            "cloudlog": 0,
            "cloudlogapi": "c01234567890123456789",
            "cloudlogurl": "https://www.cloudlog.com/Cloudlog/index.php/api",
            "cloudlogstationid": "",
            "altpower": 0,
            "outdoors": 0,
            "notathome": 0,
            "satellite": 0,
        }

    def writepreferences(self) -> None:
        """
        Write preferences to json file.
        """
        try:
            logging.info("writepreferences:")
            with open(
                "./wfd_preferences.json", "wt", encoding="utf-8"
            ) as file_descriptor:
                file_descriptor.write(dumps(self.preference, indent=4))
        except IOError as exception:
            logging.critical("writepreferences: %s", exception)

    def readpreferences(self) -> None:
        """
        Reads preferences from json file.
        """
        logging.info("readpreferences:")
        try:
            if os.path.exists("./wfd_preferences.json"):
                with open(
                    "./wfd_preferences.json", "rt", encoding="utf-8"
                ) as file_descriptor:
                    self.preference = loads(file_descriptor.read())
            else:
                with open(
                    "./wfd_preferences.json", "wt", encoding="utf-8"
                ) as file_descriptor:
                    file_descriptor.write(dumps(self.preference, indent=4))
        except IOError as exception:
            logging.critical("readpreferences: %s", exception)
