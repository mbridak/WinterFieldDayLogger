#!/usr/bin/env python3
"""
K6GTE Winter Field Day logger
Email: michael.bridak@gmail.com
GPL V3
"""

# pylint: disable=invalid-name

# Nothing to see here move along.
# xplanet -body earth -window -longitude -117 -latitude 38 -config Default -projection azmithal -radius 200 -wait 5

# from types import NoneType
# import xmlrpc.client
from math import radians, sin, cos, atan2, sqrt, asin, pi
import sys
import sqlite3
import socket
import os
import logging

from json import dumps, loads
from datetime import datetime


# from sqlite3 import Error
from pathlib import Path
from shutil import copyfile

# from xmlrpc.client import ServerProxy, Error
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QFontDatabase

# from bs4 import BeautifulSoup as bs
import requests

from settings import Settings
from database import DataBase
from lookup import HamDBlookup, HamQTH, QRZlookup
from cat_interface import CAT
from cwinterface import CW
from version import __version__


def relpath(filename: str) -> str:
    """
    Checks to see if program has been packaged with pyinstaller.
    If so base dir is in a temp folder.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = getattr(sys, "_MEIPASS")
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, filename)


def load_fonts_from_dir(directory: str) -> set:
    """
    Well it loads fonts from a directory...
    """
    font_families = set()
    for _fi in QDir(directory).entryInfoList(["*.ttf", "*.woff", "*.woff2"]):
        _id = QFontDatabase.addApplicationFont(_fi.absoluteFilePath())
        font_families |= set(QFontDatabase.applicationFontFamilies(_id))
    return font_families


class QSOEdit(QtCore.QObject):
    """
    Custom qt event signal used when qso edited or deleted.
    """

    lineChanged = QtCore.pyqtSignal()


class MainWindow(QtWidgets.QMainWindow):
    """
    The Main Window with all the clicky bits
    """

    database = "WFD.db"
    mycall = ""
    myclass = ""
    mysection = ""
    power = "100"
    band = "40"
    mode = "CW"
    qrp = False
    highpower = False
    bandmodemult = 0
    altpower = False
    outdoors = False
    notathome = False
    satellite = False
    cwcontacts = "0"
    phonecontacts = "0"
    digitalcontacts = "0"
    score = 0
    secPartial = {}
    secName = {}
    secState = {}
    scp = []
    wrkdsections = []
    linetopass = ""
    bands = ("160", "80", "60", "40", "20", "15", "10", "6", "2")
    dfreq = {
        "160": "1.830",
        "80": "3.530",
        "60": "5.340",
        "40": "7.030",
        "20": "14.030",
        "15": "21.030",
        "10": "28.030",
        "6": "50.030",
        "2": "144.030",
        "222": "222.030",
        "432": "432.030",
        "SAT": "0.0",
    }
    cloudlogapi = ""
    cloudlogurl = ""
    cloudlogauthenticated = False
    usecloudlog = False
    qrzurl = ""
    qrzpass = ""
    qrzname = ""
    useqrz = False
    usehamdb = True
    qrzsession = False
    rigctrlsocket = ""
    rigctrlhost = ""
    rigctrlport = ""
    rigonline = False
    userigctl = False
    flrig = False
    markerfile = ".xplanet/markers/ham"
    usemarker = False
    oldfreq = 0
    oldmode = 0
    oldrfpower = 0
    basescore = 0
    powermult = 0
    fkeys = dict()
    # keyerserver = "http://localhost:8000"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        uic.loadUi(self.relpath("main.ui"), self)
        # self.qrz = None
        self.db = DataBase(self.database)
        self.listWidget.itemDoubleClicked.connect(self.qsoclicked)
        self.altpowerButton.clicked.connect(self.claim_alt_power)
        self.outdoorsButton.clicked.connect(self.claim_outdoors)
        self.notathomeButton.clicked.connect(self.claim_not_at_home)
        self.satelliteButton.clicked.connect(self.claim_satellite)
        self.callsign_entry.textEdited.connect(self.calltest)
        self.class_entry.textEdited.connect(self.classtest)
        self.section_entry.textEdited.connect(self.sectiontest)
        self.callsign_entry.returnPressed.connect(self.log_contact)
        self.class_entry.returnPressed.connect(self.log_contact)
        self.section_entry.returnPressed.connect(self.log_contact)
        self.mycallEntry.textEdited.connect(self.changemycall)
        self.myclassEntry.textEdited.connect(self.changemyclass)
        self.mysectionEntry.textEdited.connect(self.changemysection)
        self.band_selector.activated.connect(self.changeband)
        self.mode_selector.activated.connect(self.changemode)
        self.power_selector.valueChanged.connect(self.changepower)
        self.callsign_entry.editingFinished.connect(self.dup_check)
        self.section_entry.textEdited.connect(self.section_check)
        self.genLogButton.clicked.connect(self.generate_logs)
        self.radio_grey = QtGui.QPixmap(self.relpath("icon/radio_grey.png"))
        self.radio_red = QtGui.QPixmap(self.relpath("icon/radio_red.png"))
        self.radio_green = QtGui.QPixmap(self.relpath("icon/radio_green.png"))
        self.cloud_grey = QtGui.QPixmap(self.relpath("icon/cloud_grey.png"))
        self.cloud_red = QtGui.QPixmap(self.relpath("icon/cloud_red.png"))
        self.cloud_green = QtGui.QPixmap(self.relpath("icon/cloud_green.png"))
        self.radio_icon.setPixmap(self.radio_grey)
        self.cloudlog_icon.setPixmap(self.cloud_grey)
        self.QRZ_icon.setStyleSheet("color: rgb(136, 138, 133);")
        self.settingsbutton.clicked.connect(self.settingspressed)
        self.F1.clicked.connect(self.sendf1)
        self.F2.clicked.connect(self.sendf2)
        self.F3.clicked.connect(self.sendf3)
        self.F4.clicked.connect(self.sendf4)
        self.F5.clicked.connect(self.sendf5)
        self.F6.clicked.connect(self.sendf6)
        self.F7.clicked.connect(self.sendf7)
        self.F8.clicked.connect(self.sendf8)
        self.F9.clicked.connect(self.sendf9)
        self.F10.clicked.connect(self.sendf10)
        self.F11.clicked.connect(self.sendf11)
        self.F12.clicked.connect(self.sendf12)
        self.contactlookup = {
            "call": "",
            "grid": "",
            "bearing": "",
            "name": "",
            "nickname": "",
            "error": "",
            "distance": "",
        }
        self.preference = {
            "mycallsign": "",
            "myclass": "",
            "mysection": "",
            "power": "100",
            "usehamdb": 0,
            "useqrz": 0,
            "usehamqth": 0,
            "lookupusername": "w1aw",
            "lookuppassword": "secret",
            "userigctld": 0,
            "useflrig": 0,
            "CAT_ip": "localhost",
            "CAT_port": 4532,
            "cloudlog": 0,
            "cloudlogapi": "c01234567890123456789",
            "cloudlogurl": "https://www.cloudlog.com/Cloudlog/index.php/api",
            "cloudlogstationid": "",
            "usemarker": 0,
            "markerfile": ".xplanet/markers/ham",
            "cwtype": 0,
            "cwip": "localhost",
            "cwport": 6789,
            "altpower": 0,
            "outdoors": 0,
            "notathome": 0,
            "satellite": 0,
        }
        self.reference_preference = self.preference.copy()
        self.look_up = None
        self.cat_control = None
        self.cw = None
        self.readpreferences()
        self.radiochecktimer = QtCore.QTimer()
        self.radiochecktimer.timeout.connect(self.radio)
        self.radiochecktimer.start(1000)

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

    def clearcontactlookup(self):
        """clearout the contact lookup"""
        self.contactlookup["call"] = ""
        self.contactlookup["grid"] = ""
        self.contactlookup["name"] = ""
        self.contactlookup["nickname"] = ""
        self.contactlookup["error"] = ""
        self.contactlookup["distance"] = ""
        self.contactlookup["bearing"] = ""

    def lazy_lookup(self, acall: str):
        """El Lookup De Lazy"""
        if self.look_up:
            if acall == self.contactlookup["call"]:
                return

            self.contactlookup["call"] = acall
            (
                self.contactlookup["grid"],
                self.contactlookup["name"],
                self.contactlookup["nickname"],
                self.contactlookup["error"],
            ) = self.look_up.lookup(acall)
            if self.contactlookup["grid"] and self.mygrid:
                self.contactlookup["distance"] = self.distance(
                    self.mygrid, self.contactlookup["grid"]
                )
                self.contactlookup["bearing"] = self.bearing(
                    self.mygrid, self.contactlookup["grid"]
                )
            logging.info("%s", self.contactlookup)

    def distance(self, grid1: str, grid2: str) -> float:
        """
        Takes two maidenhead gridsquares and returns the distance between the two in kilometers.
        """
        lat1, lon1 = self.gridtolatlon(grid1)
        lat2, lon2 = self.gridtolatlon(grid2)
        return round(self.haversine(lon1, lat1, lon2, lat2))

    def bearing(self, grid1: str, grid2: str) -> float:
        """calculate bearing to contact"""
        lat1, lon1 = self.gridtolatlon(grid1)
        lat2, lon2 = self.gridtolatlon(grid2)
        lat1 = radians(lat1)
        lon1 = radians(lon1)
        lat2 = radians(lat2)
        lon2 = radians(lon2)
        londelta = lon2 - lon1
        why = sin(londelta) * cos(lat2)
        exs = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(londelta)
        brng = atan2(why, exs)
        brng *= 180 / pi

        if brng < 0:
            brng += 360

        return round(brng)

    @staticmethod
    def haversine(lon1, lat1, lon2, lat2):
        """
        Calculate the great circle distance in kilometers between two points
        on the earth (specified in decimal degrees)
        """
        # convert degrees to radians
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

        # haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        aye = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        cee = 2 * asin(sqrt(aye))
        arrgh = 6372.8  # Radius of earth in kilometers.
        return cee * arrgh

    def read_cw_macros(self) -> None:
        """
        Reads in the CW macros, firsts it checks to see if the file exists. If it does not,
        and this has been packaged with pyinstaller it will copy the default file from the
        temp directory this is running from... In theory.
        """

        if (
            getattr(sys, "frozen", False)
            and hasattr(sys, "_MEIPASS")
            and not Path("./cwmacros.txt").exists()
        ):
            logging.debug("read_cw_macros: copying default macro file.")
            copyfile(relpath("cwmacros.txt"), "./cwmacros.txt")
        with open("./cwmacros.txt", "r", encoding="utf-8") as file_descriptor:
            for line in file_descriptor:
                try:
                    fkey, buttonname, cwtext = line.split("|")
                    self.fkeys[fkey.strip()] = (buttonname.strip(), cwtext.strip())
                except ValueError:
                    break
        keys = self.fkeys.keys()
        if "F1" in keys:
            self.F1.setText(f"F1: {self.fkeys['F1'][0]}")
            self.F1.setToolTip(self.fkeys["F1"][1])
        if "F2" in keys:
            self.F2.setText(f"F2: {self.fkeys['F2'][0]}")
            self.F2.setToolTip(self.fkeys["F2"][1])
        if "F3" in keys:
            self.F3.setText(f"F3: {self.fkeys['F3'][0]}")
            self.F3.setToolTip(self.fkeys["F3"][1])
        if "F4" in keys:
            self.F4.setText(f"F4: {self.fkeys['F4'][0]}")
            self.F4.setToolTip(self.fkeys["F4"][1])
        if "F5" in keys:
            self.F5.setText(f"F5: {self.fkeys['F5'][0]}")
            self.F5.setToolTip(self.fkeys["F5"][1])
        if "F6" in keys:
            self.F6.setText(f"F6: {self.fkeys['F6'][0]}")
            self.F6.setToolTip(self.fkeys["F6"][1])
        if "F7" in keys:
            self.F7.setText(f"F7: {self.fkeys['F7'][0]}")
            self.F7.setToolTip(self.fkeys["F7"][1])
        if "F8" in keys:
            self.F8.setText(f"F8: {self.fkeys['F8'][0]}")
            self.F8.setToolTip(self.fkeys["F8"][1])
        if "F9" in keys:
            self.F9.setText(f"F9: {self.fkeys['F9'][0]}")
            self.F9.setToolTip(self.fkeys["F9"][1])
        if "F10" in keys:
            self.F10.setText(f"F10: {self.fkeys['F10'][0]}")
            self.F10.setToolTip(self.fkeys["F10"][1])
        if "F11" in keys:
            self.F11.setText(f"F11: {self.fkeys['F11'][0]}")
            self.F11.setToolTip(self.fkeys["F11"][1])
        if "F12" in keys:
            self.F12.setText(f"F12: {self.fkeys['F12'][0]}")
            self.F12.setToolTip(self.fkeys["F12"][1])

    def update_time(self) -> None:
        """
        Update local and UTC time on screen.
        """
        now = datetime.now().isoformat(" ")[5:19].replace("-", "/")
        utcnow = datetime.utcnow().isoformat(" ")[5:19].replace("-", "/")
        self.localtime.setText(now)
        self.utctime.setText(utcnow)

    def settingspressed(self) -> None:
        """
        Show settings dialog
        """
        settingsdialog = Settings(self)
        settingsdialog.exec()
        self.infobox.clear()
        self.look_up = None
        self.cat_control = None
        self.readpreferences()
        if self.preference["useqrz"]:
            self.look_up = QRZlookup(
                self.preference["lookupusername"], self.preference["lookuppassword"]
            )
        if self.preference["usehamdb"]:
            self.look_up = HamDBlookup()
        if self.preference["usehamqth"]:
            self.look_up = HamQTH(
                self.preference["lookupusername"],
                self.preference["lookuppassword"],
            )
        if self.preference["useflrig"]:
            self.cat_control = CAT(
                "flrig", self.preference["CAT_ip"], self.preference["CAT_port"]
            )
        if self.preference["userigctld"]:
            self.cat_control = CAT(
                "rigctld", self.preference["CAT_ip"], self.preference["CAT_port"]
            )

    def readpreferences(self):
        """
        Restore preferences if they exist, otherwise create some sane defaults.
        """
        try:
            if os.path.exists("./wfd_preferences.json"):
                with open(
                    "./wfd_preferences.json", "rt", encoding="utf-8"
                ) as file_descriptor:
                    self.preference = loads(file_descriptor.read())
                    logging.info("%s", self.preference)
            else:
                logging.info("No preference file. Writing preference.")
                with open(
                    "./wfd_preferences.json", "wt", encoding="utf-8"
                ) as file_descriptor:
                    self.preference = self.reference_preference.copy()
                    file_descriptor.write(dumps(self.preference, indent=4))
                    logging.info("%s", self.preference)
        except IOError as exception:
            logging.critical("Error: %s", exception)
        try:
            self.mycallEntry.setText(self.preference["mycallsign"])
            if self.preference["mycallsign"] != "":
                self.mycallEntry.setStyleSheet("border: 1px solid green;")
            self.myclassEntry.setText(self.preference["myclass"])
            if self.preference["myclass"] != "":
                self.myclassEntry.setStyleSheet("border: 1px solid green;")
            self.mysectionEntry.setText(self.preference["mysection"])
            if self.preference["mysection"] != "":
                self.mysectionEntry.setStyleSheet("border: 1px solid green;")

            self.power_selector.setValue(int(self.preference["power"]))

            self.cat_control = None
            if self.preference["useflrig"]:
                self.cat_control = CAT(
                    "flrig", self.preference["CAT_ip"], self.preference["CAT_port"]
                )
            if self.preference["userigctld"]:
                self.cat_control = CAT(
                    "rigctld", self.preference["CAT_ip"], self.preference["CAT_port"]
                )

            if self.preference["useqrz"]:
                self.look_up = QRZlookup(
                    self.preference["lookupusername"], self.preference["lookuppassword"]
                )
                self.callbook_icon.setText("QRZ")
                if self.look_up.session:
                    self.callbook_icon.setStyleSheet("color: rgb(128, 128, 0);")
                else:
                    self.callbook_icon.setStyleSheet("color: rgb(136, 138, 133);")

            if self.preference["usehamdb"]:
                self.look_up = HamDBlookup()
                self.callbook_icon.setText("HamDB")
                self.callbook_icon.setStyleSheet("color: rgb(128, 128, 0);")

            if self.preference["usehamqth"]:
                self.look_up = HamQTH(
                    self.preference["lookupusername"],
                    self.preference["lookuppassword"],
                )
                self.callbook_icon.setText("HamQTH")
                if self.look_up.session:
                    self.callbook_icon.setStyleSheet("color: rgb(128, 128, 0);")
                else:
                    self.callbook_icon.setStyleSheet("color: rgb(136, 138, 133);")

            self.cloudlogauth()

            if self.preference["cwtype"] == 0:
                self.cw = None
            else:
                self.cw = CW(
                    self.preference["cwtype"],
                    self.preference["cwip"],
                    self.preference["cwport"],
                )
        except KeyError as err:
            logging.warning("Corrupt preference, %s, loading clean version.", err)
            self.preference = self.reference_preference.copy()
            with open(
                "./wfd_preferences.json", "wt", encoding="utf-8"
            ) as file_descriptor:
                file_descriptor.write(dumps(self.preference, indent=4))
                logging.info("writing: %s", self.preference)

    def writepreferences(self):
        """
        Write preferences to json file.
        """
        try:
            with open(
                "./wfd_preferences.json", "wt", encoding="utf-8"
            ) as file_descriptor:
                file_descriptor.write(dumps(self.preference, indent=4))
                logging.info("writing: %s", self.preference)
        except IOError as exception:
            logging.critical("writepreferences: %s", exception)

    @staticmethod
    def has_internet():
        """
        Connect to a main DNS server to check connectivity.
        """
        try:
            socket.create_connection(("1.1.1.1", 53))
            return True
        except OSError:
            pass
        return False

    def cloudlogauth(self) -> None:
        """
        Check if user has valid Cloudlog API key.
        """
        self.cloudlog_icon.setPixmap(self.cloud_grey)
        self.cloudlogauthenticated = False
        if self.preference["cloudlog"]:
            try:
                self.cloudlog_icon.setPixmap(self.cloud_red)
                test = (
                    self.preference["cloudlogurl"]
                    + "/auth/"
                    + self.preference["cloudlogapi"]
                )
                result = requests.get(test, params={}, timeout=2.0)
                if result.status_code == 200 and result.text.find("<status>") > 0:
                    if (
                        result.text[
                            result.text.find("<status>")
                            + 8 : result.text.find("</status>")
                        ]
                        == "Valid"
                    ):
                        self.cloudlogauthenticated = True
                        self.cloudlog_icon.setPixmap(self.cloud_green)
                        logging.info("Cloudlog: Authenticated.")
                else:
                    logging.warning(
                        "%s Unable to authenticate.\n%s", result.status_code, test
                    )
            except requests.exceptions.RequestException as exception:
                self.infobox.insertPlainText(
                    f"****Cloudlog Auth Error:****\n{exception}\n"
                )
                logging.warning("Cloudlog: %s", exception)

    def getband(self, freq: str) -> str:
        """
        Convert a (string) frequency into a (string) band.
        Returns a (string) band.
        Returns a "0" if frequency is out of band.
        """
        logging.info("getband: %s %s", type(freq), freq)
        if freq.isnumeric():
            frequency = int(float(freq))
            if frequency > 1800000 and frequency < 2000000:
                return "160"
            if frequency > 3500000 and frequency < 4000000:
                return "80"
            if frequency > 5330000 and frequency < 5406000:
                return "60"
            if frequency > 7000000 and frequency < 7300000:
                return "40"
            if frequency > 10100000 and frequency < 10150000:
                return "30"
            if frequency > 14000000 and frequency < 14350000:
                return "20"
            if frequency > 18068000 and frequency < 18168000:
                return "17"
            if frequency > 21000000 and frequency < 21450000:
                return "15"
            if frequency > 24890000 and frequency < 24990000:
                return "12"
            if frequency > 28000000 and frequency < 29700000:
                return "10"
            if frequency > 50000000 and frequency < 54000000:
                return "6"
            if frequency > 144000000 and frequency < 148000000:
                return "2"
        else:
            return "0"

    @staticmethod
    def getmode(rigmode: str) -> str:
        """
        Change what rigctld returned for the mode to the cabrillo mode for logging.
        """
        if rigmode == "CW" or rigmode == "CWR":
            return "CW"
        if rigmode == "USB" or rigmode == "LSB" or rigmode == "FM" or rigmode == "AM":
            return "PH"
        return "DI"  # All else digital

    def setband(self, theband: str) -> None:
        """
        Takes a band in meters and programatically changes the onscreen dropdown to match.
        """
        self.band_selector.setCurrentIndex(self.band_selector.findText(theband))
        self.changeband()

    def setmode(self, themode: str) -> None:
        """
        Takes a string for the mode (CW, PH, DI) and programatically changes the onscreen dropdown.
        """
        self.mode_selector.setCurrentIndex(self.mode_selector.findText(themode))
        self.changemode()

    def poll_radio(self) -> None:
        """
        Poll rigctld to get band.
        """
        pass
        # if self.flrig:
        #     try:
        #         newfreq = self.server.rig.get_vfo()
        #         newmode = self.server.rig.get_mode()
        #         self.radio_icon.setPixmap(self.radio_green)
        #         if newfreq != self.oldfreq or newmode != self.oldmode:
        #             self.oldfreq = newfreq
        #             self.oldmode = newmode
        #             self.setband(str(self.getband(newfreq)))
        #             self.setmode(str(self.getmode(newmode)))
        #     except socket.error as exception:
        #         self.radio_icon.setPixmap(self.radio_red)
        #         logging.warning("poll_radio: flrig: %s", exception)
        #     return
        # if self.rigonline:
        #     try:
        #         self.rigctrlsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #         self.rigctrlsocket.connect((self.rigctrlhost, int(self.rigctrlport)))
        #         self.rigctrlsocket.settimeout(0.5)
        #         self.rigctrlsocket.send(b"f\n")
        #         newfreq = self.rigctrlsocket.recv(1024).decode().strip()
        #         self.rigctrlsocket.send(b"m\n")
        #         newmode = self.rigctrlsocket.recv(1024).decode().strip().split()[0]
        #         self.radio_icon.setPixmap(self.radio_green)
        #         self.rigctrlsocket.shutdown(socket.SHUT_RDWR)
        #         self.rigctrlsocket.close()
        #         if newfreq != self.oldfreq or newmode != self.oldmode:
        #             self.oldfreq = newfreq
        #             self.oldmode = newmode
        #             self.setband(str(self.getband(newfreq)))
        #             self.setmode(str(self.getmode(newmode)))
        #     except ConnectionRefusedError:
        #         logging.warning("poll_radio: ConnectionRefusedError")

    # def poll_radio(self):
    #    if self.rigonline:
    #        try:
    #            newfreq = self.server.rig.get_vfo()
    #            newmode = self.server.rig.get_mode()
    #            self.radio_icon.setPixmap(
    #                QtGui.QPixmap(self.relpath("icon/radio_green.png"))
    #            )
    #            # or newrfpower != self.oldrfpower:
    #            if newfreq != self.oldfreq or newmode != self.oldmode:
    #                self.oldfreq = newfreq
    #                self.oldmode = newmode
    #                self.setband(str(self.getband(newfreq)))
    #                self.setmode(str(self.getmode(newmode)))
    #        except:
    #            self.rigonline = False
    #            self.radio_icon.setPixmap(
    #                QtGui.QPixmap(self.relpath("icon/radio_red.png"))
    #            )

    def check_radio(self):
        """
        Checks to see if rigctld daemon is running.
        """
        # if self.userigctl:
        #     self.rigonline = True
        #     try:
        #         self.server = xmlrpc.client.ServerProxy(
        #             f"http://{self.rigctrlhost}:{self.rigctrlport}"
        #         )
        #         self.radio_icon.setPixmap(self.radio_red)
        #     except Error:
        #         self.rigonline = False
        #         self.radio_icon.setPixmap(self.radio_grey)
        # else:
        #     self.rigonline = False

    def radio(self):
        """
        Check for connection to rigctld. if it's there, poll it for radio status.
        """
        self.check_radio()
        self.poll_radio()

    def flash(self):
        """
        Flash the screen to give visual indication of a dupe.
        """
        self.setStyleSheet(
            "background-color: rgb(245, 121, 0);\ncolor: rgb(211, 215, 207);"
        )
        app.processEvents()
        self.setStyleSheet(
            "background-color: rgb(42, 42, 42);\ncolor: rgb(211, 215, 207);"
        )
        app.processEvents()

    def process_macro(self, macro):
        """Process CW macro substitutions"""
        macro = macro.upper()
        macro = macro.replace("{MYCALL}", self.preference["mycallsign"])
        macro = macro.replace("{MYCLASS}", self.preference["myclass"])
        macro = macro.replace("{MYSECT}", self.preference["mysection"])
        macro = macro.replace("{HISCALL}", self.callsign_entry.text())
        return macro

    def keyPressEvent(self, event):
        """This overrides Qt key event."""
        if event.key() == Qt.Key_Escape:
            self.clearinputs()
        if event.key() == Qt.Key_Tab:
            if self.section_entry.hasFocus():
                logging.debug("From section")
                self.callsign_entry.setFocus()
                self.callsign_entry.deselect()
                self.callsign_entry.end(False)
                return
            if self.class_entry.hasFocus():
                logging.debug("From class")
                self.section_entry.setFocus()
                self.section_entry.deselect()
                self.section_entry.end(False)
                return
            if self.callsign_entry.hasFocus():
                logging.debug("From callsign")
                cse = self.callsign_entry.text()
                if len(cse):
                    if cse[0] == ".":
                        self.keyboardcommand(cse)
                        return
                self.class_entry.setFocus()
                self.class_entry.deselect()
                self.class_entry.end(False)
                return
        if event.key() == Qt.Key_F1:
            self.sendf1()
        if event.key() == Qt.Key_F2:
            self.sendf2()
        if event.key() == Qt.Key_F3:
            self.sendf3()
        if event.key() == Qt.Key_F4:
            self.sendf4()
        if event.key() == Qt.Key_F5:
            self.sendf5()
        if event.key() == Qt.Key_F6:
            self.sendf6()
        if event.key() == Qt.Key_F7:
            self.sendf7()
        if event.key() == Qt.Key_F8:
            self.sendf8()
        if event.key() == Qt.Key_F9:
            self.sendf9()
        if event.key() == Qt.Key_F10:
            self.sendf10()
        if event.key() == Qt.Key_F11:
            self.sendf11()
        if event.key() == Qt.Key_F12:
            self.sendf12()

    def sendf1(self):
        """Sends CW macro"""
        if self.cw:
            self.cw.sendcw(self.process_macro(self.F1.toolTip()))

    def sendf2(self):
        """Sends CW macro"""
        if self.cw:
            self.cw.sendcw(self.process_macro(self.F2.toolTip()))

    def sendf3(self):
        """Sends CW macro"""
        if self.cw:
            self.cw.sendcw(self.process_macro(self.F3.toolTip()))

    def sendf4(self):
        """Sends CW macro"""
        if self.cw:
            self.cw.sendcw(self.process_macro(self.F4.toolTip()))

    def sendf5(self):
        """Sends CW macro"""
        if self.cw:
            self.cw.sendcw(self.process_macro(self.F5.toolTip()))

    def sendf6(self):
        """Sends CW macro"""
        if self.cw:
            self.cw.sendcw(self.process_macro(self.F6.toolTip()))

    def sendf7(self):
        """Sends CW macro"""
        if self.cw:
            self.cw.sendcw(self.process_macro(self.F7.toolTip()))

    def sendf8(self):
        """Sends CW macro"""
        if self.cw:
            self.cw.sendcw(self.process_macro(self.F8.toolTip()))

    def sendf9(self):
        """Sends CW macro"""
        if self.cw:
            self.cw.sendcw(self.process_macro(self.F9.toolTip()))

    def sendf10(self):
        """Sends CW macro"""
        if self.cw:
            self.cw.sendcw(self.process_macro(self.F10.toolTip()))

    def sendf11(self):
        """Sends CW macro"""
        if self.cw:
            self.cw.sendcw(self.process_macro(self.F11.toolTip()))

    def sendf12(self):
        """Sends CW macro"""
        if self.cw:
            self.cw.sendcw(self.process_macro(self.F12.toolTip()))

    def clearinputs(self):
        """Clears the text input fields and sets focus to callsign field."""
        self.callsign_entry.clear()
        self.class_entry.clear()
        self.section_entry.clear()
        self.callsign_entry.setFocus()

    def changeband(self):
        """
        Sets the internal band used for logging to the onscreen dropdown value.
        """
        self.band = self.band_selector.currentText()

    def changemode(self):
        """
        Sets the internal mode used for logging to the onscreen dropdown value.
        """
        self.mode = self.mode_selector.currentText()

    def changepower(self):
        """
        Sets the internal power level used for logging to the onscreen dropdown value.
        """
        self.preference["power"] = str(self.power_selector.value())
        self.oldrfpower = self.preference["power"]
        self.writepreferences()

    def changemycall(self):
        """Changes the users callsign"""
        text = self.mycallEntry.text()
        if len(text):
            if text[-1] == " ":
                self.mycallEntry.setText(text.strip())
            else:
                cleaned = "".join(
                    ch for ch in text if ch.isalnum() or ch == "/"
                ).upper()
                self.mycallEntry.setText(cleaned)
        self.mycall = self.mycallEntry.text()
        self.preference["mycallsign"] = self.mycall
        logging.info("%s", self.preference)
        if self.mycall != "":
            self.mycallEntry.setStyleSheet("border: 1px solid green;")
        else:
            self.mycallEntry.setStyleSheet("border: 1px solid red;")
        self.writepreferences()

    def changemyclass(self):
        """Changes the users class"""
        text = self.myclassEntry.text()
        if len(text):
            if text[-1] == " ":
                self.myclassEntry.setText(text.strip())
            else:
                cleaned = "".join(ch for ch in text if ch.isalnum()).upper()
                self.myclassEntry.setText(cleaned)
        self.myclass = self.myclassEntry.text()
        self.preference["myclass"] = self.myclass
        if self.myclass != "":
            self.myclassEntry.setStyleSheet("border: 1px solid green;")
        else:
            self.myclassEntry.setStyleSheet("border: 1px solid red;")
        self.writepreferences()

    def changemysection(self):
        """Changes the stored section."""
        text = self.mysectionEntry.text()
        if len(text):
            if text[-1] == " ":
                self.mysectionEntry.setText(text.strip())
            else:
                cleaned = "".join(ch for ch in text if ch.isalpha()).upper()
                self.mysectionEntry.setText(cleaned)
        self.mysection = self.mysectionEntry.text()
        self.preference["mysection"] = self.mysection
        if self.mysection != "":
            self.mysectionEntry.setStyleSheet("border: 1px solid green;")
        else:
            self.mysectionEntry.setStyleSheet("border: 1px solid red;")
        self.writepreferences()

    def keyboardcommand(self, text):
        """Process . commands entered in the callsign field"""
        self.callsign_entry.setText("")
        try:
            if text[1] == "Q":
                self.close()
                return
            if text[1] == "P":
                self.power_selector.setValue(int(text[2:]))
                return
            if text[1] == "E":
                qtoedit = int(text[2:])
                try:
                    with sqlite3.connect(self.database) as conn:
                        cursor = conn.cursor()
                        cursor.execute(f"select * from contacts where id={qtoedit}")
                        log = cursor.fetchone()
                        (
                            logid,
                            hiscall,
                            hisclass,
                            hissection,
                            the_datetime,
                            band,
                            mode,
                            power,
                            _,
                            _,
                        ) = log
                        self.linetopass = (
                            f"{str(logid).rjust(3,'0')} {hiscall.ljust(10)} {hisclass.rjust(3)} "
                            f"{hissection.rjust(3)} {the_datetime} {str(band).rjust(3)} "
                            f"{mode} {str(power).rjust(3)}"
                        )
                        dialog = EditQsoDialog(self)
                        dialog.setup(self.linetopass, self.database)
                        dialog.change.lineChanged.connect(self.qsoedited)
                        dialog.open()
                except sqlite3.Error:
                    pass
                return
                # attention
            if text[1] == "M":
                self.setmode(text[2:])
                return
            if text[1] == "B":
                self.setband(text[2:])
                return
            if text[1] == "K":
                self.mycallEntry.setText(text[2:])
                self.changemycall()
                return
            if text[1] == "C":
                self.mysectionEntry.setText(text[2:])
                self.changemyclass()
                return
            if text[1] == "S":
                self.mysectionEntry.setText(text[2:])
                self.changemysection()
                return
            if text[1] == "1":
                self.claim_alt_power(0)
                return
            if text[1] == "2":
                self.claim_outdoors(0)
                return
            if text[1] == "3":
                self.claim_not_at_home(0)
                return
            if text[1] == "4":
                self.claim_satellite(0)
                return
            if text[1] == "L":
                self.generate_logs()
                return
            if text[1] == "H":
                pass  # help
            if text[1] == "":
                pass  #
        except IndexError:
            pass

    def calltest(self):
        """
        Cleans callsign of spaces and strips non alphanumeric or '/' characters.
        """
        text = self.callsign_entry.text()
        if len(text):
            if text[-1] == " ":
                stripped = text.strip()
                self.callsign_entry.setText(text.strip())
                if len(stripped):
                    if stripped[0] == ".":
                        self.keyboardcommand(stripped)
                        return
                self.class_entry.setFocus()
                self.class_entry.deselect()
            else:
                washere = self.callsign_entry.cursorPosition()
                cleaned = "".join(
                    ch for ch in text if ch.isalnum() or ch == "/" or ch == "."
                ).upper()
                self.callsign_entry.setText(cleaned)
                self.callsign_entry.setCursorPosition(washere)
                self.super_check()

    def classtest(self):
        """
        Strips class of spaces and non alphanumerics, converts to uppercase.
        """
        text = self.class_entry.text()
        if len(text):
            if text[-1] == " ":
                self.class_entry.setText(text.strip())
                self.section_entry.setFocus()
                self.section_entry.deselect()
            else:
                washere = self.class_entry.cursorPosition()
                cleaned = "".join(ch for ch in text if ch.isalnum()).upper()
                self.class_entry.setText(cleaned)
                self.class_entry.setCursorPosition(washere)

    def sectiontest(self):
        """
        Strips section of spaces and non alpha characters, converts to uppercase.
        """
        text = self.section_entry.text()
        if len(text):
            if text[-1] == " ":
                self.section_entry.setText(text.strip())
                self.callsign_entry.setFocus()
                self.callsign_entry.deselect()
            else:
                washere = self.section_entry.cursorPosition()
                cleaned = "".join(ch for ch in text if ch.isalpha()).upper()
                self.section_entry.setText(cleaned)
                self.section_entry.setCursorPosition(washere)

    @staticmethod
    def highlighted(state: bool) -> str:
        """
        Return CSS foreground highlight color if state is true,
        otherwise return an empty string.
        """
        if state:
            return "color: rgb(245, 121, 0);"
        else:
            return ""

    def log_contact(self):
        """Log a contact to the db."""

        if (
            len(self.callsign_entry.text()) == 0
            or len(self.class_entry.text()) == 0
            or len(self.section_entry.text()) == 0
        ):
            logging.info("Incomplete fields")
            return

        contact = (
            self.callsign_entry.text(),
            self.class_entry.text(),
            self.section_entry.text(),
            self.band,
            self.mode,
            int(self.power_selector.value()),
            self.contactlookup["grid"],
            self.contactlookup["name"],
        )
        self.db.log_contact(contact)
        self.sections()
        self.stats()
        self.updatemarker()
        self.logwindow()
        self.clearinputs()
        self.postcloudlog()

    def stats(self) -> None:
        """
        Get an idea of how you're doing points wise.
        """
        (
            cwcontacts,
            phonecontacts,
            digitalcontacts,
            bandmodemult,
            last15,
            lasthour,
            _,
            _,
        ) = self.db.stats()
        self.Total_CW.setText(str(cwcontacts))
        self.Total_Phone.setText(str(phonecontacts))
        self.Total_Digital.setText(str(digitalcontacts))
        self.QSO_Last15.setText(str(last15))
        self.QSO_PerHour.setText(str(lasthour))
        self.bandmodemult = bandmodemult
        self.QSO_Points.setText(str(self.calcscore()))

    def calcscore(self) -> int:
        """
        Return our current score based on operating power,
        band / mode multipliers and types of contacts.
        """
        cw, ph, di, bandmodemult, _, _, highpower, qrp = self.db.stats()
        self.score = (int(cw) * 2) + int(ph) + (int(di) * 2)
        if qrp:
            self.score = self.score * 4
        elif not highpower:
            self.score = self.score * 2
        self.score = self.score * bandmodemult
        self.score = (
            self.score
            + (500 * self.preference["altpower"])
            + (500 * self.preference["outdoors"])
            + (500 * self.preference["notathome"])
            + (500 * self.preference["satellite"])
        )
        return self.score

    def qrpcheck(self):
        """qrp = 5W cw, 10W ph and di, highpower greater than 100W"""
        try:
            with sqlite3.connect(self.database) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "select count(*) as qrpc from contacts where mode = 'CW' and power > 5"
                )
                log = cursor.fetchall()
                qrpc = list(log[0])[0]
                cursor.execute(
                    "select count(*) as qrpp from contacts where mode = 'PH' and power > 10"
                )
                log = cursor.fetchall()
                qrpp = list(log[0])[0]
                cursor.execute(
                    "select count(*) as qrpd from contacts where mode = 'DI' and power > 10"
                )
                log = cursor.fetchall()
                qrpd = list(log[0])[0]
                cursor.execute(
                    "select count(*) as highpower from contacts where power > 100"
                )
                log = cursor.fetchall()
                self.highpower = bool(list(log[0])[0])
                self.qrp = not qrpc + qrpp + qrpd
        except Error as exception:
            logging.critical("qrpcheck: %s", exception)

    def logwindow(self):
        """Populated the log window with contacts stored in the database."""
        self.listWidget.clear()
        log = self.db.fetch_all_contacts_desc()
        for x in log:
            (
                logid,
                hiscall,
                hisclass,
                hissection,
                the_date_and_time,
                band,
                mode,
                power,
                _,
                _,
            ) = x
            logline = (
                f"{str(logid).rjust(3,'0')} {hiscall.ljust(10)} {hisclass.rjust(3)} "
                f"{hissection.rjust(3)} {the_date_and_time} {str(band).rjust(3)} {mode} "
                f"{str(power).rjust(3)}"
            )
            self.listWidget.addItem(logline)

    def qsoedited(self):
        """
        Perform functions after QSO edited or deleted.
        """
        self.sections()
        self.stats()
        self.logwindow()

    def qsoclicked(self):
        """
        Gets the line of the log clicked on, and passes that line to the edit dialog.
        """
        item = self.listWidget.currentItem()
        self.linetopass = item.text()
        dialog = EditQsoDialog(self)
        dialog.setup(self.linetopass, self.database)
        dialog.change.lineChanged.connect(self.qsoedited)
        dialog.open()

    def read_sections(self):
        """
        Reads in the ARRL sections into some internal dictionaries.
        """
        try:
            with open(
                self.relpath("arrl_sect.dat"), "r", encoding="utf-8"
            ) as file_descriptor:  # read section data
                while 1:
                    line = (
                        file_descriptor.readline().strip()
                    )  # read a line and put in db
                    if not line:
                        break
                    if line[0] == "#":
                        continue
                    try:
                        _, state, canum, abbrev, name = str.split(line, None, 4)
                        self.secName[abbrev] = abbrev + " " + name + " " + canum
                        self.secState[abbrev] = state
                        for i in range(len(abbrev) - 1):
                            partial = abbrev[: -i - 1]
                            self.secPartial[partial] = 1
                    except ValueError as exception:
                        logging.warning("read_sections: %s", exception)
        except IOError as exception:
            logging.critical("read_sections: read error: %s", exception)

    def section_check(self):
        """
        Shows you the possible section matches based on
        what you have typed in the section input filed.
        """
        self.infobox.clear()
        self.infobox.setTextColor(QtGui.QColor(211, 215, 207))
        sec = self.section_entry.text()
        if sec == "":
            sec = "^"
        x = list(self.secName.keys())
        xx = list(filter(lambda y: y.startswith(sec), x))
        for xxx in xx:
            self.infobox.insertPlainText(self.secName[xxx] + "\n")

    def read_scp(self):
        """
        Reads in a list of known contesters into an internal dictionary
        """
        try:
            with open(
                self.relpath("MASTER.SCP"), "r", encoding="utf-8"
            ) as file_descriptor:
                self.scp = file_descriptor.readlines()
                self.scp = list(map(lambda x: x.strip(), self.scp))
        except IOError as exception:
            logging.critical("read_scp: read error: %s", exception)

    def super_check(self):
        """
        Performs a supercheck partial on the callsign entered in the field.
        """
        self.infobox.clear()
        self.infobox.setTextColor(QtGui.QColor(211, 215, 207))
        acall = self.callsign_entry.text()
        if len(acall) > 2:
            matches = list(filter(lambda x: x.startswith(acall), self.scp))
            for match in matches:
                self.infobox.insertPlainText(match + " ")

    def dup_check(self) -> None:
        """checks to see if a contact you're entering will be a dup."""
        acall = self.callsign_entry.text()
        self.infobox.clear()
        try:
            with sqlite3.connect(self.database) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"select callsign, class, section, band, mode "
                    f"from contacts where callsign like '{acall}' order by band"
                )
                log = cursor.fetchall()
        except sqlite3.Error as exception:
            logging.critical("dup_check: %s", exception)
            return
        for contact in log:
            hiscall, hisclass, hissection, hisband, hismode = contact
            if len(self.class_entry.text()) == 0:
                self.class_entry.setText(hisclass)
            if len(self.section_entry.text()) == 0:
                self.section_entry.setText(hissection)
            dupetext = ""
            if hisband == self.band and hismode == self.mode:
                self.flash()
                self.infobox.setTextColor(QtGui.QColor(245, 121, 0))
                dupetext = " DUP!!!"
            else:
                self.infobox.setTextColor(QtGui.QColor(211, 215, 207))
            self.infobox.insertPlainText(f"{hiscall}: {hisband} {hismode}{dupetext}\n")

    def sections_worked(self) -> None:
        """Generates a list of sections worked."""
        try:
            with sqlite3.connect(self.database) as conn:
                cursor = conn.cursor()
                cursor.execute("select distinct section from contacts")
                all_rows = cursor.fetchall()
        except sqlite3.Error as exception:
            logging.critical("sections_worked: %s", exception)
            return
        self.wrkdsections = str(all_rows)
        self.wrkdsections = (
            self.wrkdsections.replace("('", "")
            .replace("',), ", ",")
            .replace("',)]", "")
            .replace("[", "")
            .split(",")
        )

    def worked_section(self, section: str) -> str:
        """
        Return CSS foreground value for section based on if it has been worked.
        """
        if section in self.wrkdsections:
            return "color: rgb(245, 121, 0);"
        else:
            return "color: rgb(136, 138, 133);"

    def sections_column_1(self) -> None:
        """Highlights the sections worked in column 1"""
        self.Section_DX.setStyleSheet(self.worked_section("DX"))
        self.Section_CT.setStyleSheet(self.worked_section("CT"))
        self.Section_RI.setStyleSheet(self.worked_section("RI"))
        self.Section_EMA.setStyleSheet(self.worked_section("EMA"))
        self.Section_VT.setStyleSheet(self.worked_section("VT"))
        self.Section_ME.setStyleSheet(self.worked_section("ME"))
        self.Section_WMA.setStyleSheet(self.worked_section("WMA"))
        self.Section_NH.setStyleSheet(self.worked_section("NH"))
        self.Section_ENY.setStyleSheet(self.worked_section("ENY"))
        self.Section_NNY.setStyleSheet(self.worked_section("NNY"))
        self.Section_NLI.setStyleSheet(self.worked_section("NLI"))
        self.Section_SNJ.setStyleSheet(self.worked_section("SNJ"))
        self.Section_NNJ.setStyleSheet(self.worked_section("NNJ"))
        self.Section_WNY.setStyleSheet(self.worked_section("WNY"))

    def sections_column_2(self) -> None:
        """Highlights the sections worked in column 2"""
        self.Section_DE.setStyleSheet(self.worked_section("DE"))
        self.Section_MDC.setStyleSheet(self.worked_section("MDC"))
        self.Section_EPA.setStyleSheet(self.worked_section("EPA"))
        self.Section_WPA.setStyleSheet(self.worked_section("WPA"))
        self.Section_AL.setStyleSheet(self.worked_section("AL"))
        self.Section_SC.setStyleSheet(self.worked_section("SC"))
        self.Section_GA.setStyleSheet(self.worked_section("GA"))
        self.Section_SFL.setStyleSheet(self.worked_section("SFL"))
        self.Section_KY.setStyleSheet(self.worked_section("KY"))
        self.Section_TN.setStyleSheet(self.worked_section("TN"))
        self.Section_NC.setStyleSheet(self.worked_section("NC"))
        self.Section_VA.setStyleSheet(self.worked_section("VA"))
        self.Section_NFL.setStyleSheet(self.worked_section("NFL"))
        self.Section_VI.setStyleSheet(self.worked_section("VI"))
        self.Section_PR.setStyleSheet(self.worked_section("PR"))
        self.Section_WCF.setStyleSheet(self.worked_section("WCF"))

    def sections_column_3(self) -> None:
        """Highlights the sections worked in column 3"""
        self.Section_AR.setStyleSheet(self.worked_section("AR"))
        self.Section_NTX.setStyleSheet(self.worked_section("NTX"))
        self.Section_LA.setStyleSheet(self.worked_section("LA"))
        self.Section_OK.setStyleSheet(self.worked_section("OK"))
        self.Section_MS.setStyleSheet(self.worked_section("MS"))
        self.Section_STX.setStyleSheet(self.worked_section("STX"))
        self.Section_NM.setStyleSheet(self.worked_section("NM"))
        self.Section_WTX.setStyleSheet(self.worked_section("WTX"))
        self.Section_EB.setStyleSheet(self.worked_section("EB"))
        self.Section_SCV.setStyleSheet(self.worked_section("SCV"))
        self.Section_LAX.setStyleSheet(self.worked_section("LAX"))
        self.Section_SDG.setStyleSheet(self.worked_section("SDG"))
        self.Section_ORG.setStyleSheet(self.worked_section("ORG"))
        self.Section_SF.setStyleSheet(self.worked_section("SF"))
        self.Section_PAC.setStyleSheet(self.worked_section("PAC"))
        self.Section_SJV.setStyleSheet(self.worked_section("SJV"))
        self.Section_SB.setStyleSheet(self.worked_section("SB"))
        self.Section_SV.setStyleSheet(self.worked_section("SV"))

    def sections_column_4(self) -> None:
        """Highlights the sections worked in column 4"""
        self.Section_AK.setStyleSheet(self.worked_section("AK"))
        self.Section_NV.setStyleSheet(self.worked_section("NV"))
        self.Section_AZ.setStyleSheet(self.worked_section("AZ"))
        self.Section_OR.setStyleSheet(self.worked_section("OR"))
        self.Section_EWA.setStyleSheet(self.worked_section("EWA"))
        self.Section_UT.setStyleSheet(self.worked_section("UT"))
        self.Section_ID.setStyleSheet(self.worked_section("ID"))
        self.Section_WWA.setStyleSheet(self.worked_section("WWA"))
        self.Section_MT.setStyleSheet(self.worked_section("MT"))
        self.Section_WY.setStyleSheet(self.worked_section("WY"))
        self.Section_MI.setStyleSheet(self.worked_section("MI"))
        self.Section_WV.setStyleSheet(self.worked_section("WV"))
        self.Section_OH.setStyleSheet(self.worked_section("OH"))
        self.Section_IL.setStyleSheet(self.worked_section("IL"))
        self.Section_WI.setStyleSheet(self.worked_section("WI"))
        self.Section_IN.setStyleSheet(self.worked_section("IN"))

    def sections_column_5(self) -> None:
        """Highlights the sections worked in column 5"""
        self.Section_CO.setStyleSheet(self.worked_section("CO"))
        self.Section_MO.setStyleSheet(self.worked_section("MO"))
        self.Section_IA.setStyleSheet(self.worked_section("IA"))
        self.Section_ND.setStyleSheet(self.worked_section("ND"))
        self.Section_KS.setStyleSheet(self.worked_section("KS"))
        self.Section_NE.setStyleSheet(self.worked_section("NE"))
        self.Section_MN.setStyleSheet(self.worked_section("MN"))
        self.Section_SD.setStyleSheet(self.worked_section("SD"))
        self.Section_AB.setStyleSheet(self.worked_section("AB"))
        self.Section_NT.setStyleSheet(self.worked_section("NT"))
        self.Section_BC.setStyleSheet(self.worked_section("BC"))
        self.Section_ONE.setStyleSheet(self.worked_section("ONE"))
        self.Section_GTA.setStyleSheet(self.worked_section("GTA"))
        self.Section_ONN.setStyleSheet(self.worked_section("ONN"))
        self.Section_MAR.setStyleSheet(self.worked_section("MAR"))
        self.Section_ONS.setStyleSheet(self.worked_section("ONS"))
        self.Section_MB.setStyleSheet(self.worked_section("MB"))
        self.Section_QC.setStyleSheet(self.worked_section("QC"))
        self.Section_NL.setStyleSheet(self.worked_section("NL"))
        self.Section_SK.setStyleSheet(self.worked_section("SK"))
        self.Section_PE.setStyleSheet(self.worked_section("PE"))

    def sections(self) -> None:
        """
        Updates onscreen sections highlighting the ones worked.
        """
        self.sections_worked()
        self.sections_column_1()
        self.sections_column_2()
        self.sections_column_3()
        self.sections_column_4()
        self.sections_column_5()

    def claim_alt_power(self, _) -> None:
        """is called when the Alt Power button is pressed."""
        self.preference["altpower"] = not self.preference["altpower"]
        self.altpowerButton.setStyleSheet(self.highlighted(self.preference["altpower"]))
        self.writepreferences()
        self.stats()

    def claim_outdoors(self, _) -> None:
        """Is called when the Outdoors button is pressed."""
        self.preference["outdoors"] = not self.preference["outdoors"]
        self.outdoorsButton.setStyleSheet(self.highlighted(self.preference["outdoors"]))
        self.writepreferences()
        self.stats()

    def claim_not_at_home(self, _) -> None:
        """Is called when the Not At Home button is pressed."""
        self.preference["notathome"] = not self.preference["notathome"]
        self.notathomeButton.setStyleSheet(
            self.highlighted(self.preference["notathome"])
        )
        self.writepreferences()
        self.stats()

    def claim_satellite(self, _) -> None:
        """Is called when the satellite button is pressed."""
        self.preference["satellite"] = not self.preference["satellite"]
        self.satelliteButton.setStyleSheet(
            self.highlighted(self.preference["satellite"])
        )
        self.writepreferences()
        self.stats()

    def get_band_mode_tally(self, band, mode):
        """
        Returns the amount of contacts and the maximum power
        used for a particular band/mode combination.
        """
        try:
            with sqlite3.connect(self.database) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"select count(*) as tally, MAX(power) as mpow "
                    f"from contacts where band = '{band}' AND mode ='{mode}'"
                )
                return cursor.fetchone()
        except Error as exception:
            logging.critical("get_band_mode_tally: %s", exception)

    def getbands(self) -> list:
        """
        Returns a list of bands worked, and an empty list if none worked.
        """
        bandlist = []
        try:
            with sqlite3.connect(self.database) as conn:
                cursor = conn.cursor()
                cursor.execute("select DISTINCT band from contacts")
                result = cursor.fetchall()
        except Error as exception:
            logging.critical("getbands: %s", exception)
            return []
        if result:
            for returned_band in result:
                bandlist.append(returned_band[0])
            return bandlist
        return []

    def generate_band_mode_tally(self) -> None:
        """
        Creates a Statistics.txt file when the Generate Logs button
        is pressed. Containing a breakdown of the bands and modes
        used.
        """
        bandlist = self.getbands()
        try:
            with open("Statistics.txt", "w", encoding="utf-8") as file_descriptor:
                print("\t\tCW\tPWR\tDI\tPWR\tPH\tPWR", end="\r\n", file=file_descriptor)
                print("-" * 60, end="\r\n", file=file_descriptor)
                for band in self.bands:
                    if band in bandlist:
                        cwt = self.get_band_mode_tally(band, "CW")
                        dit = self.get_band_mode_tally(band, "DI")
                        pht = self.get_band_mode_tally(band, "PH")
                        print(
                            f"Band:\t{band}\t{cwt[0]}\t{cwt[1]}\t"
                            f"{dit[0]}\t{dit[1]}\t{pht[0]}\t{pht[1]}",
                            end="\r\n",
                            file=file_descriptor,
                        )
                        print("-" * 60, end="\r\n", file=file_descriptor)
        except IOError as exception:
            logging.critical("generate_band_mode_tally: write error: %s", exception)

    def get_state(self, section):
        """
        Returns the US state a section is in, or Bool False if none was found.
        !todo rewrite this probably with 'if state in self.secState:'
        """
        try:
            state = self.secState[section]
            if state != "--":
                return state
        except IndexError:
            return False
        return False

    def gridtolatlon(self, maiden):
        """
        Converts a maidenhead gridsquare to a latitude longitude pair.
        """
        maiden = str(maiden).strip().upper()

        chars_in_grid_square = len(maiden)
        if not 8 >= chars_in_grid_square >= 2 and chars_in_grid_square % 2 == 0:
            return 0, 0

        lon = (ord(maiden[0]) - 65) * 20 - 180
        lat = (ord(maiden[1]) - 65) * 10 - 90

        if chars_in_grid_square >= 4:
            lon += (ord(maiden[2]) - 48) * 2
            lat += ord(maiden[3]) - 48

        if chars_in_grid_square >= 6:
            lon += (ord(maiden[4]) - 65) / 12 + 1 / 24
            lat += (ord(maiden[5]) - 65) / 24 + 1 / 48

        if chars_in_grid_square >= 8:
            lon += (ord(maiden[6])) * 5.0 / 600
            lat += (ord(maiden[7])) * 2.5 / 600

        return lat, lon

    def updatemarker(self):
        """
        Updates the xplanet marker file with a list of logged contact lat & lon
        """
        if self.usemarker:
            filename = str(Path.home()) + "/" + self.markerfile
            try:
                with sqlite3.connect(self.database) as conn:
                    cursor = conn.cursor()
                    cursor.execute("select DISTINCT grid from contacts")
                    grids = cursor.fetchall()
                if grids:
                    lastcolor = ""
                    with open(filename, "w", encoding="ascii") as file_descriptor:
                        islast = len(grids) - 1
                        for count, grid in enumerate(grids):
                            if count == islast:
                                lastcolor = "color=Orange"
                            if len(grid[0]) > 1:
                                lat, lon = self.gridtolatlon(grid[0])
                                print(
                                    f'{lat} {lon} "" {lastcolor}',
                                    end="\r\n",
                                    file=file_descriptor,
                                )
            except IOError as exception:
                logging.warning(
                    "updatemarker: error %s writing to %s", exception, filename
                )
                self.infobox.setTextColor(QtGui.QColor(245, 121, 0))
                self.infobox.insertPlainText(f"Unable to write to {filename}\n")
            except Error as exception:
                logging.critical("updatemarker: db error: %s", exception)

    def adif(self):
        """
        Creates an ADIF file of the contacts made.
        """
        logname = "WFD.adi"
        self.infobox.setTextColor(QtGui.QColor(211, 215, 207))
        self.infobox.insertPlainText(f"Saving ADIF to: {logname}\n")
        app.processEvents()
        try:
            with sqlite3.connect(self.database) as conn:
                cursor = conn.cursor()
                cursor.execute("select * from contacts order by date_time ASC")
                log = cursor.fetchall()
        except sqlite3.Error as exception:
            logging.critical("adif: db error: %s", exception)
            return
        grid = False
        opname = False
        try:
            with open(logname, "w", encoding="ascii") as file_descriptor:
                print("<ADIF_VER:5>2.2.0", end="\r\n", file=file_descriptor)
                print("<EOH>", end="\r\n", file=file_descriptor)
                for contact in log:
                    (
                        _,
                        hiscall,
                        hisclass,
                        hissection,
                        the_date_and_time,
                        band,
                        mode,
                        _,
                        grid,
                        opname,
                    ) = contact
                    if mode == "DI":
                        mode = "RTTY"
                    if mode == "PH":
                        mode = "SSB"
                    if mode == "CW":
                        rst = "599"
                    else:
                        rst = "59"
                    loggeddate = the_date_and_time[:10]
                    loggedtime = the_date_and_time[11:13] + the_date_and_time[14:16]
                    print(
                        f"<QSO_DATE:{len(''.join(loggeddate.split('-')))}:d>"
                        f"{''.join(loggeddate.split('-'))}",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    print(
                        f"<TIME_ON:{len(loggedtime)}>{loggedtime}",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    print(
                        f"<CALL:{len(hiscall)}>{hiscall}",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    print(f"<MODE:{len(mode)}>{mode}", end="\r\n", file=file_descriptor)
                    print(
                        f"<BAND:{len(band + 'M')}>{band + 'M'}",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    try:
                        print(
                            f"<FREQ:{len(self.dfreq[band])}>{self.dfreq[band]}",
                            end="\r\n",
                            file=file_descriptor,
                        )
                    except IndexError:
                        pass  # This is bad form... I can't remember why this is in a try block
                    print(
                        f"<RST_SENT:{len(rst)}>{rst}", end="\r\n", file=file_descriptor
                    )
                    print(
                        f"<RST_RCVD:{len(rst)}>{rst}", end="\r\n", file=file_descriptor
                    )
                    print(
                        f"<STX_STRING:{len(self.myclass + ' ' + self.mysection)}>"
                        f"{self.myclass + ' ' + self.mysection}",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    print(
                        f"<SRX_STRING:{len(hisclass + ' ' + hissection)}>"
                        f"{hisclass + ' ' + hissection}",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    print(
                        f"<ARRL_SECT:{len(hissection)}>{hissection}",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    print(
                        f"<CLASS:{len(hisclass)}>{hisclass}",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    state = self.get_state(hissection)
                    if state:
                        print(
                            f"<STATE:{len(state)}>{state}",
                            end="\r\n",
                            file=file_descriptor,
                        )
                    if len(grid) > 1:
                        print(
                            f"<GRIDSQUARE:{len(grid)}>{grid}",
                            end="\r\n",
                            file=file_descriptor,
                        )
                    if len(opname) > 1:
                        print(
                            f"<NAME:{len(opname)}>{opname}",
                            end="\r\n",
                            file=file_descriptor,
                        )
                    comment = "WINTER-FIELD-DAY"
                    print(
                        f"<COMMENT:{len(comment)}>{comment}",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    print("<EOR>", end="\r\n", file=file_descriptor)
                    print("", end="\r\n", file=file_descriptor)
        except IOError as exception:
            logging.critical("adif: IO error: %s", exception)
        self.infobox.insertPlainText("Done\n\n")
        app.processEvents()

    def postcloudlog(self):
        """
        Log contact to Cloudlog: https://github.com/magicbug/Cloudlog
        """
        if (not self.usecloudlog) or (not self.cloudlogauthenticated):
            return
        try:
            with sqlite3.connect(self.database) as conn:
                cursor = conn.cursor()
                cursor.execute("select * from contacts order by id DESC")
                contact = cursor.fetchone()
        except sqlite3.Error as exception:
            logging.critical("postcloudlog: db error: %s", exception)
            return
        (
            _,
            hiscall,
            hisclass,
            hissection,
            the_date_and_time,
            band,
            mode,
            _,
            grid,
            opname,
        ) = contact

        if mode == "DI":
            mode = "RTTY"
        if mode == "PH":
            mode = "SSB"
        if mode == "CW":
            rst = "599"
        else:
            rst = "59"
        loggeddate = the_date_and_time[:10]
        loggedtime = the_date_and_time[11:13] + the_date_and_time[14:16]
        adifq = (
            f"<QSO_DATE:{len(''.join(loggeddate.split('-')))}:d>"
            f"{''.join(loggeddate.split('-'))}"
            f"<TIME_ON:{len(loggedtime)}>{loggedtime}"
            f"<CALL:{len(hiscall)}>{hiscall}"
            f"<MODE:{len(mode)}>{mode}"
            f"<BAND:{len(band + 'M')}>{band + 'M'}"
            f"<FREQ:{len(self.dfreq[band])}>{self.dfreq[band]}"
            f"<RST_SENT:{len(rst)}>{rst}"
            f"<RST_RCVD:{len(rst)}>{rst}"
            f"<STX_STRING:{len(self.myclass + ' ' + self.mysection)}>"
            f"{self.myclass + ' ' + self.mysection}"
            f"<SRX_STRING:{len(hisclass + ' ' + hissection)}>"
            f"{hisclass + ' ' + hissection}"
            f"<ARRL_SECT:{len(hissection)}>{hissection}"
            f"<CLASS:{len(hisclass)}>{hisclass}"
        )
        state = self.get_state(hissection)
        if state:
            adifq += f"<STATE:{len(state)}>{state}"
        if len(grid) > 1:
            adifq += f"<GRIDSQUARE:{len(grid)}>{grid}"
        if len(opname) > 1:
            adifq += f"<NAME:{len(opname)}>{opname}"
        comment = "Winter Field Day"
        adifq += f"<COMMENT:{len(comment)}>{comment}"
        adifq += "<EOR>"

        payload_dict = {"key": self.cloudlogapi, "type": "adif", "string": adifq}
        jason_data = dumps(payload_dict)
        _ = requests.post(self.cloudlogurl, jason_data)

    def cabrillo(self):
        """
        Generates a cabrillo log file.
        """
        filename = f"{self.mycall.upper()}.log"
        self.infobox.setTextColor(QtGui.QColor(211, 215, 207))
        self.infobox.insertPlainText(f"Saving cabrillo to: {filename}")
        app.processEvents()
        bonuses = 0
        try:
            with sqlite3.connect(self.database) as conn:
                cursor = conn.cursor()
                cursor.execute("select * from contacts order by date_time ASC")
                log = cursor.fetchall()
        except sqlite3.Error as exception:
            logging.critical("cabrillo: db error: %s", exception)
            self.infobox.insertPlainText(" Failed\n\n")
            app.processEvents()
            return
        catpower = ""
        if self.qrp:
            catpower = "QRP"
        elif self.highpower:
            catpower = "HIGH"
        else:
            catpower = "LOW"
        try:
            with open(filename, "w", encoding="ascii") as file_descriptor:
                print("START-OF-LOG: 3.0", end="\r\n", file=file_descriptor)
                print(
                    "CREATED-BY: K6GTE Winter Field Day Logger",
                    end="\r\n",
                    file=file_descriptor,
                )
                print("CONTEST: WFD", end="\r\n", file=file_descriptor)
                print(f"CALLSIGN: {self.mycall}", end="\r\n", file=file_descriptor)
                print("LOCATION:", end="\r\n", file=file_descriptor)
                print(
                    f"ARRL-SECTION: {self.mysection}", end="\r\n", file=file_descriptor
                )
                print(f"CATEGORY: {self.myclass}", end="\r\n", file=file_descriptor)
                print(f"CATEGORY-POWER: {catpower}", end="\r\n", file=file_descriptor)
                print(
                    f"SOAPBOX: QSO Points {self.basescore}",
                    end="\r\n",
                    file=file_descriptor,
                )
                print(
                    f"SOAPBOX: Power Output Multiplier {self.powermult}",
                    end="\r\n",
                    file=file_descriptor,
                )
                print(
                    f"SOAPBOX: Band/mode multiplier {self.bandmodemult}",
                    end="\r\n",
                    file=file_descriptor,
                )
                if self.preference["altpower"]:
                    print(
                        "SOAPBOX: 500 points for not using commercial power",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    bonuses = bonuses + 500
                if self.preference["outdoors"]:
                    print(
                        "SOAPBOX: 500 points for setting up outdoors",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    bonuses = bonuses + 500
                if self.preference["notathome"]:
                    print(
                        "SOAPBOX: 500 points for setting up away from home",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    bonuses = bonuses + 500
                if self.preference["satellite"]:
                    print(
                        "SOAPBOX: 500 points for working satellite",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    bonuses = bonuses + 500
                print(
                    f"SOAPBOX: BONUS Total {bonuses}", end="\r\n", file=file_descriptor
                )
                print(
                    f"CLAIMED-SCORE: {self.calcscore()}",
                    end="\r\n",
                    file=file_descriptor,
                )
                print(f"OPERATORS: {self.mycall}", end="\r\n", file=file_descriptor)
                print("NAME: ", end="\r\n", file=file_descriptor)
                print("ADDRESS: ", end="\r\n", file=file_descriptor)
                print("ADDRESS-CITY: ", end="\r\n", file=file_descriptor)
                print("ADDRESS-STATE: ", end="\r\n", file=file_descriptor)
                print("ADDRESS-POSTALCODE: ", end="\r\n", file=file_descriptor)
                print("ADDRESS-COUNTRY: ", end="\r\n", file=file_descriptor)
                print("EMAIL: ", end="\r\n", file=file_descriptor)
                for contact in log:
                    (
                        _,
                        hiscall,
                        hisclass,
                        hissection,
                        the_date_and_time,
                        band,
                        mode,
                        _,
                        _,
                        _,
                    ) = contact
                    loggeddate = the_date_and_time[:10]
                    loggedtime = the_date_and_time[11:13] + the_date_and_time[14:16]
                    print(
                        f"QSO: {self.dfreq[band].replace('.','')} {mode} {loggeddate} "
                        f"{loggedtime} {self.mycall} {self.myclass} {self.mysection} "
                        f"{hiscall} {hisclass} {hissection}",
                        end="\r\n",
                        file=file_descriptor,
                    )
                print("END-OF-LOG:", end="\r\n", file=file_descriptor)
        except IOError as exception:
            logging.critical(
                "cabrillo: IO error: %s, writing to %s", exception, filename
            )
            self.infobox.insertPlainText(" Failed\n\n")
            app.processEvents()
            return
        self.infobox.insertPlainText(" Done\n\n")
        app.processEvents()

    def generate_logs(self):
        """Called when the user presses the Generate Logs button."""
        self.infobox.clear()
        self.cabrillo()
        self.generate_band_mode_tally()
        self.adif()


class EditQsoDialog(QtWidgets.QDialog):
    """Edits/deletes a contacts in the database"""

    theitem = ""
    database = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(self.relpath("dialog.ui"), self)
        self.deleteButton.clicked.connect(self.delete_contact)
        self.buttonBox.accepted.connect(self.save_changes)
        self.change = QSOEdit()

    def setup(self, linetopass, thedatabase):
        """Loads in the contact information and db to access."""
        self.database = thedatabase
        (
            self.theitem,
            thecall,
            theclass,
            thesection,
            thedate,
            thetime,
            theband,
            themode,
            thepower,
        ) = linetopass.split()
        self.editCallsign.setText(thecall)
        self.editClass.setText(theclass)
        self.editSection.setText(thesection)
        self.editBand.setCurrentIndex(self.editBand.findText(theband))
        self.editMode.setCurrentIndex(self.editMode.findText(themode))
        self.editPower.setValue(int(thepower))
        date_time = thedate + " " + thetime
        now = QtCore.QDateTime.fromString(date_time, "yyyy-MM-dd hh:mm:ss")
        self.editDateTime.setDateTime(now)

    @staticmethod
    def relpath(filename: str) -> str:
        """
        If the program is packaged with pyinstaller,
        this is needed since all files will be in a temp folder during execution.
        """
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            base_path = getattr(sys, "_MEIPASS")
        else:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, filename)

    def save_changes(self):
        """Update edited contact in the db."""
        try:
            with sqlite3.connect(self.database) as conn:
                sql = (
                    f"update contacts set callsign = '{self.editCallsign.text().upper()}', "
                    f"class = '{self.editClass.text().upper()}', "
                    f"section = '{self.editSection.text().upper()}', "
                    f"date_time = '{self.editDateTime.text()}', "
                    f"band = '{self.editBand.currentText()}', "
                    f"mode = '{self.editMode.currentText()}', "
                    f"power = '{self.editPower.value()}'  where id={self.theitem}"
                )
                cur = conn.cursor()
                cur.execute(sql)
                conn.commit()
        except sqlite3.Error as exception:
            logging.critical("save_changes: db error: %s", exception)
        self.change.lineChanged.emit()

    def delete_contact(self):
        """Delete a contact from the db."""
        try:
            with sqlite3.connect(self.database) as conn:
                sql = f"delete from contacts where id={self.theitem}"
                cur = conn.cursor()
                cur.execute(sql)
                conn.commit()
        except sqlite3.Error as exception:
            logging.critical("delete_contact: db error: %s", exception)
        self.change.lineChanged.emit()
        self.close()


class Startup(QtWidgets.QDialog):
    """
    Show splash screen, get Op call, class, section
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(self.relpath("startup.ui"), self)
        self.continue_pushButton.clicked.connect(self.store)

    @staticmethod
    def relpath(filename: str) -> str:
        """
        Checks to see if program has been packaged with pyinstaller.
        If so base dir is in a temp folder.
        """
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            base_path = getattr(sys, "_MEIPASS")
        else:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, filename)

    def set_callsign(self, callsign):
        """generic getter/setter method"""
        self.dialog_callsign.setText(callsign)

    def set_class(self, myclass):
        """generic getter/setter method"""
        self.dialog_class.setText(myclass)

    def set_section(self, mysection):
        """generic getter/setter method"""
        self.dialog_section.setText(mysection)

    def get_callsign(self):
        """generic getter/setter method"""
        return self.dialog_callsign.text()

    def get_class(self):
        """generic getter/setter method"""
        return self.dialog_class.text()

    def get_section(self):
        """generic getter/setter method"""
        return self.dialog_section.text()

    def store(self):
        """dialog magic"""
        self.accept()


def startup_dialog_finished():
    """
    Store call, class, section enteries and close dialog
    """
    window.mycallEntry.setText(startupdialog.get_callsign())
    window.changemycall()
    window.myclassEntry.setText(startupdialog.get_class())
    window.changemyclass()
    window.mysectionEntry.setText(startupdialog.get_section())
    window.changemysection()
    startupdialog.close()


if __name__ == "__main__":
    if Path("./debug").exists():
        logging.basicConfig(
            format=(
                "[%(asctime)s] %(levelname)s %(module)s - "
                "%(funcName)s Line %(lineno)d:\n%(message)s"
            ),
            datefmt="%H:%M:%S",
            level=logging.INFO,
        )
    else:
        logging.basicConfig(
            format=(
                "[%(asctime)s] %(levelname)s %(module)s - "
                "%(funcName)s Line %(lineno)d:\n%(message)s"
            ),
            datefmt="%H:%M:%S",
            level=logging.WARNING,
        )
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    font_dir = relpath("font")
    families = load_fonts_from_dir(os.fspath(font_dir))
    logging.info(families)
    window = MainWindow()
    window.setWindowTitle(f"K6GTE Winter Field Day Logger v{__version__}")
    window.show()
    window.read_cw_macros()
    # window.create_db()
    window.changeband()
    window.changemode()
    if (
        window.preference["mycallsign"] == ""
        or window.preference["myclass"] == ""
        or window.preference["mysection"] == ""
    ):
        startupdialog = Startup()
        startupdialog.accepted.connect(startup_dialog_finished)
        startupdialog.open()
        startupdialog.set_callsign(window.preference["mycallsign"])
        startupdialog.set_class(window.preference["myclass"])
        startupdialog.set_section(window.preference["mysection"])
    window.read_cw_macros()
    # window.setup_qrz()
    window.cloudlogauth()
    window.stats()
    window.read_sections()
    window.read_scp()
    window.logwindow()
    window.sections()
    window.callsign_entry.setFocus()

    timer = QtCore.QTimer()
    timer.timeout.connect(window.update_time)
    timer.start(1000)

    sys.exit(app.exec())
