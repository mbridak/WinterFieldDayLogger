"""Settings Dialog Class"""

import logging
import sys
import os
from json import dumps, loads
from PyQt5 import QtWidgets, uic


class Settings(QtWidgets.QDialog):
    """Settings dialog"""

    def __init__(self, parent=None):
        """initialize dialog"""
        super().__init__(parent)
        uic.loadUi(self.relpath("data/settings.ui"), self)
        self.reference_preference = {
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
        self.buttonBox.accepted.connect(self.save_changes)
        self.preference = None
        self.setup()

    def setup(self):
        """setup dialog"""
        with open("./wfd_preferences.json", "rt", encoding="utf-8") as file_descriptor:
            self.preference = loads(file_descriptor.read())
            logging.info("reading: %s", self.preference)
            self.useqrz_radioButton.setChecked(bool(self.preference["useqrz"]))
            self.usehamdb_radioButton.setChecked(bool(self.preference["usehamdb"]))
            self.usehamqth_radioButton.setChecked(bool(self.preference["usehamqth"]))
            self.lookup_user_name_field.setText(self.preference["lookupusername"])
            self.lookup_password_field.setText(self.preference["lookuppassword"])
            self.cloudlogapi_field.setText(self.preference["cloudlogapi"])
            self.cloudlogurl_field.setText(self.preference["cloudlogurl"])
            self.rigcontrolip_field.setText(self.preference["CAT_ip"])
            self.rigcontrolport_field.setText(str(self.preference["CAT_port"]))
            self.usecloudlog_checkBox.setChecked(bool(self.preference["cloudlog"]))
            self.userigctld_radioButton.setChecked(bool(self.preference["userigctld"]))
            self.useflrig_radioButton.setChecked(bool(self.preference["useflrig"]))
            self.markerfile_field.setText(self.preference["markerfile"])
            self.generatemarker_checkbox.setChecked(bool(self.preference["usemarker"]))
            self.cwip_field.setText(self.preference["cwip"])
            self.cwport_field.setText(str(self.preference["cwport"]))
            self.usecwdaemon_radioButton.setChecked(
                bool(self.preference["cwtype"] == 1)
            )
            self.usepywinkeyer_radioButton.setChecked(
                bool(self.preference["cwtype"] == 2)
            )

    @staticmethod
    def relpath(filename: str) -> str:
        """
        If the program is packaged with pyinstaller,
        this is needed since all files will be in a temp
        folder during execution.
        """
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            base_path = getattr(sys, "_MEIPASS")
        else:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, filename)

    def save_changes(self):
        """
        Write preferences to json file.
        """

        self.preference["useqrz"] = self.useqrz_radioButton.isChecked()
        self.preference["usehamdb"] = self.usehamdb_radioButton.isChecked()
        self.preference["usehamqth"] = self.usehamqth_radioButton.isChecked()
        self.preference["lookupusername"] = self.lookup_user_name_field.text()
        self.preference["lookuppassword"] = self.lookup_password_field.text()
        self.preference["cloudlog"] = self.usecloudlog_checkBox.isChecked()
        self.preference["cloudlogapi"] = self.cloudlogapi_field.text()
        self.preference["cloudlogurl"] = self.cloudlogurl_field.text()
        self.preference["CAT_ip"] = self.rigcontrolip_field.text()
        self.preference["CAT_port"] = int(self.rigcontrolport_field.text())
        self.preference["userigctld"] = self.userigctld_radioButton.isChecked()
        self.preference["useflrig"] = self.useflrig_radioButton.isChecked()
        self.preference["markerfile"] = self.markerfile_field.text()
        self.preference["usemarker"] = self.generatemarker_checkbox.isChecked()
        self.preference["cwip"] = self.cwip_field.text()
        self.preference["cwport"] = int(self.cwport_field.text())
        self.preference["cwtype"] = 0
        if self.usecwdaemon_radioButton.isChecked():
            self.preference["cwtype"] = 1
        if self.usepywinkeyer_radioButton.isChecked():
            self.preference["cwtype"] = 2
        try:
            logging.info("save_changes:")
            with open(
                "./wfd_preferences.json", "wt", encoding="utf-8"
            ) as file_descriptor:
                file_descriptor.write(dumps(self.preference, indent=4))
                logging.info("writing: %s", self.preference)
        except IOError as exception:
            logging.critical("save_changes: %s", exception)

    def readpreferences(self) -> None:
        """
        Reads preferences from json file.
        """
        logging.info("readpreferences:")
        try:
            if os.path.exists("./wfd_preferences.json"):
                logging.info("Reading Preference:")
                with open(
                    "./wfd_preferences.json", "rt", encoding="utf-8"
                ) as file_descriptor:
                    self.preference = loads(file_descriptor.read())
                    logging.info("%s", self.preference)
            else:
                with open(
                    "./wfd_preferences.json", "wt", encoding="utf-8"
                ) as file_descriptor:
                    file_descriptor.write(dumps(self.reference_preference, indent=4))
                    self.preference = self.reference_preference
        except IOError as exception:
            logging.critical("readpreferences: %s", exception)

    def writepreferences(self) -> None:
        """
        Write preferences to json file.
        """
        try:
            logging.info("writepreferences: %s", self.preference)
            with open(
                "./wfd_preferences.json", "wt", encoding="utf-8"
            ) as file_descriptor:
                file_descriptor.write(dumps(self.preference, indent=4))
        except IOError as exception:
            logging.critical("writepreferences: %s", exception)
