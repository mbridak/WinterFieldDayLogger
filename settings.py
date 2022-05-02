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
        uic.loadUi(self.relpath("settings.ui"), self)
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

        # self.mycallsign = EditTextField(self.screen, 2, 11, 14, curses.A_UNDERLINE)
        # self.mycallsign.set_text(preference["mycallsign"])
        # self.myclass = EditTextField(self.screen, 2, 36, 3, curses.A_UNDERLINE)
        # self.myclass.set_text(preference["myclass"])
        # self.mysection = EditTextField(self.screen, 2, 52, 3, curses.A_UNDERLINE)
        # self.mysection.set_text(preference["mysection"])
        # self.power = EditTextField(self.screen, 2, 70, 3, curses.A_UNDERLINE)
        # self.power.set_text(preference["power"])
        # self.usehamdb = EditTextField(self.screen, 5, 14, 1, curses.A_UNDERLINE)
        # self.usehamdb.set_bool(True)
        # self.usehamdb.set_state(bool(preference["usehamdb"]))
        # self.useqrz = EditTextField(self.screen, 5, 38, 1, curses.A_UNDERLINE)
        # self.useqrz.set_bool(True)
        # self.useqrz.set_state(bool(preference["useqrz"]))
        # self.usehamqth = EditTextField(self.screen, 5, 67, 1, curses.A_UNDERLINE)
        # self.usehamqth.set_bool(True)
        # self.usehamqth.set_state(bool(preference["usehamqth"]))
        # self.lookupusername = EditTextField(self.screen, 6, 12, 15, curses.A_UNDERLINE)
        # self.lookupusername.lowercase(True)
        # self.lookupusername.set_text(preference["lookupusername"])
        # self.lookuppassword = EditTextField(self.screen, 6, 38, 20, curses.A_UNDERLINE)
        # self.lookuppassword.lowercase(True)
        # self.lookuppassword.set_text(preference["lookuppassword"])
        # self.userigctld = EditTextField(self.screen, 9, 16, 1, curses.A_UNDERLINE)
        # self.userigctld.set_bool(True)
        # self.userigctld.set_state(bool(preference["userigctld"]))
        # self.useflrig = EditTextField(self.screen, 9, 35, 1, curses.A_UNDERLINE)
        # self.useflrig.set_bool(True)
        # self.useflrig.set_state(bool(preference["useflrig"]))
        # self.CAT_ip = EditTextField(self.screen, 10, 19, 20, curses.A_UNDERLINE)
        # self.CAT_ip.lowercase(True)
        # self.CAT_ip.set_text(preference["CAT_ip"])
        # self.CAT_port = EditTextField(self.screen, 10, 50, 5, curses.A_UNDERLINE)
        # self.CAT_port.set_text(str(preference["CAT_port"]))
        # self.cloudlog = EditTextField(self.screen, 13, 17, 1, curses.A_UNDERLINE)
        # self.cloudlog.set_bool(True)
        # self.cloudlog.set_state(bool(preference["cloudlog"]))
        # self.cloudlogapi = EditTextField(self.screen, 14, 16, 25, curses.A_UNDERLINE)
        # self.cloudlogapi.lowercase(True)
        # self.cloudlogapi.set_text(preference["cloudlogapi"])
        # self.cloudlogurl = EditTextField(self.screen, 15, 16, 58, curses.A_UNDERLINE)
        # self.cloudlogurl.lowercase(True)
        # self.cloudlogurl.set_text(preference["cloudlogurl"])
        # self.cloudlogstationid = EditTextField(
        #     self.screen, 16, 23, 20, curses.A_UNDERLINE
        # )
        # self.cloudlogstationid.lowercase(True)
        # self.cloudlogstationid.set_text(preference["cloudlogstationid"])
        # self.altpower = EditTextField(self.screen, 19, 14, 1, curses.A_UNDERLINE)
        # self.altpower.set_bool(True)
        # self.outdoors = EditTextField(self.screen, 19, 31, 1, curses.A_UNDERLINE)
        # self.outdoors.set_bool(True)
        # self.notathome = EditTextField(self.screen, 19, 50, 1, curses.A_UNDERLINE)
        # self.notathome.set_bool(True)
        # self.satellite = EditTextField(self.screen, 19, 67, 1, curses.A_UNDERLINE)
        # self.satellite.set_bool(True)
        # self.altpower.set_state(bool(preference["altpower"]))
        # self.outdoors.set_state(bool(preference["outdoors"]))
        # self.notathome.set_state(bool(preference["notathome"]))
        # self.satellite.set_state(bool(preference["satellite"]))

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
