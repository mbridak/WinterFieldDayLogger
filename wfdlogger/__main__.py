#!/usr/bin/env python3
"""
K6GTE Winter Field Day logger
Email: michael.bridak@gmail.com
GPL V3
"""

# pylint: disable=too-many-lines
# pylint: disable=invalid-name
# pylint: disable=no-member
# pylint: disable=no-name-in-module
# pylint: disable=c-extension-no-member

# Nothing to see here move along.
# xplanet -body earth -window -longitude -117 -latitude 38 -config Default
# -projection azmithal -radius 200 -wait 5

from math import radians, sin, cos, atan2, sqrt, asin, pi
import sys
import socket
import os
import logging
import threading
import uuid
import queue
import time
import pkgutil
from itertools import chain

from json import dumps, loads, JSONDecodeError
from datetime import datetime, timedelta
from pathlib import Path
from shutil import copyfile

from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QFontDatabase

import requests

try:
    from wfdlogger.lib.settings import Settings
except ModuleNotFoundError:
    from lib.settings import Settings

try:
    from wfdlogger.lib.database import DataBase
except ModuleNotFoundError:
    from lib.database import DataBase

try:
    from wfdlogger.lib.lookup import HamDBlookup, HamQTH, QRZlookup
except ModuleNotFoundError:
    from lib.lookup import HamDBlookup, HamQTH, QRZlookup

try:
    from wfdlogger.lib.cat_interface import CAT
except ModuleNotFoundError:
    from lib.cat_interface import CAT

try:
    from wfdlogger.lib.cwinterface import CW
except ModuleNotFoundError:
    from lib.cwinterface import CW

try:
    from wfdlogger.lib.n1mm import N1MM
except ModuleNotFoundError:
    from lib.n1mm import N1MM

try:
    from wfdlogger.lib.version import __version__
