#!/usr/bin/env python3

# Nothing to see here move along.
# xplanet -body earth -window -longitude -117 -latitude 38 -config Default -projection azmithal -radius 200 -wait 5

import xmlrpc.client
import requests
import sys
import sqlite3
import socket
import os
import logging

from json import dumps
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QFontDatabase
from datetime import datetime
from sqlite3 import Error
from pathlib import Path
from shutil import copyfile
from xmlrpc.client import ServerProxy, Error


def relpath(filename):
    try:
        base_path = sys._MEIPASS  # pylint: disable=no-member
    except:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, filename)


def load_fonts_from_dir(directory):
    families = set()
    for fi in QDir(directory).entryInfoList(["*.ttf", "*.woff", "*.woff2"]):
        _id = QFontDatabase.addApplicationFont(fi.absoluteFilePath())
        families |= set(QFontDatabase.applicationFontFamilies(_id))
    return families


class qsoEdit(QtCore.QObject):
    """
    Custom qt event signal used when qso edited or deleted.
    """

    lineChanged = QtCore.pyqtSignal()


class MainWindow(QtWidgets.QMainWindow):
    database = "WFD.db"
    mycall = ""
    myclass = ""
    mysection = ""
    power = "0"
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
    markerfile = ".xplanet/markers/ham"
    usemarker = False
    oldfreq = 0
    oldmode = 0
    oldrfpower = 0
    basescore = 0
    powermult = 0
    fkeys = dict()
    keyerserver = "http://localhost:8000"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        uic.loadUi(self.relpath("main.ui"), self)
        self.listWidget.itemDoubleClicked.connect(self.qsoclicked)
        self.altpowerButton.clicked.connect(self.claimAltPower)
        self.outdoorsButton.clicked.connect(self.claimOutdoors)
        self.notathomeButton.clicked.connect(self.claimNotHome)
        self.satelliteButton.clicked.connect(self.claimSatellite)
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
        self.callsign_entry.editingFinished.connect(self.dupCheck)
        self.section_entry.textEdited.connect(self.sectionCheck)
        self.genLogButton.clicked.connect(self.generateLogs)
        self.radio_icon.setPixmap(QtGui.QPixmap(self.relpath("icon/radio_grey.png")))
        self.cloudlog_icon.setPixmap(QtGui.QPixmap(self.relpath("icon/cloud_grey.png")))
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

        self.server = xmlrpc.client.ServerProxy("http://localhost:12345")
        self.radiochecktimer = QtCore.QTimer()
        self.radiochecktimer.timeout.connect(self.Radio)
        self.radiochecktimer.start(1000)

    def relpath(self, filename):
        """
        If the program is packaged with pyinstaller, this is needed since all files will be in a temp folder during execution.
        """
        try:
            base_path = sys._MEIPASS  # pylint: disable=no-member
        except:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, filename)

    def readCWmacros(self):
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
            logging.debug("readCWmacros: copying default macro file.")
            copyfile(relpath("cwmacros.txt"), "./cwmacros.txt")
        with open("./cwmacros.txt", "r") as f:
            for line in f:
                try:
                    fkey, buttonname, cwtext = line.split("|")
                    self.fkeys[fkey.strip()] = (buttonname.strip(), cwtext.strip())
                except ValueError:
                    break
        if "F1" in self.fkeys.keys():
            self.F1.setText(f"F1: {self.fkeys['F1'][0]}")
            self.F1.setToolTip(self.fkeys["F1"][1])
        if "F2" in self.fkeys.keys():
            self.F2.setText(f"F2: {self.fkeys['F2'][0]}")
            self.F2.setToolTip(self.fkeys["F2"][1])
        if "F3" in self.fkeys.keys():
            self.F3.setText(f"F3: {self.fkeys['F3'][0]}")
            self.F3.setToolTip(self.fkeys["F3"][1])
        if "F4" in self.fkeys.keys():
            self.F4.setText(f"F4: {self.fkeys['F4'][0]}")
            self.F4.setToolTip(self.fkeys["F4"][1])
        if "F5" in self.fkeys.keys():
            self.F5.setText(f"F5: {self.fkeys['F5'][0]}")
            self.F5.setToolTip(self.fkeys["F5"][1])
        if "F6" in self.fkeys.keys():
            self.F6.setText(f"F6: {self.fkeys['F6'][0]}")
            self.F6.setToolTip(self.fkeys["F6"][1])
        if "F7" in self.fkeys.keys():
            self.F7.setText(f"F7: {self.fkeys['F7'][0]}")
            self.F7.setToolTip(self.fkeys["F7"][1])
        if "F8" in self.fkeys.keys():
            self.F8.setText(f"F8: {self.fkeys['F8'][0]}")
            self.F8.setToolTip(self.fkeys["F8"][1])
        if "F9" in self.fkeys.keys():
            self.F9.setText(f"F9: {self.fkeys['F9'][0]}")
            self.F9.setToolTip(self.fkeys["F9"][1])
        if "F10" in self.fkeys.keys():
            self.F10.setText(f"F10: {self.fkeys['F10'][0]}")
            self.F10.setToolTip(self.fkeys["F10"][1])
        if "F11" in self.fkeys.keys():
            self.F11.setText(f"F11: {self.fkeys['F11'][0]}")
            self.F11.setToolTip(self.fkeys["F11"][1])
        if "F12" in self.fkeys.keys():
            self.F12.setText(f"F12: {self.fkeys['F12'][0]}")
            self.F12.setToolTip(self.fkeys["F12"][1])

    def updateTime(self):
        """
        Update local and UTC time on screen.
        """
        now = datetime.now().isoformat(" ")[5:19].replace("-", "/")
        utcnow = datetime.utcnow().isoformat(" ")[5:19].replace("-", "/")
        self.localtime.setText(now)
        self.utctime.setText(utcnow)

    def settingspressed(self):
        """
        Get settings changes, Authorize to QRZ and Cloudlog if needed.
        """
        settingsdialog = Settings(self)
        settingsdialog.setup(self.database)
        settingsdialog.exec()
        self.infobox.clear()
        self.readpreferences()
        self.qrzauth()
        self.cloudlogauth()

    def has_internet(self):
        """
        Connect to a main DNS server to check connectivity.
        """
        try:
            socket.create_connection(("1.1.1.1", 53))
            return True
        except OSError:
            pass
        return False

    def qrzauth(self):
        """
        Get QRZ session key.
        """
        if self.useqrz and self.has_internet():
            try:
                payload = {"username": self.qrzname, "password": self.qrzpass}
                r = requests.get(self.qrzurl, params=payload, timeout=1.0)
                if r.status_code == 200 and r.text.find("<Key>") > 0:
                    self.qrzsession = r.text[
                        r.text.find("<Key>") + 5 : r.text.find("</Key>")
                    ]
                    self.QRZ_icon.setStyleSheet("color: rgb(128, 128, 0);")
                    logging.info("QRZ: Obtained session key.")
                else:
                    self.qrzsession = False
                    self.QRZ_icon.setStyleSheet("color: rgb(136, 138, 133);")
                if r.status_code == 200 and r.text.find("<Error>") > 0:
                    errorText = r.text[
                        r.text.find("<Error>") + 7 : r.text.find("</Error>")
                    ]
                    self.infobox.insertPlainText("\nQRZ Error: " + errorText + "\n")
                    logging.warning(f"QRZ Error: {errorText}")
            except requests.exceptions.RequestException as e:
                self.infobox.insertPlainText(f"****QRZ Error****\n{e}\n")
                logging.warning(f"QRZ Error: {e}")
        else:
            self.QRZ_icon.setStyleSheet("color: rgb(26, 26, 26);")
            self.qrzsession = False

    def cloudlogauth(self):
        """
        Check if user has valid Cloudlog API key.
        """
        self.cloudlog_icon.setPixmap(QtGui.QPixmap(self.relpath("icon/cloud_grey.png")))
        self.cloudlogauthenticated = False
        if self.usecloudlog:
            try:
                self.cloudlog_icon.setPixmap(
                    QtGui.QPixmap(self.relpath("icon/cloud_red.png"))
                )
                test = self.cloudlogurl[:-3] + "auth/" + self.cloudlogapi
                r = requests.get(test, params={}, timeout=2.0)
                if r.status_code == 200 and r.text.find("<status>") > 0:
                    if (
                        r.text[r.text.find("<status>") + 8 : r.text.find("</status>")]
                        == "Valid"
                    ):
                        self.cloudlogauthenticated = True
                        self.cloudlog_icon.setPixmap(
                            QtGui.QPixmap(self.relpath("icon/cloud_green.png"))
                        )
                        logging.info("Cloudlog: Authenticated.")
                else:
                    logging.warning(
                        f"Cloudlog: {r.status_code} Unable to authenticate."
                    )
            except requests.exceptions.RequestException as e:
                self.infobox.insertPlainText(f"****Cloudlog Auth Error:****\n{e}\n")
                logging.warning(f"Cloudlog: {e}")

    def getband(self, freq):
        """
        Convert a (float) frequency into a (string) band.
        Returns a (string) band.
        Returns a "0" if frequency is out of band.
        """
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

    def getmode(self, rigmode):
        """
        Change what rigctld returned for the mode to the cabrillo mode for logging.
        """
        if rigmode == "CW" or rigmode == "CWR":
            return "CW"
        if rigmode == "USB" or rigmode == "LSB" or rigmode == "FM" or rigmode == "AM":
            return "PH"
        return "DI"  # All else digital

    def setband(self, theband):
        """
        Takes a band in meters and programatically changes the onscreen dropdown to match.
        """
        self.band_selector.setCurrentIndex(self.band_selector.findText(theband))
        self.changeband()

    def setmode(self, themode):
        """
        Takes a string for the mode (CW, PH, DI) and programatically changes the onscreen dropdown.
        """
        self.mode_selector.setCurrentIndex(self.mode_selector.findText(themode))
        self.changemode()

    def pollRadio(self):
        """
        Poll rigctld to get power band and mode of the radio.
        """
        if self.rigonline:
            try:
                newfreq = self.server.rig.get_vfo()
                newmode = self.server.rig.get_mode()
                self.radio_icon.setPixmap(
                    QtGui.QPixmap(self.relpath("icon/radio_green.png"))
                )
                # or newrfpower != self.oldrfpower:
                if newfreq != self.oldfreq or newmode != self.oldmode:
                    self.oldfreq = newfreq
                    self.oldmode = newmode
                    self.setband(str(self.getband(newfreq)))
                    self.setmode(str(self.getmode(newmode)))
            except:
                self.rigonline = False
                self.radio_icon.setPixmap(
                    QtGui.QPixmap(self.relpath("icon/radio_red.png"))
                )

    def checkRadio(self):
        """
        Checks to see if rigctld daemon is running.
        """
        if self.userigctl:
            self.rigonline = True
            try:
                self.server = xmlrpc.client.ServerProxy(
                    f"http://{self.rigctrlhost}:{self.rigctrlport}"
                )
                self.radio_icon.setPixmap(
                    QtGui.QPixmap(self.relpath("icon/radio_red.png"))
                )
            except:
                self.rigonline = False
                self.radio_icon.setPixmap(
                    QtGui.QPixmap(self.relpath("icon/radio_grey.png"))
                )
        else:
            self.rigonline = False

    def Radio(self):
        """
        Check for connection to rigctld. if it's there, poll it for radio status.
        """
        self.checkRadio()
        self.pollRadio()

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

    def processMacro(self, macro):
        macro = macro.upper()
        macro = macro.replace("{MYCALL}", self.mycall)
        macro = macro.replace("{MYCLASS}", self.myclass)
        macro = macro.replace("{MYSECT}", self.mysection)
        macro = macro.replace("{HISCALL}", self.callsign_entry.text())
        return macro

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.clearinputs()
        if event.key() == Qt.Key_Tab:
            if self.section_entry.hasFocus():
                logging.debug(f"From section")
                self.callsign_entry.setFocus()
                self.callsign_entry.deselect()
                self.callsign_entry.end(False)
                return
            if self.class_entry.hasFocus():
                logging.debug(f"From class")
                self.section_entry.setFocus()
                self.section_entry.deselect()
                self.section_entry.end(False)
                return
            if self.callsign_entry.hasFocus():
                logging.debug(f"From callsign")
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

    def sendcw(self, texttosend):
        with ServerProxy(self.keyerserver) as proxy:
            try:
                proxy.k1elsendstring(texttosend)
            except Error as e:
                logging.debug(f"{self.keyerserver}, xmlrpc error: {e}")
            except ConnectionRefusedError:
                logging.debug(f"{self.keyerserver}, xmlrpc Connection Refused")

    def sendf1(self):
        self.sendcw(self.processMacro(self.F1.toolTip()))

    def sendf2(self):
        self.sendcw(self.processMacro(self.F2.toolTip()))

    def sendf3(self):
        self.sendcw(self.processMacro(self.F3.toolTip()))

    def sendf4(self):
        self.sendcw(self.processMacro(self.F4.toolTip()))

    def sendf5(self):
        self.sendcw(self.processMacro(self.F5.toolTip()))

    def sendf6(self):
        self.sendcw(self.processMacro(self.F6.toolTip()))

    def sendf7(self):
        self.sendcw(self.processMacro(self.F7.toolTip()))

    def sendf8(self):
        self.sendcw(self.processMacro(self.F8.toolTip()))

    def sendf9(self):
        self.sendcw(self.processMacro(self.F9.toolTip()))

    def sendf10(self):
        self.sendcw(self.processMacro(self.F10.toolTip()))

    def sendf11(self):
        self.sendcw(self.processMacro(self.F11.toolTip()))

    def sendf12(self):
        self.sendcw(self.processMacro(self.F12.toolTip()))

    def clearinputs(self):
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
        self.power = str(self.power_selector.value())
        self.oldrfpower = self.power
        self.writepreferences()

    def changemycall(self):
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
        if self.mycall != "":
            self.mycallEntry.setStyleSheet("border: 1px solid green;")
        else:
            self.mycallEntry.setStyleSheet("border: 1px solid red;")
        self.writepreferences()

    def changemyclass(self):
        text = self.myclassEntry.text()
        if len(text):
            if text[-1] == " ":
                self.myclassEntry.setText(text.strip())
            else:
                cleaned = "".join(ch for ch in text if ch.isalnum()).upper()
                self.myclassEntry.setText(cleaned)
        self.myclass = self.myclassEntry.text()
        if self.myclass != "":
            self.myclassEntry.setStyleSheet("border: 1px solid green;")
        else:
            self.myclassEntry.setStyleSheet("border: 1px solid red;")
        self.writepreferences()

    def changemysection(self):
        text = self.mysectionEntry.text()
        if len(text):
            if text[-1] == " ":
                self.mysectionEntry.setText(text.strip())
            else:
                cleaned = "".join(ch for ch in text if ch.isalpha()).upper()
                self.mysectionEntry.setText(cleaned)
        self.mysection = self.mysectionEntry.text()
        if self.mysection != "":
            self.mysectionEntry.setStyleSheet("border: 1px solid green;")
        else:
            self.mysectionEntry.setStyleSheet("border: 1px solid red;")
        self.writepreferences()

    def calltest(self):
        """
        Cleans callsign of spaces and strips non alphanumeric or '/' characters.
        """
        text = self.callsign_entry.text()
        if len(text):
            if text[-1] == " ":
                self.callsign_entry.setText(text.strip())
                self.class_entry.setFocus()
                self.class_entry.deselect()
            else:
                washere = self.callsign_entry.cursorPosition()
                cleaned = "".join(
                    ch for ch in text if ch.isalnum() or ch == "/"
                ).upper()
                self.callsign_entry.setText(cleaned)
                self.callsign_entry.setCursorPosition(washere)
                self.superCheck()

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

    def create_DB(self):
        """create a database and table if it does not exist"""
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                sql_table = """ CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY, callsign text NOT NULL, class text NOT NULL, section text NOT NULL, date_time text NOT NULL, band text NOT NULL, mode text NOT NULL, power INTEGER NOT NULL, grid text NOT NULL, opname text NOT NULL); """
                c.execute(sql_table)
                sql_table = """ CREATE TABLE IF NOT EXISTS preferences (id INTEGER PRIMARY KEY, mycallsign TEXT DEFAULT '', myclass TEXT DEFAULT '', mysection TEXT DEFAULT '', power TEXT DEFAULT '0', altpower INTEGER DEFAULT 0, outdoors INTEGER DEFAULT 0, notathome INTEGER DEFAULT 0, satellite INTEGER DEFAULT 0, qrzusername TEXT DEFAULT 'w1aw', qrzpassword TEXT default 'secret', qrzurl TEXT DEFAULT 'https://xmldata.qrz.com/xml/',cloudlogapi TEXT DEFAULT 'cl12345678901234567890', cloudlogurl TEXT DEFAULT 'http://www.yoururl.com/Cloudlog/index.php/api/qso', useqrz INTEGER DEFAULT 0, usecloudlog INTEGER DEFAULT 0, userigcontrol INTEGER DEFAULT 0, rigcontrolip TEXT DEFAULT '127.0.0.1', rigcontrolport TEXT DEFAULT '12345',markerfile TEXT default 'secret', usemarker INTEGER DEFAULT 0, usehamdb INTEGER DEFAULT 0); """
                c.execute(sql_table)
                conn.commit()
        except Error as e:
            logging.critical(f"create_DB: Unable to create database: {e}")

    def highlighted(self, state):
        """
        Return CSS foreground highlight color if state is true,
        otherwise return an empty string.
        """
        if state:
            return "color: rgb(245, 121, 0);"
        else:
            return ""

    def readpreferences(self):
        """
        Restore preferences if they exist, otherwise create some sane defaults.
        """
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute("select * from preferences where id = 1")
                pref = c.fetchall()
                if len(pref) > 0:
                    for x in pref:
                        (
                            _,
                            self.mycall,
                            self.myclass,
                            self.mysection,
                            self.power,
                            self.altpower,
                            self.outdoors,
                            self.notathome,
                            self.satellite,
                            self.qrzname,
                            self.qrzpass,
                            self.qrzurl,
                            self.cloudlogapi,
                            self.cloudlogurl,
                            useqrz,
                            usecloudlog,
                            userigcontrol,
                            self.rigctrlhost,
                            self.rigctrlport,
                            self.markerfile,
                            self.usemarker,
                            self.usehamdb,
                        ) = x
                        self.altpower = bool(self.altpower)
                        self.altpowerButton.setStyleSheet(
                            self.highlighted(self.altpower)
                        )
                        self.outdoors = bool(self.outdoors)
                        self.outdoorsButton.setStyleSheet(
                            self.highlighted(self.outdoors)
                        )
                        self.notathome = bool(self.notathome)
                        self.notathomeButton.setStyleSheet(
                            self.highlighted(self.notathome)
                        )
                        self.satellite = bool(self.satellite)
                        self.satelliteButton.setStyleSheet(
                            self.highlighted(self.satellite)
                        )
                        self.mycallEntry.setText(self.mycall)
                        self.myclassEntry.setText(self.myclass)
                        self.mysectionEntry.setText(self.mysection)
                        self.power_selector.setValue(int(self.power))
                        self.usecloudlog = bool(usecloudlog)
                        self.useqrz = bool(useqrz)
                        self.userigctl = bool(userigcontrol)
                        self.usemarker = bool(self.usemarker)
                        self.usehamdb = bool(self.usehamdb)
                else:
                    sql = f"INSERT INTO preferences(id, mycallsign, myclass, mysection, power, altpower, outdoors, notathome, satellite, markerfile, usemarker, usehamdb) VALUES(1,'{self.mycall}','{self.myclass}','{self.mysection}','{self.power}',{int(self.altpower)},{int(self.outdoors)},{int(self.notathome)},{int(self.satellite)},'{self.markerfile}',{int(self.usemarker)},{int(self.usehamdb)})"
                    c.execute(sql)
                    conn.commit()
                    self.power_selector.setValue(int(self.power))
        except Error as e:
            logging.critical(f"readpreferences: {e}")

    def writepreferences(self):
        """
        Stores preferences into the 'preferences' sql table.
        """
        try:
            with sqlite3.connect(self.database) as conn:
                sql = f"UPDATE preferences SET mycallsign = '{self.mycall}', myclass = '{self.myclass}', mysection = '{self.mysection}', power = '{self.power_selector.value()}', altpower = {int(self.altpower)}, outdoors = {int(self.outdoors)}, notathome = {int(self.notathome)}, satellite = {int(self.satellite)}, markerfile = '{self.markerfile}', usemarker = {int(self.usemarker)}, usehamdb = {int(self.usehamdb)} WHERE id = 1"
                cur = conn.cursor()
                cur.execute(sql)
                conn.commit()
        except Error as e:
            logging.critical(f"writepreferences: {e}")

    def log_contact(self):
        if (
            len(self.callsign_entry.text()) == 0
            or len(self.class_entry.text()) == 0
            or len(self.section_entry.text()) == 0
        ):
            return
        grid, opname = self.qrzlookup(self.callsign_entry.text())
        contact = (
            self.callsign_entry.text(),
            self.class_entry.text(),
            self.section_entry.text(),
            self.band,
            self.mode,
            int(self.power_selector.value()),
            grid,
            opname,
        )
        try:
            with sqlite3.connect(self.database) as conn:
                sql = "INSERT INTO contacts(callsign, class, section, date_time, band, mode, power, grid, opname) VALUES(?,?,?,datetime('now'),?,?,?,?,?)"
                cur = conn.cursor()
                logging.info(f"log_contact: {sql} : {contact}")
                cur.execute(sql, contact)
                conn.commit()
        except Error as e:
            logging.critical(f"log_ontact: {e}")
        self.sections()
        self.stats()
        self.updatemarker()
        self.logwindow()
        self.clearinputs()
        self.postcloudlog()

    def stats(self):
        """
        Get an idea of how you're doing points wise.
        """
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute("select count(*) from contacts where mode = 'CW'")
                self.Total_CW.setText(str(c.fetchone()[0]))
                c.execute("select count(*) from contacts where mode = 'PH'")
                self.Total_Phone.setText(str(c.fetchone()[0]))
                c.execute("select count(*) from contacts where mode = 'DI'")
                self.Total_Digital.setText(str(c.fetchone()[0]))
                c.execute("select distinct band, mode from contacts")
                self.bandmodemult = len(c.fetchall())
                c.execute(
                    "SELECT count(*) FROM contacts where datetime(date_time) >=datetime('now', '-15 Minutes')"
                )
                self.QSO_Last15.setText(str(c.fetchone()[0]))
                c.execute(
                    "SELECT count(*) FROM contacts where datetime(date_time) >=datetime('now', '-1 Hours')"
                )
                self.QSO_PerHour.setText(str(c.fetchone()[0]))
                self.QSO_Points.setText(str(self.calcscore()))
        except Error as e:
            logging.critical(f"stats: {e}")

    def calcscore(self):
        """
        Return our current score based on operating power, band / mode multipliers and types of contacts.
        """
        self.qrpcheck()
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute("select count(*) as cw from contacts where mode = 'CW'")
                cw = str(c.fetchone()[0])
                c.execute("select count(*) as ph from contacts where mode = 'PH'")
                ph = str(c.fetchone()[0])
                c.execute("select count(*) as di from contacts where mode = 'DI'")
                di = str(c.fetchone()[0])
                c.execute("select distinct band, mode from contacts")
                self.bandmodemult = len(c.fetchall())
        except Error as e:
            logging.critical(f"calcscore: {e}")
            return 0
        self.score = (int(cw) * 2) + int(ph) + (int(di) * 2)
        self.basescore = self.score
        self.powermult = 0  # 2022 rules, no highpower allowed
        if self.qrp:
            self.powermult = 4
            self.score = self.score * 4
        elif not (self.highpower):
            self.powermult = 2
            self.score = self.score * 2
        self.score = self.score * self.bandmodemult
        # 2022 rules, bonuses down from 1500 to 500 each.
        self.score = (
            self.score
            + (500 * self.altpower)
            + (500 * self.outdoors)
            + (500 * self.notathome)
            + (500 * self.satellite)
        )
        return self.score

    def qrpcheck(self):
        """qrp = 5W cw, 10W ph and di, highpower greater than 100W"""
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute(
                    "select count(*) as qrpc from contacts where mode = 'CW' and power > 5"
                )
                log = c.fetchall()
                qrpc = list(log[0])[0]
                c.execute(
                    "select count(*) as qrpp from contacts where mode = 'PH' and power > 10"
                )
                log = c.fetchall()
                qrpp = list(log[0])[0]
                c.execute(
                    "select count(*) as qrpd from contacts where mode = 'DI' and power > 10"
                )
                log = c.fetchall()
                qrpd = list(log[0])[0]
                c.execute(
                    "select count(*) as highpower from contacts where power > 100"
                )
                log = c.fetchall()
                self.highpower = bool(list(log[0])[0])
                self.qrp = not (qrpc + qrpp + qrpd)
        except Error as e:
            logging.critical(f"qrpcheck: {e}")

    def logwindow(self):
        self.listWidget.clear()
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute("select * from contacts order by date_time desc")
                log = c.fetchall()
        except Error as e:
            logging.critical(f"logwindow: {e}")
            return
        for x in log:
            logid, hiscall, hisclass, hissection, datetime, band, mode, power, _, _ = x
            logline = f"{str(logid).rjust(3,'0')} {hiscall.ljust(10)} {hisclass.rjust(3)} {hissection.rjust(3)} {datetime} {str(band).rjust(3)} {mode} {str(power).rjust(3)}"
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
        dialog = editQSODialog(self)
        dialog.setup(self.linetopass, self.database)
        dialog.change.lineChanged.connect(self.qsoedited)
        dialog.open()

    def readSections(self):
        """
        Reads in the ARRL sections into some internal dictionaries.
        """
        try:
            with open(self.relpath("arrl_sect.dat"), "r") as fd:  # read section data
                while 1:
                    ln = fd.readline().strip()  # read a line and put in db
                    if not ln:
                        break
                    if ln[0] == "#":
                        continue
                    try:
                        _, st, canum, abbrev, name = str.split(ln, None, 4)
                        self.secName[abbrev] = abbrev + " " + name + " " + canum
                        self.secState[abbrev] = st
                        for i in range(len(abbrev) - 1):
                            p = abbrev[: -i - 1]
                            self.secPartial[p] = 1
                    except ValueError as e:
                        logging.warning(f"readSections: {e}")
        except IOError as e:
            logging.critical(f"readSections: read error: {e}")

    def sectionCheck(self):
        """
        Shows you the possible section matches based on what you have typed in the section input filed.
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

    def readSCP(self):
        """
        Reads in a list of known contesters into an internal dictionary
        """
        try:
            with open(self.relpath("MASTER.SCP"), "r") as f:
                self.scp = f.readlines()
                self.scp = list(map(lambda x: x.strip(), self.scp))
        except IOError as e:
            logging.critical(f"readSCP: read error: {e}")

    def superCheck(self):
        """
        Performs a supercheck partial on the callsign entered in the field.
        """
        self.infobox.clear()
        self.infobox.setTextColor(QtGui.QColor(211, 215, 207))
        acall = self.callsign_entry.text()
        if len(acall) > 2:
            matches = list(filter(lambda x: x.startswith(acall), self.scp))
            for x in matches:
                self.infobox.insertPlainText(x + " ")

    def dupCheck(self):
        acall = self.callsign_entry.text()
        self.infobox.clear()
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute(
                    f"select callsign, class, section, band, mode from contacts where callsign like '{acall}' order by band"
                )
                log = c.fetchall()
        except Error as e:
            logging.critical(f"dupCheck: {e}")
            return
        for x in log:
            hiscall, hisclass, hissection, hisband, hismode = x
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

    def workedSections(self):
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute("select distinct section from contacts")
                all_rows = c.fetchall()
        except Error as e:
            logging.critical(f"workedSections: {e}")
            return
        self.wrkdsections = str(all_rows)
        self.wrkdsections = (
            self.wrkdsections.replace("('", "")
            .replace("',), ", ",")
            .replace("',)]", "")
            .replace("[", "")
            .split(",")
        )

    def workedSection(self, section):
        """
        Return CSS foreground value for section based on if it has been worked.
        """
        if section in self.wrkdsections:
            return "color: rgb(245, 121, 0);"
        else:
            return "color: rgb(136, 138, 133);"

    def sectionsCol1(self):
        self.Section_DX.setStyleSheet(self.workedSection("DX"))
        self.Section_CT.setStyleSheet(self.workedSection("CT"))
        self.Section_RI.setStyleSheet(self.workedSection("RI"))
        self.Section_EMA.setStyleSheet(self.workedSection("EMA"))
        self.Section_VT.setStyleSheet(self.workedSection("VT"))
        self.Section_ME.setStyleSheet(self.workedSection("ME"))
        self.Section_WMA.setStyleSheet(self.workedSection("WMA"))
        self.Section_NH.setStyleSheet(self.workedSection("NH"))
        self.Section_ENY.setStyleSheet(self.workedSection("ENY"))
        self.Section_NNY.setStyleSheet(self.workedSection("NNY"))
        self.Section_NLI.setStyleSheet(self.workedSection("NLI"))
        self.Section_SNJ.setStyleSheet(self.workedSection("SNJ"))
        self.Section_NNJ.setStyleSheet(self.workedSection("NNJ"))
        self.Section_WNY.setStyleSheet(self.workedSection("WNY"))

    def sectionsCol2(self):
        self.Section_DE.setStyleSheet(self.workedSection("DE"))
        self.Section_MDC.setStyleSheet(self.workedSection("MDC"))
        self.Section_EPA.setStyleSheet(self.workedSection("EPA"))
        self.Section_WPA.setStyleSheet(self.workedSection("WPA"))
        self.Section_AL.setStyleSheet(self.workedSection("AL"))
        self.Section_SC.setStyleSheet(self.workedSection("SC"))
        self.Section_GA.setStyleSheet(self.workedSection("GA"))
        self.Section_SFL.setStyleSheet(self.workedSection("SFL"))
        self.Section_KY.setStyleSheet(self.workedSection("KY"))
        self.Section_TN.setStyleSheet(self.workedSection("TN"))
        self.Section_NC.setStyleSheet(self.workedSection("NC"))
        self.Section_VA.setStyleSheet(self.workedSection("VA"))
        self.Section_NFL.setStyleSheet(self.workedSection("NFL"))
        self.Section_VI.setStyleSheet(self.workedSection("VI"))
        self.Section_PR.setStyleSheet(self.workedSection("PR"))
        self.Section_WCF.setStyleSheet(self.workedSection("WCF"))

    def sectionsCol3(self):
        self.Section_AR.setStyleSheet(self.workedSection("AR"))
        self.Section_NTX.setStyleSheet(self.workedSection("NTX"))
        self.Section_LA.setStyleSheet(self.workedSection("LA"))
        self.Section_OK.setStyleSheet(self.workedSection("OK"))
        self.Section_MS.setStyleSheet(self.workedSection("MS"))
        self.Section_STX.setStyleSheet(self.workedSection("STX"))
        self.Section_NM.setStyleSheet(self.workedSection("NM"))
        self.Section_WTX.setStyleSheet(self.workedSection("WTX"))
        self.Section_EB.setStyleSheet(self.workedSection("EB"))
        self.Section_SCV.setStyleSheet(self.workedSection("SCV"))
        self.Section_LAX.setStyleSheet(self.workedSection("LAX"))
        self.Section_SDG.setStyleSheet(self.workedSection("SDG"))
        self.Section_ORG.setStyleSheet(self.workedSection("ORG"))
        self.Section_SF.setStyleSheet(self.workedSection("SF"))
        self.Section_PAC.setStyleSheet(self.workedSection("PAC"))
        self.Section_SJV.setStyleSheet(self.workedSection("SJV"))
        self.Section_SB.setStyleSheet(self.workedSection("SB"))
        self.Section_SV.setStyleSheet(self.workedSection("SV"))

    def sectionsCol4(self):
        self.Section_AK.setStyleSheet(self.workedSection("AK"))
        self.Section_NV.setStyleSheet(self.workedSection("NV"))
        self.Section_AZ.setStyleSheet(self.workedSection("AZ"))
        self.Section_OR.setStyleSheet(self.workedSection("OR"))
        self.Section_EWA.setStyleSheet(self.workedSection("EWA"))
        self.Section_UT.setStyleSheet(self.workedSection("UT"))
        self.Section_ID.setStyleSheet(self.workedSection("ID"))
        self.Section_WWA.setStyleSheet(self.workedSection("WWA"))
        self.Section_MT.setStyleSheet(self.workedSection("MT"))
        self.Section_WY.setStyleSheet(self.workedSection("WY"))
        self.Section_MI.setStyleSheet(self.workedSection("MI"))
        self.Section_WV.setStyleSheet(self.workedSection("WV"))
        self.Section_OH.setStyleSheet(self.workedSection("OH"))
        self.Section_IL.setStyleSheet(self.workedSection("IL"))
        self.Section_WI.setStyleSheet(self.workedSection("WI"))
        self.Section_IN.setStyleSheet(self.workedSection("IN"))

    def sectionsCol5(self):
        self.Section_CO.setStyleSheet(self.workedSection("CO"))
        self.Section_MO.setStyleSheet(self.workedSection("MO"))
        self.Section_IA.setStyleSheet(self.workedSection("IA"))
        self.Section_ND.setStyleSheet(self.workedSection("ND"))
        self.Section_KS.setStyleSheet(self.workedSection("KS"))
        self.Section_NE.setStyleSheet(self.workedSection("NE"))
        self.Section_MN.setStyleSheet(self.workedSection("MN"))
        self.Section_SD.setStyleSheet(self.workedSection("SD"))
        self.Section_AB.setStyleSheet(self.workedSection("AB"))
        self.Section_NT.setStyleSheet(self.workedSection("NT"))
        self.Section_BC.setStyleSheet(self.workedSection("BC"))
        self.Section_ONE.setStyleSheet(self.workedSection("ONE"))
        self.Section_GTA.setStyleSheet(self.workedSection("GTA"))
        self.Section_ONN.setStyleSheet(self.workedSection("ONN"))
        self.Section_MAR.setStyleSheet(self.workedSection("MAR"))
        self.Section_ONS.setStyleSheet(self.workedSection("ONS"))
        self.Section_MB.setStyleSheet(self.workedSection("MB"))
        self.Section_QC.setStyleSheet(self.workedSection("QC"))
        self.Section_NL.setStyleSheet(self.workedSection("NL"))
        self.Section_SK.setStyleSheet(self.workedSection("SK"))
        self.Section_PE.setStyleSheet(self.workedSection("PE"))

    def sections(self):
        """
        Updates onscreen sections highlighting the ones worked.
        """
        self.workedSections()
        self.sectionsCol1()
        self.sectionsCol2()
        self.sectionsCol3()
        self.sectionsCol4()
        self.sectionsCol5()

    def claimAltPower(self, _):
        if self.altpower:
            self.altpower = False
        else:
            self.altpower = True
        self.altpowerButton.setStyleSheet(self.highlighted(self.altpower))
        self.writepreferences()
        self.stats()

    def claimOutdoors(self, _):
        if self.outdoors:
            self.outdoors = False
        else:
            self.outdoors = True
        self.outdoorsButton.setStyleSheet(self.highlighted(self.outdoors))
        self.writepreferences()
        self.stats()

    def claimNotHome(self, _):
        if self.notathome:
            self.notathome = False
        else:
            self.notathome = True
        self.notathomeButton.setStyleSheet(self.highlighted(self.notathome))
        self.writepreferences()
        self.stats()

    def claimSatellite(self, _):
        if self.satellite:
            self.satellite = False
        else:
            self.satellite = True
        self.satelliteButton.setStyleSheet(self.highlighted(self.satellite))
        self.writepreferences()
        self.stats()

    def getBandModeTally(self, band, mode):
        """
        Returns the amount of contacts and the maximum power used for a particular band/mode combination.
        """
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute(
                    f"select count(*) as tally, MAX(power) as mpow from contacts where band = '{band}' AND mode ='{mode}'"
                )
                return c.fetchone()
        except Error as e:
            logging.critical(f"getBandModeTally: {e}")

    def getbands(self):
        """
        Returns a list of bands worked, and an empty list if none worked.
        """
        bandlist = []
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute("select DISTINCT band from contacts")
                result = c.fetchall()
        except Error as e:
            logging.critical(f"getbands: {e}")
            return []
        if result:
            for returnedBand in result:
                bandlist.append(returnedBand[0])
            return bandlist
        return []

    def generateBandModeTally(self):
        bandlist = self.getbands()
        try:
            with open("Statistics.txt", "w") as f:
                print("\t\tCW\tPWR\tDI\tPWR\tPH\tPWR", end="\r\n", file=f)
                print("-" * 60, end="\r\n", file=f)
                for band in self.bands:
                    if band in bandlist:
                        cwt = self.getBandModeTally(band, "CW")
                        dit = self.getBandModeTally(band, "DI")
                        pht = self.getBandModeTally(band, "PH")
                        print(
                            f"Band:\t{band}\t{cwt[0]}\t{cwt[1]}\t{dit[0]}\t{dit[1]}\t{pht[0]}\t{pht[1]}",
                            end="\r\n",
                            file=f,
                        )
                        print("-" * 60, end="\r\n", file=f)
        except IOError as e:
            logging.critical("generateBandModeTally: write error: {e}")

    def getState(self, section):
        """
        Returns the US state a section is in, or Bool False if none was found.
        """
        try:
            state = self.secState[section]
            if state != "--":
                return state
        except:
            return False
        return False

    def gridtolatlon(self, maiden):
        """
        Converts a maidenhead gridsquare to a latitude longitude pair.
        """
        maiden = str(maiden).strip().upper()

        N = len(maiden)
        if not 8 >= N >= 2 and N % 2 == 0:
            return 0, 0

        lon = (ord(maiden[0]) - 65) * 20 - 180
        lat = (ord(maiden[1]) - 65) * 10 - 90

        if N >= 4:
            lon += (ord(maiden[2]) - 48) * 2
            lat += ord(maiden[3]) - 48

        if N >= 6:
            lon += (ord(maiden[4]) - 65) / 12 + 1 / 24
            lat += (ord(maiden[5]) - 65) / 24 + 1 / 48

        if N >= 8:
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
                    c = conn.cursor()
                    c.execute("select DISTINCT grid from contacts")
                    x = c.fetchall()
                if x:
                    lastcolor = ""
                    with open(filename, "w", encoding="ascii") as f:
                        islast = len(x) - 1
                        for count, grid in enumerate(x):
                            if count == islast:
                                lastcolor = "color=Orange"
                            if len(grid[0]) > 1:
                                lat, lon = self.gridtolatlon(grid[0])
                                print(f'{lat} {lon} "" {lastcolor}', end="\r\n", file=f)
            except IOError as e:
                logging.warning(f"updatemarker: error {e} writing to {filename}")
                self.infobox.setTextColor(QtGui.QColor(245, 121, 0))
                self.infobox.insertPlainText(f"Unable to write to {filename}\n")
            except Error as e:
                logging.critical(f"updatemarker: db error: {e}")

    def qrzlookup(self, call):
        grid = False
        name = False
        internet_good = self.has_internet()
        try:
            if self.qrzsession and self.useqrz and internet_good:
                payload = {"s": self.qrzsession, "callsign": call}
                r = requests.get(self.qrzurl, params=payload, timeout=3.0)
                if not r.text.find("<Key>"):  # key expired get a new one
                    logging.info("qrzlookup: no key, getting new one.")
                    self.qrzauth()
                    if self.qrzsession:
                        payload = {"s": self.qrzsession, "callsign": call}
                        r = requests.get(self.qrzurl, params=payload, timeout=3.0)
                grid, name = self.parseLookup(r)
            elif self.usehamdb and internet_good:
                logging.info("qrzlookup: using hamdb for the lookup.")
                r = requests.get(
                    f"http://api.hamdb.org/{call}/xml/k6gtewfdlogger", timeout=3.0
                )
                grid, name = self.parseLookup(r)
        except:
            logging.warning("qrzlookup: lookup failed.")
            self.infobox.insertPlainText(f"Something Smells...\n")
        return grid, name

    def parseLookup(self, r):
        """
        Returns gridsquare and name for a callsign looked up by qrz or hamdb.
        Or False for both if none found or error.
        """
        grid = False
        name = False
        try:
            if r.status_code == 200:
                if r.text.find("<Error>") > 0:
                    errorText = r.text[
                        r.text.find("<Error>") + 7 : r.text.find("</Error>")
                    ]
                    logging.warning(f"parseLookup: {errorText}")
                    self.infobox.insertPlainText(f"\nQRZ/HamDB Error: {errorText}\n")
                if r.text.find("<grid>") > 0:
                    grid = r.text[r.text.find("<grid>") + 6 : r.text.find("</grid>")]
                if r.text.find("<fname>") > 0:
                    name = r.text[r.text.find("<fname>") + 7 : r.text.find("</fname>")]
                if r.text.find("<name>") > 0:
                    if not name:
                        name = r.text[
                            r.text.find("<name>") + 6 : r.text.find("</name>")
                        ]
                    else:
                        name += (
                            " "
                            + r.text[r.text.find("<name>") + 6 : r.text.find("</name>")]
                        )
        except:
            logging.warning("parseLookup: Lookup failed.")
            self.infobox.insertPlainText(f"Lookup Failed...\n")
        return grid, name

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
                c = conn.cursor()
                c.execute("select * from contacts order by date_time ASC")
                log = c.fetchall()
        except Error as e:
            logging.critical(f"adif: db error: {e}")
            return
        grid = False
        opname = False
        try:
            with open(logname, "w", encoding="ascii") as f:
                print("<ADIF_VER:5>2.2.0", end="\r\n", file=f)
                print("<EOH>", end="\r\n", file=f)
                for x in log:
                    (
                        _,
                        hiscall,
                        hisclass,
                        hissection,
                        datetime,
                        band,
                        mode,
                        _,
                        grid,
                        opname,
                    ) = x
                    if mode == "DI":
                        mode = "RTTY"
                    if mode == "PH":
                        mode = "SSB"
                    if mode == "CW":
                        rst = "599"
                    else:
                        rst = "59"
                    loggeddate = datetime[:10]
                    loggedtime = datetime[11:13] + datetime[14:16]
                    print(
                        f"<QSO_DATE:{len(''.join(loggeddate.split('-')))}:d>{''.join(loggeddate.split('-'))}",
                        end="\r\n",
                        file=f,
                    )
                    print(
                        f"<TIME_ON:{len(loggedtime)}>{loggedtime}", end="\r\n", file=f
                    )
                    print(f"<CALL:{len(hiscall)}>{hiscall}", end="\r\n", file=f)
                    print(f"<MODE:{len(mode)}>{mode}", end="\r\n", file=f)
                    print(f"<BAND:{len(band + 'M')}>{band + 'M'}", end="\r\n", file=f)
                    try:
                        print(
                            f"<FREQ:{len(self.dfreq[band])}>{self.dfreq[band]}",
                            end="\r\n",
                            file=f,
                        )
                    except:
                        pass  # This is bad form... I can't remember why this is in a try block
                    print(f"<RST_SENT:{len(rst)}>{rst}", end="\r\n", file=f)
                    print(f"<RST_RCVD:{len(rst)}>{rst}", end="\r\n", file=f)
                    print(
                        f"<STX_STRING:{len(self.myclass + ' ' + self.mysection)}>{self.myclass + ' ' + self.mysection}",
                        end="\r\n",
                        file=f,
                    )
                    print(
                        f"<SRX_STRING:{len(hisclass + ' ' + hissection)}>{hisclass + ' ' + hissection}",
                        end="\r\n",
                        file=f,
                    )
                    print(
                        f"<ARRL_SECT:{len(hissection)}>{hissection}", end="\r\n", file=f
                    )
                    print(f"<CLASS:{len(hisclass)}>{hisclass}", end="\r\n", file=f)
                    state = self.getState(hissection)
                    if state:
                        print(f"<STATE:{len(state)}>{state}", end="\r\n", file=f)
                    if len(grid) > 1:
                        print(f"<GRIDSQUARE:{len(grid)}>{grid}", end="\r\n", file=f)
                    if len(opname) > 1:
                        print(f"<NAME:{len(opname)}>{opname}", end="\r\n", file=f)
                    comment = "WINTER-FIELD-DAY"
                    print(f"<COMMENT:{len(comment)}>{comment}", end="\r\n", file=f)
                    print("<EOR>", end="\r\n", file=f)
                    print("", end="\r\n", file=f)
        except IOError as e:
            logging.critical(f"adif: IO error: {e}")
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
                c = conn.cursor()
                c.execute("select * from contacts order by id DESC")
                q = c.fetchone()
        except Error as e:
            logging.critical(f"postcloudlog: db error: {e}")
            return
        _, hiscall, hisclass, hissection, datetime, band, mode, _, grid, opname = q

        if mode == "DI":
            mode = "RTTY"
        if mode == "PH":
            mode = "SSB"
        if mode == "CW":
            rst = "599"
        else:
            rst = "59"
        loggeddate = datetime[:10]
        loggedtime = datetime[11:13] + datetime[14:16]
        adifq = f"<QSO_DATE:{len(''.join(loggeddate.split('-')))}:d>{''.join(loggeddate.split('-'))}"
        adifq += f"<TIME_ON:{len(loggedtime)}>{loggedtime}"
        adifq += f"<CALL:{len(hiscall)}>{hiscall}"
        adifq += f"<MODE:{len(mode)}>{mode}"
        adifq += f"<BAND:{len(band + 'M')}>{band + 'M'}"
        adifq += f"<FREQ:{len(self.dfreq[band])}>{self.dfreq[band]}"
        adifq += f"<RST_SENT:{len(rst)}>{rst}"
        adifq += f"<RST_RCVD:{len(rst)}>{rst}"
        adifq += f"<STX_STRING:{len(self.myclass + ' ' + self.mysection)}>{self.myclass + ' ' + self.mysection}"
        adifq += f"<SRX_STRING:{len(hisclass + ' ' + hissection)}>{hisclass + ' ' + hissection}"
        adifq += f"<ARRL_SECT:{len(hissection)}>{hissection}"
        adifq += f"<CLASS:{len(hisclass)}>{hisclass}"
        state = self.getState(hissection)
        if state:
            adifq += f"<STATE:{len(state)}>{state}"
        if len(grid) > 1:
            adifq += f"<GRIDSQUARE:{len(grid)}>{grid}"
        if len(opname) > 1:
            adifq += f"<NAME:{len(opname)}>{opname}"
        comment = "Winter Field Day"
        adifq += f"<COMMENT:{len(comment)}>{comment}"
        adifq += "<EOR>"

        payloadDict = {"key": self.cloudlogapi, "type": "adif", "string": adifq}
        jsonData = dumps(payloadDict)
        _ = requests.post(self.cloudlogurl, jsonData)

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
                c = conn.cursor()
                c.execute("select * from contacts order by date_time ASC")
                log = c.fetchall()
        except Error as e:
            logging.critical(f"cabrillo: db error: {e}")
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
            with open(filename, "w", encoding="ascii") as f:
                print("START-OF-LOG: 3.0", end="\r\n", file=f)
                print("CREATED-BY: K6GTE Winter Field Day Logger", end="\r\n", file=f)
                print("CONTEST: WFD", end="\r\n", file=f)
                print(f"CALLSIGN: {self.mycall}", end="\r\n", file=f)
                print("LOCATION:", end="\r\n", file=f)
                print(f"ARRL-SECTION: {self.mysection}", end="\r\n", file=f)
                print(f"CATEGORY: {self.myclass}", end="\r\n", file=f)
                print(f"CATEGORY-POWER: {catpower}", end="\r\n", file=f)
                print(f"SOAPBOX: QSO Points {self.basescore}", end="\r\n", file=f)
                print(
                    f"SOAPBOX: Power Output Multiplier {self.powermult}",
                    end="\r\n",
                    file=f,
                )
                print(
                    f"SOAPBOX: Band/mode multiplier {self.bandmodemult}",
                    end="\r\n",
                    file=f,
                )
                if self.altpower:
                    print(
                        "SOAPBOX: 500 points for not using commercial power",
                        end="\r\n",
                        file=f,
                    )
                    bonuses = bonuses + 500
                if self.outdoors:
                    print(
                        "SOAPBOX: 500 points for setting up outdoors",
                        end="\r\n",
                        file=f,
                    )
                    bonuses = bonuses + 500
                if self.notathome:
                    print(
                        "SOAPBOX: 500 points for setting up away from home",
                        end="\r\n",
                        file=f,
                    )
                    bonuses = bonuses + 500
                if self.satellite:
                    print(
                        "SOAPBOX: 500 points for working satellite", end="\r\n", file=f
                    )
                    bonuses = bonuses + 500
                print(f"SOAPBOX: BONUS Total {bonuses}", end="\r\n", file=f)
                print(f"CLAIMED-SCORE: {self.calcscore()}", end="\r\n", file=f)
                print(f"OPERATORS: {self.mycall}", end="\r\n", file=f)
                print("NAME: ", end="\r\n", file=f)
                print("ADDRESS: ", end="\r\n", file=f)
                print("ADDRESS-CITY: ", end="\r\n", file=f)
                print("ADDRESS-STATE: ", end="\r\n", file=f)
                print("ADDRESS-POSTALCODE: ", end="\r\n", file=f)
                print("ADDRESS-COUNTRY: ", end="\r\n", file=f)
                print("EMAIL: ", end="\r\n", file=f)
                for x in log:
                    _, hiscall, hisclass, hissection, datetime, band, mode, _, _, _ = x
                    loggeddate = datetime[:10]
                    loggedtime = datetime[11:13] + datetime[14:16]
                    print(
                        f"QSO: {self.dfreq[band].replace('.','')} {mode} {loggeddate} {loggedtime} {self.mycall} {self.myclass} {self.mysection} {hiscall} {hisclass} {hissection}",
                        end="\r\n",
                        file=f,
                    )
                print("END-OF-LOG:", end="\r\n", file=f)
        except IOError as e:
            logging.critical(f"cabrillo: IO error: {e}, writing to {filename}")
            self.infobox.insertPlainText(" Failed\n\n")
            app.processEvents()
            return
        self.infobox.insertPlainText(" Done\n\n")
        app.processEvents()

    def generateLogs(self):
        self.infobox.clear()
        self.cabrillo()
        self.generateBandModeTally()
        self.adif()


class editQSODialog(QtWidgets.QDialog):

    theitem = ""
    database = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(self.relpath("dialog.ui"), self)
        self.deleteButton.clicked.connect(self.delete_contact)
        self.buttonBox.accepted.connect(self.saveChanges)
        self.change = qsoEdit()

    def setup(self, linetopass, thedatabase):
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

    def relpath(self, filename):
        try:
            base_path = sys._MEIPASS  # pylint: disable=no-member
        except:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, filename)

    def saveChanges(self):
        try:
            with sqlite3.connect(self.database) as conn:
                sql = f"update contacts set callsign = '{self.editCallsign.text().upper()}', class = '{self.editClass.text().upper()}', section = '{self.editSection.text().upper()}', date_time = '{self.editDateTime.text()}', band = '{self.editBand.currentText()}', mode = '{self.editMode.currentText()}', power = '{self.editPower.value()}'  where id={self.theitem}"
                cur = conn.cursor()
                cur.execute(sql)
                conn.commit()
        except Error as e:
            logging.critical(f"saveChanges: db error: {e}")
        self.change.lineChanged.emit()

    def delete_contact(self):
        try:
            with sqlite3.connect(self.database) as conn:
                sql = f"delete from contacts where id={self.theitem}"
                cur = conn.cursor()
                cur.execute(sql)
                conn.commit()
        except Error as e:
            logging.critical(f"delete_contact: db error: {e}")
        self.change.lineChanged.emit()
        self.close()


class Settings(QtWidgets.QDialog):
    """
    Setup settings dialog. Reads and stores settings to an sqlite db.
    Call setup() with filename of db.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(self.relpath("settings.ui"), self)
        self.buttonBox.accepted.connect(self.saveChanges)

    def setup(self, thedatabase):
        self.database = thedatabase
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute("select * from preferences where id = 1")
                pref = c.fetchall()
        except Error as e:
            logging.critical(f"settings setup: db error: {e}")
            return
        if len(pref) > 0:
            for x in pref:
                (
                    _,
                    _,
                    _,
                    _,
                    _,
                    _,
                    _,
                    _,
                    _,
                    qrzname,
                    qrzpass,
                    qrzurl,
                    cloudlogapi,
                    cloudlogurl,
                    useqrz,
                    usecloudlog,
                    userigcontrol,
                    rigctrlhost,
                    rigctrlport,
                    markerfile,
                    usemarker,
                    usehamdb,
                ) = x
                self.qrzname_field.setText(qrzname)
                self.qrzpass_field.setText(qrzpass)
                self.qrzurl_field.setText(qrzurl)
                self.cloudlogapi_field.setText(cloudlogapi)
                self.cloudlogurl_field.setText(cloudlogurl)
                self.rigcontrolip_field.setText(rigctrlhost)
                self.rigcontrolport_field.setText(rigctrlport)
                self.usecloudlog_checkBox.setChecked(bool(usecloudlog))
                self.useqrz_checkBox.setChecked(bool(useqrz))
                self.userigcontrol_checkBox.setChecked(bool(userigcontrol))
                self.markerfile_field.setText(markerfile)
                self.generatemarker_checkbox.setChecked(bool(usemarker))
                self.usehamdb_checkBox.setChecked(bool(usehamdb))

    def relpath(self, filename):
        try:
            base_path = sys._MEIPASS  # pylint: disable=no-member
        except:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, filename)

    def saveChanges(self):
        try:
            with sqlite3.connect(self.database) as conn:
                sql = f"UPDATE preferences SET qrzusername = '{self.qrzname_field.text()}', qrzpassword = '{self.qrzpass_field.text()}', qrzurl = '{self.qrzurl_field.text()}', cloudlogapi = '{self.cloudlogapi_field.text()}', cloudlogurl = '{self.cloudlogurl_field.text()}', rigcontrolip = '{self.rigcontrolip_field.text()}', rigcontrolport = '{self.rigcontrolport_field.text()}', useqrz = '{int(self.useqrz_checkBox.isChecked())}', usecloudlog = '{int(self.usecloudlog_checkBox.isChecked())}', userigcontrol = '{int(self.userigcontrol_checkBox.isChecked())}', markerfile = '{self.markerfile_field.text()}', usemarker = '{int(self.generatemarker_checkbox.isChecked())}', usehamdb = '{int(self.usehamdb_checkBox.isChecked())}'  where id=1;"
                cur = conn.cursor()
                cur.execute(sql)
                conn.commit()
        except Error as e:
            logging.critical(f"settings saveChanges: db error: {e}")


