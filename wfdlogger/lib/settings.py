"""
K6GTE, Settings Dialog Class
Email: michael.bridak@gmail.com
GPL V3
"""
# pylint: disable=c-extension-no-member

import logging
import sys
import os
import pkgutil
from json import dumps, loads
from PyQt5 import QtWidgets, uic

if __name__ == "__main__":
    print("I'm not the program you are looking for.")


class Settings(QtWidgets.QDialog):
    """Settings dialog"""

    def __init__(self, parent=None):
        """initialize dialog"""
        super().__init__(parent)
        ui_path = os.path.dirname(pkgutil.get_loader("wfdlogger").get_filename())
        ui_path += "/data/settings.ui"
        uic.loadUi(ui_path, self)
        self.reference_preference = {
            "mycallsign": "",
            "myclass": "",
            "mysection": "",
            "power": "100",
            "usehamdb": False,
            "useqrz": False,
            "usehamqth": False,
            "lookupusername": "w1aw",
            "lookuppassword": "secret",
            "userigctld": False,
            "useflrig": False,
            "CAT_ip": "localhost",
            "CAT_port": 4532,
            "cloudlog": False,
            "cloudlogapi": "c01234567890123456789",
            "cloudlogurl": "https://www.cloudlog.com/Cloudlog/index.php/api",
            "cloudlogstationid": "",
            "usemarker": False,
            "markerfile": ".xplanet/markers/ham",
            "cwtype": 0,
            "cwip": "localhost",
            "cwport": 6789,
            "altpower": False,
            "outdoors": False,
            "notathome": False,
            "satellite": False,
            "useserver": 0,
            "multicast_group": "224.1.1.1",
            "multicast_port": 2239,
            "interface_ip": "0.0.0.0",
            "send_n1mm_packets": False,
            "n1mm_station_name": "20M CW Tent",
            "n1mm_operator": "Bernie",
            "n1mm_ip": "127.0.0.1",
            "n1mm_radioport": 12060,
            "n1mm_contactport": 12061,
            "n1mm_lookupport": 12060,
            "n1mm_scoreport": 12062,
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
            self.connect_to_server.setChecked(bool(self.preference.get("useserver")))
            self.multicast_group.setText(self.preference.get("multicast_group"))
            self.multicast_port.setText(str(self.preference.get("multicast_port")))
            self.interface_ip.setText(self.preference.get("interface_ip"))

            self.send_n1mm_packets.setChecked(
                bool(self.preference["send_n1mm_packets"])
            )
            self.n1mm_station_name.setText(self.preference["n1mm_station_name"])
            self.n1mm_operator.setText(self.preference["n1mm_operator"])
            self.n1mm_ip.setText(self.preference.get("n1mm_ip"))
            self.n1mm_radioport.setText(str(self.preference["n1mm_radioport"]))
            self.n1mm_contactport.setText(str(self.preference["n1mm_contactport"]))
            self.n1mm_lookupport.setText(str(self.preference["n1mm_lookupport"]))
            self.n1mm_scoreport.setText(str(self.preference["n1mm_scoreport"]))

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
        self.preference["useserver"] = self.connect_to_server.isChecked()
        self.preference["multicast_group"] = self.multicast_group.text()
        self.preference["multicast_port"] = self.multicast_port.text()
        self.preference["interface_ip"] = self.interface_ip.text()

        self.preference["send_n1mm_packets"] = self.send_n1mm_packets.isChecked()
        self.preference["n1mm_station_name"] = self.n1mm_station_name.text()
        self.preference["n1mm_operator"] = self.n1mm_operator.text()
        self.preference["n1mm_ip"] = self.n1mm_ip.text()
        self.preference["n1mm_radioport"] = self.n1mm_radioport.text()
        self.preference["n1mm_contactport"] = self.n1mm_contactport.text()
        self.preference["n1mm_lookupport"] = self.n1mm_lookupport.text()
        self.preference["n1mm_scoreport"] = self.n1mm_scoreport.text()

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