except ModuleNotFoundError:
    from lib.version import __version__


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
    mygrid = ""
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
        "60": "5.357",
        "40": "7.030",
        "30": "10.130",
        "20": "14.030",
        "17": "18.100",
        "15": "21.030",
        "12": "24.920",
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
    fkeys = {}
    run_state = False
    people = {}
    groupcall = None
    server_commands = []
    server_seen = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ui_path = os.path.dirname(pkgutil.get_loader("wfdlogger").get_filename())
        ui_path += "/data/main.ui"
        uic.loadUi(ui_path, self)
        self.db = DataBase(self.database)
        self.udp_fifo = queue.Queue()
        self.listWidget.itemDoubleClicked.connect(self.qsoclicked)
        self.run_button.clicked.connect(self.run_button_pressed)
        self.altpowerButton.clicked.connect(self.claim_alt_power)
        self.outdoorsButton.clicked.connect(self.claim_outdoors)
        self.notathomeButton.clicked.connect(self.claim_not_at_home)
        self.satelliteButton.clicked.connect(self.claim_satellite)
        self.antButton.clicked.connect(self.claim_ant)
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
        self.chat_entry.returnPressed.connect(self.send_chat)
        ui_path = os.path.dirname(pkgutil.get_loader("wfdlogger").get_filename())
        ui_path += "/icon/"
        self.radio_grey = QtGui.QPixmap(ui_path + "radio_grey.png")
        self.radio_red = QtGui.QPixmap(ui_path + "radio_red.png")
        self.radio_green = QtGui.QPixmap(ui_path + "radio_green.png")
        self.cloud_grey = QtGui.QPixmap(ui_path + "cloud_grey.png")
        self.cloud_red = QtGui.QPixmap(ui_path + "cloud_red.png")
        self.cloud_green = QtGui.QPixmap(ui_path + "cloud_green.png")
        self.radio_icon.setPixmap(self.radio_grey)
        self.cloudlog_icon.setPixmap(self.cloud_grey)
        self.QRZ_icon.setStyleSheet("color: rgb(136, 138, 133);")
        self.chat_window.hide()
        self.group_call_indicator.hide()
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
            "antenna": False,
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
        self.reference_preference = self.preference.copy()
        self.look_up = None
        self.cat_control = None
        self.cw = None
        self.connect_to_server = False
        self.multicast_group = None
        self.multicast_port = None
        self.interface_ip = None
        self._udpwatch = None
        self.readpreferences()

        self.radiochecktimer = QtCore.QTimer()
        self.radiochecktimer.timeout.connect(self.poll_radio)
        self.radiochecktimer.start(1000)

    def show_people(self):
        """Display operators"""
        rev_dict = {}
        for key, value in self.people.items():
            rev_dict.setdefault(value, set()).add(key)
        result = set(
            chain.from_iterable(
                values for key, values in rev_dict.items() if len(values) > 1
            )
        )
        self.users_list.clear()
        self.users_list.insertPlainText("    Operators\n")
        for op_callsign in self.people:
            if op_callsign in result:
                self.users_list.setTextColor(QtGui.QColor(245, 121, 0))
                self.users_list.insertPlainText(
                    f"{op_callsign.rjust(6,' ')} {self.people.get(op_callsign).rjust(6, ' ')}\n"
                )
                self.users_list.setTextColor(QtGui.QColor(211, 215, 207))
            else:
                self.users_list.insertPlainText(
                    f"{op_callsign.rjust(6,' ')} {self.people.get(op_callsign).rjust(6, ' ')}\n"
                )

    def show_dirty_records(self):
        """Checks for dirty records, Changes Generate Log button to give visual indication."""
        if self.connect_to_server:
            result = self.db.count_all_dirty_contacts()
            all_dirty_count = result.get("alldirty")
            if all_dirty_count:
                self.genLogButton.setStyleSheet("background-color: red;")
                self.genLogButton.setText(f"UnVfyd: {all_dirty_count}")
            else:
                self.genLogButton.setStyleSheet("background-color: rgb(92, 53, 102);")
                self.genLogButton.setText("Generate Logs")

    def resolve_dirty_records(self):
        """Go through dirty records and submit them to the server."""
        if self.connect_to_server:
            records = self.db.fetch_all_dirty_contacts()
            self.infobox.setTextColor(QtGui.QColor(211, 215, 207))
            self.infobox.insertPlainText(f"Resolving {len(records)} unsent contacts.\n")
            app.processEvents()
            if records:
                for count, dirty_contact in enumerate(records):
                    contact = {}
                    contact["cmd"] = "POST"
                    contact["station"] = self.preference.get("mycallsign")
                    stale = datetime.now() + timedelta(seconds=30)
                    contact["expire"] = stale.isoformat()
                    contact["unique_id"] = dirty_contact.get("unique_id")
                    contact["hiscall"] = dirty_contact.get("callsign")
                    contact["class"] = dirty_contact.get("class")
                    contact["section"] = dirty_contact.get("section")
                    contact["date_and_time"] = dirty_contact.get("date_time")
                    contact["frequency"] = dirty_contact.get("frequency")
                    contact["band"] = dirty_contact.get("band")
                    contact["mode"] = dirty_contact.get("mode")
                    contact["power"] = dirty_contact.get("power")
                    contact["grid"] = dirty_contact.get("grid")
                    contact["opname"] = dirty_contact.get("opname")
                    self.server_commands.append(contact)
                    bytesToSend = bytes(dumps(contact), encoding="ascii")
                    try:
                        self.server_udp.sendto(
                            bytesToSend,
                            (self.multicast_group, int(self.multicast_port)),
                        )
                    except OSError as err:
                        logging.warning("%s", err)
                    time.sleep(0.1)  # Do I need this?
                    self.infobox.insertPlainText(f"Sending {count}\n")
                    app.processEvents()

    def clear_dirty_flag(self, unique_id):
        """clear the dirty flag on record once response is returned from server."""
        self.db.clear_dirty_flag(unique_id)
        self.show_dirty_records()

    def remove_confirmed_commands(self, data):
        """Removed confirmed commands from the sent commands list."""
        for index, item in enumerate(self.server_commands):
            if item.get("unique_id") == data.get("unique_id") and item.get(
                "cmd"
            ) == data.get("subject"):
                self.server_commands.pop(index)
                self.clear_dirty_flag(data.get("unique_id"))
                self.infobox.insertPlainText(
                    f"Server Confirmed {data.get('subject')}\n"
                )

    def check_for_stale_commands(self):
        """
        Check through server commands to see if there has not been a reply in 30 seconds.
        Resubmits those that are stale.
        """
        if self.connect_to_server:
            for index, item in enumerate(self.server_commands):
                expired = datetime.strptime(item.get("expire"), "%Y-%m-%dT%H:%M:%S.%f")
                if datetime.now() > expired:
                    newexpire = datetime.now() + timedelta(seconds=30)
                    self.server_commands[index]["expire"] = newexpire.isoformat()
                    bytesToSend = bytes(dumps(item), encoding="ascii")
                    try:
                        self.server_udp.sendto(
                            bytesToSend,
                            (self.multicast_group, int(self.multicast_port)),
                        )
                    except OSError as err:
                        logging.warning("%s", err)

    def send_chat(self):
        """Sends UDP chat packet with text entered in chat_entry field."""
        message = self.chat_entry.text()
        packet = {"cmd": "CHAT"}
        packet["sender"] = self.preference.get("mycallsign")
        packet["message"] = message
        bytesToSend = bytes(dumps(packet), encoding="ascii")
        try:
            self.server_udp.sendto(
                bytesToSend, (self.multicast_group, int(self.multicast_port))
            )
        except OSError as err:
            logging.warning("%s", err)
        self.chat_entry.setText("")

    def display_chat(self, sender, body):
        """Displays the chat history."""
        if self.preference.get("mycallsign") in body.upper():
            self.chatlog.setTextColor(QtGui.QColor(245, 121, 0))
        self.chatlog.insertPlainText(f"\n{sender}: {body}")
        self.chatlog.setTextColor(QtGui.QColor(211, 215, 207))
        self.chatlog.ensureCursorVisible()

    def watch_udp(self):
        """Puts UDP datagrams in a FIFO queue"""
        while True:
            if self.connect_to_server:
                try:
                    datagram = self.server_udp.recv(1500)
                except socket.timeout:
                    time.sleep(1)
                    continue
                if datagram:
                    self.udp_fifo.put(datagram)
            else:
                time.sleep(1)

    def check_udp_queue(self):
        """checks the UDP datagram queue."""
        if self.server_seen:
            if datetime.now() > self.server_seen:
                self.group_call_indicator.setStyleSheet(
                    "border: 1px solid green;\nbackground-color: red;\ncolor: yellow;"
                )
        while not self.udp_fifo.empty():
            datagram = self.udp_fifo.get()
            try:
                json_data = loads(datagram.decode())
            except UnicodeDecodeError as err:
                the_error = f"Not Unicode: {err}\n{datagram}"
                logging.info(the_error)
                continue
            except JSONDecodeError as err:
                the_error = f"Not JSON: {err}\n{datagram}"
                logging.info(the_error)
                continue
            logging.info("%s", json_data)

            if json_data.get("cmd") == "PING":
                if json_data.get("station"):
                    band_mode = f"{json_data.get('band')} {json_data.get('mode')}"
                    if self.people.get(json_data.get("station")) != band_mode:
                        self.people[json_data.get("station")] = band_mode
                    self.show_people()
                if json_data.get("host"):
                    self.server_seen = datetime.now() + timedelta(seconds=30)
                    self.group_call_indicator.setStyleSheet("border: 1px solid green;")
                continue

            if json_data.get("cmd") == "RESPONSE":
                if json_data.get("recipient") == self.preference.get("mycallsign"):
                    if json_data.get("subject") == "HOSTINFO":
                        self.groupcall = str(json_data.get("groupcall"))
                        self.myclassEntry.setText(str(json_data.get("groupclass")))
                        self.mysectionEntry.setText(str(json_data.get("groupsection")))
                        self.group_call_indicator.setText(self.groupcall)
                        self.changemyclass()
                        self.changemysection()
                        self.mycallEntry.hide()
                        self.server_seen = datetime.now() + timedelta(seconds=30)
                        self.group_call_indicator.show()
                        self.group_call_indicator.setStyleSheet(
                            "border: 1px solid green;"
                        )
                        return
                    if json_data.get("subject") == "LOG":
                        self.infobox.insertPlainText("Server Generated Log.\n")
                    self.remove_confirmed_commands(json_data)
                    continue

            if json_data.get("cmd") == "CHAT":
                self.display_chat(json_data.get("sender"), json_data.get("message"))
                continue

            if json_data.get("cmd") == "GROUPQUERY":
                if self.groupcall:
                    self.send_status_udp()

    def query_group(self):
        """Sends request to server asking for group call/class/section."""
        update = {
            "cmd": "GROUPQUERY",
            "station": self.preference["mycallsign"],
        }
        bytesToSend = bytes(dumps(update), encoding="ascii")
        try:
            self.server_udp.sendto(
                bytesToSend, (self.multicast_group, int(self.multicast_port))
            )
        except OSError as err:
            logging.warning("%s", err)

    def send_status_udp(self):
        """Send status update to server informing of our band and mode"""
        if self.connect_to_server:
            if self.groupcall is None and self.preference["mycallsign"] != "":
                self.query_group()
                return

            update = {
                "cmd": "PING",
                "mode": self.mode,
                "band": self.band,
                "station": self.preference["mycallsign"],
            }
            bytesToSend = bytes(dumps(update), encoding="ascii")
            try:
                self.server_udp.sendto(
                    bytesToSend, (self.multicast_group, int(self.multicast_port))
                )
            except OSError as err:
                logging.warning("%s", err)

            self.check_for_stale_commands()

    def clearcontactlookup(self):
        """clearout the contact lookup"""
        self.contactlookup["call"] = ""
        self.contactlookup["grid"] = ""
        self.contactlookup["name"] = ""
        self.contactlookup["nickname"] = ""
        self.contactlookup["error"] = ""
        self.contactlookup["distance"] = ""
        self.contactlookup["bearing"] = ""

    def lookupmygrid(self):
        """lookup my own gridsquare"""
        if self.look_up:
            self.mygrid, _, _, _ = self.look_up.lookup(self.preference["mycallsign"])
            logging.info("my grid: %s", self.mygrid)

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
            if self.contactlookup.get("grid") and self.mygrid:
                self.contactlookup["distance"] = self.distance(
                    self.mygrid, self.contactlookup.get("grid")
                )
                self.contactlookup["bearing"] = self.bearing(
                    self.mygrid, self.contactlookup.get("grid")
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

    def run_button_pressed(self):
        """The run/S&P button was pressed."""
        if self.run_button.text() == "Run":
            self.run_state = False
            self.run_button.setText("SP")
        else:
            self.run_state = True
            self.run_button.setText("Run")
        self.read_cw_macros()

    def read_cw_macros(self) -> None:
        """
        Reads in the CW macros, firsts it checks to see if the file exists. If it does not,
        and this has been packaged with pyinstaller it will copy the default file from the
        temp directory this is running from... In theory.
        """

        if not Path("./cwmacros.txt").exists():
            logging.debug("read_cw_macros: copying default macro file.")
            ui_path = os.path.dirname(pkgutil.get_loader("wfdlogger").get_filename())
            ui_path += "/data/cwmacros.txt"
            copyfile(ui_path, "./cwmacros.txt")
        with open("./cwmacros.txt", "r", encoding="utf-8") as file_descriptor:
            for line in file_descriptor:
                try:
                    mode, fkey, buttonname, cwtext = line.split("|")
                    if mode.strip().upper() == "R" and self.run_state:
                        self.fkeys[fkey.strip()] = (buttonname.strip(), cwtext.strip())
                    if mode.strip().upper() != "R" and not self.run_state:
                        self.fkeys[fkey.strip()] = (buttonname.strip(), cwtext.strip())
                except ValueError as err:
                    logging.info("read_cw_macros: %s", err)
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
            self.mycallEntry.setText(self.preference.get("mycallsign"))
            if self.preference.get("mycallsign"):
                self.mycallEntry.setStyleSheet("border: 1px solid green;")
            self.myclassEntry.setText(self.preference.get("myclass"))
            if self.preference.get("myclass"):
                self.myclassEntry.setStyleSheet("border: 1px solid green;")
            self.mysectionEntry.setText(self.preference.get("mysection"))
            if self.preference.get("mysection"):
                self.mysectionEntry.setStyleSheet("border: 1px solid green;")
            if self.preference.get("power"):
                self.power_selector.setValue(int(self.preference.get("power")))

            self.cat_control = None
            if self.preference.get("useflrig"):
                self.cat_control = CAT(
                    "flrig",
                    self.preference.get("CAT_ip"),
                    self.preference.get("CAT_port"),
                )
            if self.preference.get("userigctld"):
                self.cat_control = CAT(
                    "rigctld",
                    self.preference.get("CAT_ip"),
                    self.preference.get("CAT_port"),
                )

            if self.preference.get("useqrz"):
                self.look_up = QRZlookup(
                    self.preference.get("lookupusername"),
                    self.preference.get("lookuppassword"),
                )
                if self.look_up.session:
                    self.QRZ_icon.setStyleSheet("color: rgb(128, 128, 0);")
                else:
                    self.QRZ_icon.setStyleSheet("color: rgb(136, 138, 133);")

            if self.preference.get("usehamdb"):
                self.look_up = HamDBlookup()
                self.QRZ_icon.setStyleSheet("color: rgb(128, 128, 0);")

            if self.preference.get("usehamqth"):
                self.look_up = HamQTH(
                    self.preference.get("lookupusername"),
                    self.preference.get("lookuppassword"),
                )
                if self.look_up.session:
                    self.QRZ_icon.setStyleSheet("color: rgb(128, 128, 0);")
                else:
                    self.QRZ_icon.setStyleSheet("color: rgb(136, 138, 133);")

            if self.look_up and self.preference.get("mycallsign"):
                _thethread = threading.Thread(
                    target=self.lookupmygrid,
                    daemon=True,
                )
                _thethread.start()

            self.cloudlogauth()

            if self.preference.get("cwtype") == 0:
                self.cw = None
            else:
                self.cw = CW(
                    self.preference.get("cwtype"),
                    self.preference.get("cwip"),
                    self.preference.get("cwport"),
                )
                self.cw.speed = 20

            self.altpowerButton.setStyleSheet(
                self.highlighted(self.preference.get("altpower"))
            )
            self.outdoorsButton.setStyleSheet(
                self.highlighted(self.preference.get("outdoors"))
            )
            self.notathomeButton.setStyleSheet(
                self.highlighted(self.preference.get("notathome"))
            )
            self.satelliteButton.setStyleSheet(
                self.highlighted(self.preference.get("satellite"))
            )
            self.antButton.setStyleSheet(
                self.highlighted(self.preference.get("antenna"))
            )

            self.connect_to_server = self.preference.get("useserver")
            self.multicast_group = self.preference.get("multicast_group")
            self.multicast_port = self.preference.get("multicast_port")
            self.interface_ip = self.preference.get("interface_ip")

            # group upd server
            logging.info("Use group server: %s", self.connect_to_server)
            if self.connect_to_server:
                logging.info(
                    "Connecting: %s:%s %s",
                    self.multicast_group,
                    self.multicast_port,
                    self.interface_ip,
                )
                self.mycallEntry.hide()
                self.group_call_indicator.show()
                self.chat_window.show()
                self.server_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.server_udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_udp.bind(("", int(self.multicast_port)))
                mreq = socket.inet_aton(self.multicast_group) + socket.inet_aton(
                    self.interface_ip
                )
                self.server_udp.setsockopt(
                    socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, bytes(mreq)
                )
                self.server_udp.settimeout(0.01)

                if self._udpwatch is None:
                    self._udpwatch = threading.Thread(
                        target=self.watch_udp,
                        daemon=True,
                    )
                    self._udpwatch.start()
            else:
                self.groupcall = None
                self.mycallEntry.show()
                self.group_call_indicator.hide()
                self.chat_window.hide()

            self.n1mm = N1MM(
                ip_address=self.preference.get("n1mm_ip"),
                radioport=self.preference.get("n1mm_radioport"),
                contactport=self.preference.get("n1mm_contactport"),
            )
            self.n1mm.set_station_name(self.preference.get("n1mm_station_name"))
            self.n1mm.set_operator(self.preference.get("n1mm_operator"))

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
        if self.preference.get("cloudlog"):
            try:
                self.cloudlog_icon.setPixmap(self.cloud_red)
                test = (
                    self.preference.get("cloudlogurl")
                    + "/auth/"
                    + self.preference.get("cloudlogapi")
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

    @staticmethod
    def fakefreq(band, mode):
        """
        If unable to obtain a frequency from the rig,
        This will return a sane value for a frequency mainly for the cabrillo and adif log.
        Takes a band and mode as input and returns freq in khz.
        """
        logging.info("fakefreq: band:%s mode:%s", band, mode)
        modes = {"CW": 0, "DI": 1, "PH": 2, "FT8": 1, "SSB": 2}
        fakefreqs = {
            "160": ["1830", "1805", "1840"],
            "80": ["3530", "3559", "3970"],
            "60": ["5332", "5373", "5405"],
            "40": ["7030", "7040", "7250"],
            "30": ["10130", "10130", "0000"],
            "20": ["14030", "14070", "14250"],
            "17": ["18080", "18100", "18150"],
            "15": ["21065", "21070", "21200"],
            "12": ["24911", "24920", "24970"],
            "10": ["28065", "28070", "28400"],
            "6": ["50030", "50300", "50125"],
            "2": ["144030", "144144", "144250"],
            "222": ["222100", "222070", "222100"],
            "432": ["432070", "432200", "432100"],
            "SAT": ["144144", "144144", "144144"],
        }
        freqtoreturn = fakefreqs[band][modes[mode]]
        logging.info("fakefreq: returning:%s", freqtoreturn)
        return freqtoreturn

    def getband(self, freq: str) -> str:
        """
        Convert a (string) frequency into a (string) band.
        Returns a (string) band.
        Returns a "0" if frequency is out of band.
        """
        logging.info("getband: %s %s", type(freq), freq)
        if freq.isnumeric():
            frequency = int(float(freq))
            if 2000000 > frequency > 1800000:
                return "160"
            if 4000000 > frequency > 3500000:
                return "80"
            if 5406000 > frequency > 5330000:
                return "60"
            if 7300000 > frequency > 7000000:
                return "40"
            if 10150000 > frequency > 10100000:
                return "30"
            if 14350000 > frequency > 14000000:
                return "20"
            if 18168000 > frequency > 18068000:
                return "17"
            if 21450000 > frequency > 21000000:
                return "15"
            if 24990000 > frequency > 24890000:
                return "12"
            if 29700000 > frequency > 28000000:
                return "10"
            if 54000000 > frequency > 50000000:
                return "6"
            if 148000000 > frequency > 144000000:
                return "2"
            if 225000000 > frequency > 222000000:
                return "222"
            if 450000000 > frequency > 420000000:
                return "432"
        else:
            return "0"

    @staticmethod
    def getmode(rigmode: str) -> str:
        """
        Change what rigctld returned for the mode to the cabrillo mode for logging.
        """
        if rigmode in ("CW", "CWR"):
            return "CW"
        if rigmode in ("USB", "LSB", "FM", "AM"):
            return "PH"
        return "DI"  # All else digital

    def setband(self, theband: str) -> None:
        """
        Takes a band in meters and programatically changes the onscreen dropdown to match.
        """
        self.band_selector.setCurrentIndex(self.band_selector.findText(theband))
        self.changeband()
        self.send_status_udp()

    def setmode(self, themode: str) -> None:
        """
        Takes a string for the mode (CW, PH, DI) and programatically changes the onscreen dropdown.
        """
        self.mode_selector.setCurrentIndex(self.mode_selector.findText(themode))
        self.changemode()
        self.send_status_udp()

    def poll_radio(self) -> None:
        """
        Poll rigctld to get band.
        """
        if self.cat_control is None:
            self.radio_icon.setPixmap(self.radio_grey)
            return

        if not self.cat_control.online:
            self.radio_icon.setPixmap(self.radio_red)
            if self.preference.get("useflrig"):
                self.cat_control = CAT(
                    "flrig",
                    self.preference.get("CAT_ip"),
                    self.preference.get("CAT_port"),
                )
            if self.preference.get("userigctld"):
                self.cat_control = CAT(
                    "rigctld",
                    self.preference.get("CAT_ip"),
                    self.preference.get("CAT_port"),
                )
        if self.cat_control.online:
            self.radio_icon.setPixmap(self.radio_green)
            newfreq = self.cat_control.get_vfo()
            newmode = self.cat_control.get_mode()
            # newpwr = self.cat_control.get_power()
            logging.info("F:%s M:%s", newfreq, newmode)
            # newpwr = int(float(rigctrlsocket.recv(1024).decode().strip()) * 100)
            if (
                newfreq != self.oldfreq or newmode != self.oldmode
            ):  # or newpwr != oldpwr
                self.oldfreq = newfreq
                self.oldmode = newmode
                # self.oldpwr = newpwr
                self.setband(str(self.getband(newfreq)))
                self.setmode(str(self.getmode(newmode)))
                # setpower(str(newpwr))
                # self.setfreq(str(newfreq))
            if self.preference.get("send_n1mm_packets"):
                self.n1mm.radio_info["StationName"] = self.preference.get(
                    "n1mm_station_name"
                )
                self.n1mm.radio_info["Freq"] = newfreq[:-1]
                self.n1mm.radio_info["TXFreq"] = newfreq[:-1]
                self.n1mm.radio_info["Mode"] = newmode
                self.n1mm.radio_info["OpCall"] = self.preference["mycallsign"]
                self.n1mm.radio_info["IsRunning"] = str(self.run_state)
                if self.cat_control.get_ptt() == "0":
                    self.n1mm.radio_info["IsTransmitting"] = "False"
                else:
                    self.n1mm.radio_info["IsTransmitting"] = "True"
                self.n1mm.send_radio()

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
        if self.groupcall and self.connect_to_server:
            macro = macro.replace("{MYCALL}", self.groupcall)
        else:
            macro = macro.replace("{MYCALL}", self.preference["mycallsign"])
        macro = macro.replace("{MYCLASS}", self.preference["myclass"])
        macro = macro.replace("{MYSECT}", self.preference["mysection"])
        macro = macro.replace("{HISCALL}", self.callsign_entry.text())
        return macro

    def keyPressEvent(self, event):
        """This overrides Qt key event."""
        modifier = event.modifiers()
        if event.key() == Qt.Key.Key_Escape:
            self.clearinputs()
            if self.cw is not None and modifier == Qt.ControlModifier:
                if self.cw.servertype == 1:
                    self.cw.sendcw("\x1b4")
        if event.key() == Qt.Key.Key_PageUp:
            if self.cw is not None:
                if self.cw.servertype == 1:
                    self.cw.speed += 1
                    self.cw.sendcw(f"\x1b2{self.cw.speed}")
        if event.key() == Qt.Key.Key_PageDown:
            if self.cw is not None:
                if self.cw.servertype == 1:
                    self.cw.speed -= 1
                    self.cw.sendcw(f"\x1b2{self.cw.speed}")
        if event.key() == Qt.Key.Key_Tab:
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
                    else:
                        _thethread = threading.Thread(
                            target=self.lazy_lookup,
                            args=(self.callsign_entry.text(),),
                            daemon=True,
                        )
                        _thethread.start()
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
            if self.preference.get("send_n1mm_packets"):
                self.n1mm.radio_info["FunctionKeyCaption"] = self.F1.text()
            self.cw.sendcw(self.process_macro(self.F1.toolTip()))

    def sendf2(self):
        """Sends CW macro"""
        if self.cw:
            if self.preference.get("send_n1mm_packets"):
                self.n1mm.radio_info["FunctionKeyCaption"] = self.F2.text()
            self.cw.sendcw(self.process_macro(self.F2.toolTip()))

    def sendf3(self):
        """Sends CW macro"""
        if self.cw:
            if self.preference.get("send_n1mm_packets"):
                self.n1mm.radio_info["FunctionKeyCaption"] = self.F3.text()
            self.cw.sendcw(self.process_macro(self.F3.toolTip()))

    def sendf4(self):
        """Sends CW macro"""
        if self.cw:
            if self.preference.get("send_n1mm_packets"):
                self.n1mm.radio_info["FunctionKeyCaption"] = self.F4.text()
            self.cw.sendcw(self.process_macro(self.F4.toolTip()))

    def sendf5(self):
        """Sends CW macro"""
        if self.cw:
            if self.preference.get("send_n1mm_packets"):
                self.n1mm.radio_info["FunctionKeyCaption"] = self.F5.text()
            self.cw.sendcw(self.process_macro(self.F5.toolTip()))

    def sendf6(self):
        """Sends CW macro"""
        if self.cw:
            if self.preference.get("send_n1mm_packets"):
                self.n1mm.radio_info["FunctionKeyCaption"] = self.F6.text()
            self.cw.sendcw(self.process_macro(self.F6.toolTip()))

    def sendf7(self):
        """Sends CW macro"""
        if self.cw:
            if self.preference.get("send_n1mm_packets"):
                self.n1mm.radio_info["FunctionKeyCaption"] = self.F7.text()
            self.cw.sendcw(self.process_macro(self.F7.toolTip()))

    def sendf8(self):
        """Sends CW macro"""
        if self.cw:
            if self.preference.get("send_n1mm_packets"):
                self.n1mm.radio_info["FunctionKeyCaption"] = self.F8.text()
            self.cw.sendcw(self.process_macro(self.F8.toolTip()))

    def sendf9(self):
        """Sends CW macro"""
        if self.cw:
            if self.preference.get("send_n1mm_packets"):
                self.n1mm.radio_info["FunctionKeyCaption"] = self.F9.text()
            self.cw.sendcw(self.process_macro(self.F9.toolTip()))

    def sendf10(self):
        """Sends CW macro"""
        if self.cw:
            if self.preference.get("send_n1mm_packets"):
                self.n1mm.radio_info["FunctionKeyCaption"] = self.F10.text()
            self.cw.sendcw(self.process_macro(self.F10.toolTip()))

    def sendf11(self):
        """Sends CW macro"""
        if self.cw:
            if self.preference.get("send_n1mm_packets"):
                self.n1mm.radio_info["FunctionKeyCaption"] = self.F11.text()
            self.cw.sendcw(self.process_macro(self.F11.toolTip()))

    def sendf12(self):
        """Sends CW macro"""
        if self.cw:
            if self.preference.get("send_n1mm_packets"):
                self.n1mm.radio_info["FunctionKeyCaption"] = self.F12.text()
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
        self.oldrfpower = self.preference.get("power")
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
            _thethread = threading.Thread(
                target=self.lookupmygrid,
                daemon=True,
            )
            _thethread.start()
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
                try:
                    qtoedit = int(text[2:])
                except ValueError:
                    return
                log = self.db.contact_by_id(qtoedit)
                if log:
                    dialog = EditQsoDialog(self)
                    dialog.setup(log, self.db)
                    dialog.change.lineChanged.connect(self.qsoedited)
                    dialog.open()
                return
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
                _thethread = threading.Thread(
                    target=self.lazy_lookup,
                    args=(self.callsign_entry.text(),),
                    daemon=True,
                )
                _thethread.start()
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
        self.show_dirty_records()
        if (
            len(self.callsign_entry.text()) == 0
            or len(self.class_entry.text()) == 0
            or len(self.section_entry.text()) == 0
        ):
            logging.info("Incomplete fields")
            return
        if not self.cat_control or self.oldfreq == 0:
            self.oldfreq = int(self.fakefreq(self.band, self.mode) + "000")
        unique_id = uuid.uuid4().hex
        contact = (
            self.callsign_entry.text(),
            self.class_entry.text(),
            self.section_entry.text(),
            self.oldfreq,
            self.band,
            self.mode,
            int(self.power_selector.value()),
            self.contactlookup.get("grid"),
            self.contactlookup.get("name"),
            self.run_state,
            unique_id,
        )
        self.db.log_contact(contact)
        stale = datetime.now() + timedelta(seconds=30)
        if self.connect_to_server:
            contact = {
                "cmd": "POST",
                "hiscall": self.callsign_entry.text(),
                "class": self.class_entry.text(),
                "section": self.section_entry.text(),
                "mode": self.mode,
                "band": self.band,
                "frequency": self.oldfreq,
                "date_and_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "power": int(self.power_selector.value()),
                "grid": self.contactlookup["grid"],
                "opname": self.contactlookup["name"],
                "station": self.preference["mycallsign"],
                "unique_id": unique_id,
                "expire": stale.isoformat(),
            }
            self.server_commands.append(contact)
            bytesToSend = bytes(dumps(contact), encoding="ascii")
            try:
                self.server_udp.sendto(
                    bytesToSend, (self.multicast_group, int(self.multicast_port))
                )
            except OSError as err:
                logging.warning("%s", err)
        if self.preference.get("send_n1mm_packets"):
            self.n1mm.contact_info["rxfreq"] = str(self.oldfreq)[:-1]
            self.n1mm.contact_info["txfreq"] = str(self.oldfreq)[:-1]
            self.n1mm.contact_info["mode"] = self.oldmode
            if self.oldmode in ("CW", "DI"):
                self.n1mm.contact_info["points"] = "2"
            else:
                self.n1mm.contact_info["points"] = "1"
            self.n1mm.contact_info["band"] = self.band
            self.n1mm.contact_info["mycall"] = self.preference["mycallsign"]
            self.n1mm.contact_info["IsRunQSO"] = str(self.run_state)
            self.n1mm.contact_info["timestamp"] = datetime.utcnow().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            self.n1mm.contact_info["call"] = self.callsign_entry.text()
            self.n1mm.contact_info["gridsquare"] = self.contactlookup["grid"]
            self.n1mm.contact_info["exchange1"] = self.class_entry.text()
            self.n1mm.contact_info["section"] = self.section_entry.text()
            self.n1mm.contact_info["name"] = self.contactlookup["name"]
            self.n1mm.contact_info["power"] = self.power_selector.value()
            self.n1mm.contact_info["ID"] = unique_id
            self.n1mm.send_contact_info()

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
        results = self.db.stats()
        cwcontacts = results.get("cwcontacts")
        phonecontacts = results.get("phonecontacts")
        digitalcontacts = results.get("digitalcontacts")
        bandmodemult = results.get("bandmodemult")
        last15 = results.get("last15")
        lasthour = results.get("lasthour")
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
        results = self.db.stats()
        cw = results.get("cwcontacts")
        ph = results.get("phonecontacts")
        di = results.get("digitalcontacts")
        bandmodemult = results.get("bandmodemult")
        # highpower = results.get("highpower")
        qrp = results.get("qrp")
        self.score = (int(cw) * 2) + int(ph) + (int(di) * 2)
        self.basescore = self.score
        if qrp:
            self.score = self.score * 2
        # elif not highpower:
        #     self.score = self.score * 1
        self.score = self.score * bandmodemult
        self.score = (
            self.score
            + (500 * self.preference.get("altpower"))
            + (500 * self.preference.get("outdoors"))
            + (500 * self.preference.get("notathome"))
            + (500 * self.preference.get("satellite"))
            + (500 * self.preference.get("antenna"))
        )
        return self.score

    def logwindow(self):
        """Populated the log window with contacts stored in the database."""
        self.listWidget.clear()
        log = self.db.fetch_all_contacts_desc()
        for x in log:
            logid = x.get("id")
            hiscall = x.get("callsign")
            hisclass = x.get("class")
            hissection = x.get("section")
            the_date_and_time = x.get("date_time")
            band = x.get("band")
            mode = x.get("mode")
            power = x.get("power")

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
        contactnumber = item.text().split()[0]
        result = self.db.contact_by_id(contactnumber)
        dialog = EditQsoDialog(self)
        dialog.setup(result, self.db)
        dialog.change.lineChanged.connect(self.qsoedited)
        dialog.open()

    def read_sections(self):
        """
        Reads in the ARRL sections into some internal dictionaries.
        """

        try:
            ui_path = os.path.dirname(pkgutil.get_loader("wfdlogger").get_filename())
            ui_path += "/data/secname.json"
            with open(ui_path, "rt", encoding="utf-8") as file_descriptor:
                self.secName = loads(file_descriptor.read())
            ui_path = os.path.dirname(pkgutil.get_loader("wfdlogger").get_filename())
            ui_path += "/data/secstate.json"
            with open(ui_path, "rt", encoding="utf-8") as file_descriptor:
                self.secState = loads(file_descriptor.read())
            ui_path = os.path.dirname(pkgutil.get_loader("wfdlogger").get_filename())
            ui_path += "/data/secpartial.json"
            with open(ui_path, "rt", encoding="utf-8") as file_descriptor:
                self.secPartial = loads(file_descriptor.read())
        except IOError as exception:
            logging.critical("read error: %s", exception)

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
            ui_path = os.path.dirname(pkgutil.get_loader("wfdlogger").get_filename())
            ui_path += "/data/MASTER.SCP"
            with open(ui_path, "r", encoding="utf-8") as file_descriptor:
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
        log = self.db.dup_check(acall)
        for contact in log:
            hiscall = contact.get("callsign")
            hisclass = contact.get("class")
            hissection = contact.get("section")
            hisband = contact.get("band")
            hismode = contact.get("mode")
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
        result = self.db.sections()
        self.wrkdsections = []
        for section in result:
            self.wrkdsections.append(section.get("section"))

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
        self.Section_MX.setStyleSheet(self.worked_section("MX"))
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
        self.Section_NB.setStyleSheet(self.worked_section("NB"))
        self.Section_BC.setStyleSheet(self.worked_section("BC"))
        self.Section_ONE.setStyleSheet(self.worked_section("ONE"))
        self.Section_GH.setStyleSheet(self.worked_section("GH"))
        self.Section_ONN.setStyleSheet(self.worked_section("ONN"))
        self.Section_NS.setStyleSheet(self.worked_section("NS"))
        self.Section_ONS.setStyleSheet(self.worked_section("ONS"))
        self.Section_MB.setStyleSheet(self.worked_section("MB"))
        self.Section_QC.setStyleSheet(self.worked_section("QC"))
        self.Section_NL.setStyleSheet(self.worked_section("NL"))
        self.Section_SK.setStyleSheet(self.worked_section("SK"))
        self.Section_PE.setStyleSheet(self.worked_section("PE"))
        self.Section_TER.setStyleSheet(self.worked_section("TER"))

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
        self.preference["altpower"] = not self.preference.get("altpower")
        self.altpowerButton.setStyleSheet(
            self.highlighted(self.preference.get("altpower"))
        )
        self.writepreferences()
        self.stats()

    def claim_outdoors(self, _) -> None:
        """Is called when the Outdoors button is pressed."""
        self.preference["outdoors"] = not self.preference.get("outdoors")
        self.outdoorsButton.setStyleSheet(
            self.highlighted(self.preference.get("outdoors"))
        )
        self.writepreferences()
        self.stats()

    def claim_not_at_home(self, _) -> None:
        """Is called when the Not At Home button is pressed."""
        self.preference["notathome"] = not self.preference.get("notathome")
        self.notathomeButton.setStyleSheet(
            self.highlighted(self.preference.get("notathome"))
        )
        self.writepreferences()
        self.stats()

    def claim_satellite(self, _) -> None:
        """Is called when the satellite button is pressed."""
        self.preference["satellite"] = not self.preference.get("satellite")
        self.satelliteButton.setStyleSheet(
            self.highlighted(self.preference.get("satellite"))
        )
        self.writepreferences()
        self.stats()

    def claim_ant(self, _) -> None:
        """Is called when the ant button is pressed."""
        self.preference["antenna"] = not self.preference.get("antenna")
        self.antButton.setStyleSheet(self.highlighted(self.preference.get("antenna")))
        self.writepreferences()
        self.stats()

    def get_band_mode_tally(self, band, mode):
        """
        Returns the amount of contacts and the maximum power
        used for a particular band/mode combination.
        """
        return self.db.get_band_mode_tally(band, mode)

    def getbands(self) -> list:
        """
        Returns a list of bands worked, and an empty list if none worked.
        """
        bandlist = []
        result = self.db.get_bands()
        if result:
            for returned_band in result:
                bandlist.append(returned_band.get("band"))
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
                            f"Band:\t{band}\t{cwt.get('tally')}\t{cwt.get('mpow')}\t"
                            f"{dit.get('tally')}\t{dit.get('mpow')}\t"
                            f"{pht.get('tally')}\t{pht.get('mpow')}",
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
        state = self.secState.get(section)
        if state not in ("--", None):
            return state
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
                grids = self.db.get_unique_grids()
                if grids:
                    lastcolor = ""
                    with open(filename, "w", encoding="ascii") as file_descriptor:
                        islast = len(grids) - 1
                        for count, grid in enumerate(grids):
                            if count == islast:
                                lastcolor = "color=Orange"
                            if len(grid.get("grid")) > 1:
                                lat, lon = self.gridtolatlon(grid.get("grid"))
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

    def adif(self):
        """
        Creates an ADIF file of the contacts made.
        """
        logname = "WFD.adi"
        self.infobox.setTextColor(QtGui.QColor(211, 215, 207))
        self.infobox.insertPlainText(f"Saving ADIF to: {logname}\n")
        app.processEvents()
        log = self.db.fetch_all_contacts_asc()
        grid = False
        opname = False
        try:
            with open(logname, "w", encoding="utf-8") as file_descriptor:
                print("<ADIF_VER:5>2.2.0", end="\r\n", file=file_descriptor)
                print("<EOH>", end="\r\n", file=file_descriptor)
                for contact in log:

                    hiscall = contact.get("callsign")
                    hisclass = contact.get("class")
                    hissection = contact.get("section")
                    the_date_and_time = contact.get("date_time")
                    band = contact.get("band")
                    mode = contact.get("mode")
                    grid = contact.get("grid")
                    opname = contact.get("opname")
                    frequency = contact.get("frequency")
                    if frequency == 0:
                        frequency = f"{int(self.fakefreq(band, mode)) / 1000:.3f}"
                    else:
                        frequency = f"{int(frequency) / 1000000:.3f}"
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
                            f"<FREQ:{len(frequency)}>{frequency}",
                            end="\r\n",
                            file=file_descriptor,
                        )
                    except TypeError:
                        pass  # This is bad form... I can't remember why this is in a try block
                    print(
                        f"<RST_SENT:{len(rst)}>{rst}", end="\r\n", file=file_descriptor
                    )
                    print(
                        f"<RST_RCVD:{len(rst)}>{rst}", end="\r\n", file=file_descriptor
                    )
                    myexch = f"{self.preference.get('myclass')} {self.preference.get('mysection')}"
                    print(
                        f"<STX_STRING:{len(myexch)}>{myexch}",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    hisexch = f"{hisclass} {hissection}"
                    print(
                        f"<SRX_STRING:{len(hisexch)}>{hisexch}",
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
        if (not self.preference.get("cloudlog")) or (not self.cloudlogauthenticated):
            return
        contact = self.db.fetch_last_contact()

        hiscall = contact.get("callsign")
        hisclass = contact.get("class")
        hissection = contact.get("section")
        the_date_and_time = contact.get("date_time")
        band = contact.get("band")
        mode = contact.get("mode")
        grid = contact.get("grid")
        opname = contact.get("opname")
        frequency = contact.get("frequency")
        if frequency == 0:
            frequency = f"{int(self.fakefreq(band, mode)) / 1000:.3f}"
        else:
            frequency = f"{int(frequency) / 1000000:.3f}"

        logging.info("%s", contact)
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
        stx = (
            f"{self.preference.get('myclass') + ' ' + self.preference.get('mysection')}"
        )
        adifq = (
            f"<QSO_DATE:{len(''.join(loggeddate.split('-')))}:d>"
            f"{''.join(loggeddate.split('-'))}"
            f"<TIME_ON:{len(loggedtime)}>{loggedtime}"
            f"<CALL:{len(hiscall)}>{hiscall}"
            f"<MODE:{len(mode)}>{mode}"
            f"<BAND:{len(band + 'M')}>{band + 'M'}"
            f"<FREQ:{len(frequency)}>{frequency}"
            f"<RST_SENT:{len(rst)}>{rst}"
            f"<RST_RCVD:{len(rst)}>{rst}"
            f"<STX_STRING:{len(stx)}>"
            f"{stx}"
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

        payload_dict = {
            "key": self.preference.get("cloudlogapi"),
            "type": "adif",
            "string": adifq,
        }
        jason_data = dumps(payload_dict)
        _ = requests.post(
            self.preference.get("cloudlogurl") + "/qso/", jason_data, timeout=5
        )

    def cabrillo(self):
        """
        Generates a cabrillo log file.
        """
        filename = f"{self.preference.get('mycallsign').upper()}.log"
        self.infobox.setTextColor(QtGui.QColor(211, 215, 207))
        self.infobox.insertPlainText(f"Saving cabrillo to: {filename}")
        app.processEvents()
        bonuses = 0
        log = self.db.fetch_all_contacts_asc()
        catpower = ""
        result = self.db.stats()
        highpower = result.get("highpower")
        qrp = result.get("qrp")
        self.powermult = 1
        if qrp:
            catpower = "QRP"
            self.powermult = 2
        elif highpower:
            catpower = "HIGH"
            self.powermult = 0
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
                print("CONTEST: WINTER-FIELD-DAY", end="\r\n", file=file_descriptor)
                print(
                    f"CALLSIGN: {self.preference.get('mycallsign')}",
                    end="\r\n",
                    file=file_descriptor,
                )
                print("LOCATION:", end="\r\n", file=file_descriptor)
                print(
                    f"ARRL-SECTION: {self.preference.get('mysection')}",
                    end="\r\n",
                    file=file_descriptor,
                )
                print(
                    f"CATEGORY: {self.preference.get('myclass')}",
                    end="\r\n",
                    file=file_descriptor,
                )
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
                if self.preference.get("altpower"):
                    print(
                        "SOAPBOX: 500 points for not using commercial power",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    bonuses += 500
                if self.preference.get("outdoors"):
                    print(
                        "SOAPBOX: 500 points for setting up outdoors",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    bonuses += 500
                if self.preference.get("notathome"):
                    print(
                        "SOAPBOX: 500 points for setting up away from home",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    bonuses += 500
                if self.preference.get("satellite"):
                    print(
                        "SOAPBOX: 500 points for working satellite",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    bonuses += 500
                if self.preference.get("antenna"):
                    print(
                        "SOAPBOX: 500 points for setting up WFD antenna",
                        end="\r\n",
                        file=file_descriptor,
                    )
                    bonuses += 500

                print(
                    f"SOAPBOX: BONUS Total {bonuses}", end="\r\n", file=file_descriptor
                )
                print(
                    f"CLAIMED-SCORE: {self.calcscore()}",
                    end="\r\n",
                    file=file_descriptor,
                )
                print(
                    f"OPERATORS: {self.preference.get('mycallsign')}",
                    end="\r\n",
                    file=file_descriptor,
                )
                print("NAME: ", end="\r\n", file=file_descriptor)
                print("ADDRESS: ", end="\r\n", file=file_descriptor)
                print("ADDRESS-CITY: ", end="\r\n", file=file_descriptor)
                print("ADDRESS-STATE: ", end="\r\n", file=file_descriptor)
                print("ADDRESS-POSTALCODE: ", end="\r\n", file=file_descriptor)
                print("ADDRESS-COUNTRY: ", end="\r\n", file=file_descriptor)
                print("EMAIL: ", end="\r\n", file=file_descriptor)
                for contact in log:

                    hiscall = contact.get("callsign")
                    hisclass = contact.get("class")
                    hissection = contact.get("section")
                    the_date_and_time = contact.get("date_time")
                    band = contact.get("band")
                    mode = contact.get("mode")
                    frequency = contact.get("frequency")
                    if frequency == 0:
                        frequency = self.fakefreq(band, mode)
                    else:
                        frequency = f"{int(frequency / 1000)}"

                    loggeddate = the_date_and_time[:10]
                    loggedtime = the_date_and_time[11:13] + the_date_and_time[14:16]
                    print(
                        f"QSO: {frequency} {mode} {loggeddate} {loggedtime}"
                        f" {self.preference.get('mycallsign')}"
                        f" {self.preference.get('myclass')}"
                        f" {self.preference.get('mysection')} "
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
        self.show_dirty_records()
        self.resolve_dirty_records()
        self.cabrillo()
        self.generate_band_mode_tally()
        self.adif()
        if self.connect_to_server:
            update = {
                "cmd": "LOG",
                "station": self.preference["mycallsign"],
            }
            bytesToSend = bytes(dumps(update), encoding="ascii")
            try:
                self.server_udp.sendto(
                    bytesToSend, (self.multicast_group, int(self.multicast_port))
                )
            except OSError as err:
                logging.warning("%s", err)


class EditQsoDialog(QtWidgets.QDialog):
    """Edits/deletes a contacts in the database"""

    theitem = ""
    database = None
    contact = None

    def __init__(self, parent=None):
        super().__init__(parent)
        ui_path = os.path.dirname(pkgutil.get_loader("wfdlogger").get_filename())
        ui_path += "/data/dialog.ui"
        uic.loadUi(ui_path, self)
        self.deleteButton.clicked.connect(self.delete_contact)
        self.buttonBox.accepted.connect(self.save_changes)
        self.change = QSOEdit()

    def setup(self, contact, thedatabase):
        """Loads in the contact information and db to access."""
        self.database = thedatabase
        self.contact = contact
        self.theitem = contact.get("id")
        self.editCallsign.setText(contact.get("callsign"))
        self.editClass.setText(contact.get("class"))
        self.editSection.setText(contact.get("section"))
        self.editFreq.setText(str(contact.get("frequency")))
        self.editBand.setCurrentIndex(self.editBand.findText(contact.get("band")))
        self.editMode.setCurrentIndex(self.editMode.findText(contact.get("mode")))
        self.editPower.setValue(int(contact.get("power")))
        date_time = contact.get("date_time")
        now = QtCore.QDateTime.fromString(date_time, "yyyy-MM-dd hh:mm:ss")
        self.editDateTime.setDateTime(now)

    def save_changes(self):
        """Update edited contact in the db."""
        qso = (
            self.editCallsign.text().upper(),
            self.editClass.text().upper(),
            self.editSection.text().upper(),
            self.editDateTime.text(),
            self.editBand.currentText(),
            self.editMode.currentText(),
            self.editPower.value(),
            self.editFreq.text(),
            self.theitem,
        )
        self.database.change_contact(qso)
        if window.connect_to_server:
            stale = datetime.now() + timedelta(seconds=30)
            command = {"cmd": "UPDATE"}
            command["hiscall"] = self.editCallsign.text().upper()
            command["class"] = self.editClass.text().upper()
            command["section"] = self.editSection.text().upper()
            command["date_and_time"] = self.editDateTime.text()
            command["frequency"] = self.editFreq.text()
            command["band"] = self.editBand.currentText()
            command["mode"] = self.editMode.currentText().upper()
            command["power"] = self.editPower.value()
            command["station"] = window.preference["mycallsign"].upper()
            command["unique_id"] = self.contact.get("unique_id")
            command["expire"] = stale.isoformat()
            command["opname"] = self.contact.get("opname")
            command["grid"] = self.contact.get("grid")
            window.server_commands.append(command)
            bytesToSend = bytes(dumps(command), encoding="ascii")
            try:
                window.server_udp.sendto(
                    bytesToSend, (window.multicast_group, int(window.multicast_port))
                )
            except OSError as err:
                logging.warning("%s", err)
        if window.preference.get("send_n1mm_packets"):

            window.n1mm.contact_info["rxfreq"] = self.editFreq.text()[:-1]
            window.n1mm.contact_info["txfreq"] = self.editFreq.text()[:-1]
            window.n1mm.contact_info["mode"] = self.editMode.currentText().upper()
            window.n1mm.contact_info["band"] = self.editBand.currentText()
            window.n1mm.contact_info["mycall"] = window.preference["mycallsign"]
            window.n1mm.contact_info["IsRunQSO"] = self.contact.get("IsRunQSO")
            window.n1mm.contact_info["timestamp"] = self.contact.get("date_time")
            window.n1mm.contact_info["call"] = self.editCallsign.text().upper()
            window.n1mm.contact_info["gridsquare"] = self.contact.get("grid")
            window.n1mm.contact_info["exchange1"] = self.editClass.text().upper()
            window.n1mm.contact_info["section"] = self.editSection.text().upper()
            window.n1mm.contact_info["name"] = self.contact.get("opname")
            window.n1mm.contact_info["power"] = self.editPower.value()
            window.n1mm.contact_info["ID"] = self.contact.get("unique_id")
            if window.n1mm.contact_info["mode"] in ("CW", "DI"):
                window.n1mm.contact_info["points"] = "2"
            else:
                window.n1mm.contact_info["points"] = "1"
            window.n1mm.send_contactreplace()

        self.change.lineChanged.emit()

    def delete_contact(self):
        """Delete a contact from the db."""
        self.database.delete_contact(self.theitem)
        if window.connect_to_server:
            stale = datetime.now() + timedelta(seconds=30)
            command = {}
            command["cmd"] = "DELETE"
            command["unique_id"] = self.contact.get("unique_id")
            command["station"] = window.preference["mycallsign"].upper()
            command["expire"] = stale.isoformat()
            window.server_commands.append(command)
            bytesToSend = bytes(dumps(command), encoding="ascii")
            try:
                window.server_udp.sendto(
                    bytesToSend, (window.multicast_group, int(window.multicast_port))
                )
            except OSError as err:
                logging.warning("%s", err)
        if window.preference.get("send_n1mm_packets"):
            window.n1mm.contactdelete["timestamp"] = datetime.utcnow().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            window.n1mm.contactdelete["call"] = self.contact.get("callsign")
            window.n1mm.contactdelete["ID"] = self.contact.get("unique_id")
            window.n1mm.send_contact_delete()
        self.change.lineChanged.emit()
        self.close()


class Startup(QtWidgets.QDialog):
    """
    Show splash screen, get Op call, class, section
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        ui_path = os.path.dirname(pkgutil.get_loader("wfdlogger").get_filename())
        ui_path += "/data/startup.ui"
        uic.loadUi(ui_path, self)
        self.continue_pushButton.clicked.connect(self.store)

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


# if Path("./debug").exists():
if True:
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
ui_path = os.path.dirname(pkgutil.get_loader("wfdlogger").get_filename())
ui_path += "/data"
families = load_fonts_from_dir(os.fspath(ui_path))
logging.info(families)
window = MainWindow()
window.setWindowTitle(f"K6GTE Winter Field Day Logger v{__version__}")
window.show()
window.read_cw_macros()
window.changeband()
window.changemode()
if (
    window.preference.get("mycallsign") == ""
    or window.preference.get("myclass") == ""
    or window.preference.get("mysection") == ""
):
    startupdialog = Startup()
    startupdialog.accepted.connect(startup_dialog_finished)
    startupdialog.open()
    startupdialog.set_callsign(window.preference.get("mycallsign"))
    startupdialog.set_class(window.preference.get("myclass"))
    startupdialog.set_section(window.preference.get("mysection"))
window.read_cw_macros()
# window.cloudlogauth()
window.stats()
window.read_sections()
window.read_scp()
window.logwindow()
window.sections()
window.callsign_entry.setFocus()

timer = QtCore.QTimer()
timer.timeout.connect(window.update_time)
# timer.start(1000)

timer2 = QtCore.QTimer()
timer2.timeout.connect(window.check_udp_queue)
# timer2.start(1000)

timer3 = QtCore.QTimer()
timer3.timeout.connect(window.send_status_udp)
# timer3.start(15000)

# sys.exit(app.exec())


def run():
    timer.start(1000)
    timer2.start(1000)
    timer3.start(15000)
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