class Startup(QtWidgets.QDialog):
    """
    Show splash screen, get Op call, class, section
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(self.relpath("startup.ui"), self)
        self.continue_pushButton.clicked.connect(self.store)

    def relpath(self, filename):
        try:
            base_path = sys._MEIPASS  # pylint: disable=no-member
        except:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, filename)

    def setCallSign(self, callsign):
        self.dialog_callsign.setText(callsign)

    def setClass(self, myclass):
        self.dialog_class.setText(myclass)

    def setSection(self, mysection):
        self.dialog_section.setText(mysection)

    def getCallSign(self):
        return self.dialog_callsign.text()

    def getClass(self):
        return self.dialog_class.text()

    def getSection(self):
        return self.dialog_section.text()

    def store(self):
        self.accept()


def startupDialogFinished():
    """
    Store call, class, section enteries and close dialog
    """
    window.mycallEntry.setText(startupdialog.getCallSign())
    window.changemycall()
    window.myclassEntry.setText(startupdialog.getClass())
    window.changemyclass()
    window.mysectionEntry.setText(startupdialog.getSection())
    window.changemysection()
    startupdialog.close()


if __name__ == "__main__":
    if Path("./debug").exists():
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    font_dir = relpath("font")
    families = load_fonts_from_dir(os.fspath(font_dir))
    logging.info(families)
    window = MainWindow()
    window.show()
    window.create_DB()
    window.changeband()
    window.changemode()
    window.readpreferences()
    if window.mycall == "" or window.myclass == "" or window.mysection == "":
        startupdialog = Startup()
        startupdialog.accepted.connect(startupDialogFinished)
        startupdialog.open()
        startupdialog.setCallSign(window.mycall)
        startupdialog.setClass(window.myclass)
        startupdialog.setSection(window.mysection)
    window.readCWmacros()
    window.qrzauth()
    window.cloudlogauth()
    window.stats()
    window.readSections()
    window.readSCP()
    window.logwindow()
    window.sections()
    window.callsign_entry.setFocus()

    timer = QtCore.QTimer()
    timer.timeout.connect(window.updateTime)
    timer.start(1000)

    app.exec()
