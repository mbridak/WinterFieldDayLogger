#!/usr/bin/env python3
"""Testing n1mm stuff"""

import socket
import uuid
from datetime import datetime

# pip3 install -U dicttoxml
from dicttoxml import dicttoxml


class N1MM:
    """ "Send N1MM style packets"""

    radio_info = {
        "app": "N1MM",
        "StationName": "",
        "uNICORNbLOOD": "1",
        "RadioNr": "1",
        "Freq": "",
        "TXFreq": "",
        "Mode": "",
        "OpCall": "",
        "IsRunning": "False",
        "FocusEntry": "0",
        "EntryWindowHwnd": "0",
        "Antenna": "",
        "Rotors": "",
        "FocusRadioNr": "1",
        "IsStereo": "False",
        "IsSplit": "False",
        "ActiveRadioNr": "1",
        "IsTransmitting": "False",
        "FunctionKeyCaption": "",
        "RadioName": "Little Todd",
        "AuxAntSelected": "-1",
        "AuxAntSelectedName": "",
    }

    contact_info = {
        "contestname": "",
        "contestnr": "1",
        "timestamp": "",
        "mycall": "",
        "operator": "",
        "band:": "",
        "rxfreq": "",
        "txfreq": "",
        "mode": "",
        "call": "",
        "countryprefix": "K",
        "wpxprefix": "",
        "stationprefix": "",
        "continent": "NA",
        "snt": "59",
        "sntnr": "",
        "rcv": "59",
        "rcvnr": "",
        "gridsquare": "",
        "exchange1": "",
        "section": "",
        "comment": "",
        "qth": "",
        "name": "",
        "power": "",
        "misctext": "",
        "zone": "5",
        "prec": "",
        "ck": "0",
        "ismultiplier1": "0",
        "ismultiplier2": "0",
        "ismultiplier3": "0",
        "points": "1",
        "radionr": "1",
        "RoverLocation": "",
        "RadioInterfaced": "0",
        "NetworkedCompNr": "0",
        "IsOriginal": "True",
        "NetBiosName": "",
        "IsRunQSO": "0",
        "Run1Run2": "",
        "ContactType": "",
        "StationName": "",
        "ID": "",
        "IsClaimedQso": "True",
    }

    contactdelete = {
        "timestamp": "",
        "call": "",
        "contestnr": "1",
        "StationName": "",
    }

    def __init__(
        self,
        ip_address="127.0.0.1",
        radioport=12060,
        contactport=12060,
        lookupport=12060,
        scoreport=12060,
    ):
        """
        Initialize the N1MM interface.

        Optional arguments are:

        - ip_address, The IP of the device you're sending too.
        - radioport, Where radio status messages go.
        - contactport, Where Add, Update, Delete messages go.
        - lookupport, Where callsign queries go.
        - scoreport, Where to send scores to.
        """
        self.ip_address = ip_address
        self.radio_port = radioport
        self.contact_port = contactport
        self.lookup_port = lookupport
        self.score_port = scoreport
        self.radio_socket = None
        self.radio_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

    def send_radio(self):
        """Send XML data"""
        self._send(self.radio_port, self.radio_info, "RadioInfo")

    def send_contact_info(self):
        """Send XML data"""
        self._send(self.contact_port, self.contact_info, "contactinfo")

    def send_contactreplace(self):
        """Send replace"""
        self._send(self.contact_port, self.contactdelete, "contactreplace")

    def send_contact_delete(self):
        """Send Delete"""
        self._send(self.contact_port, self.contact_info, "contactdelete")

    def send_lookup(self):
        """Send lookup request"""
        self._send(self.lookup_port, self.contact_info, "lookupinfo")

    def _send(self, port, payload, package_name):
        """Send XML data"""
        bytes_to_send = dicttoxml(payload, custom_root=package_name, attr_type=False)
        self.radio_socket.sendto(
            bytes_to_send,
            (self.ip_address, int(port)),
        )


# n1mm = N1MM(contactport=12061, lookupport=12061, scoreport=12062)

# n1mm.radio_info["StationName"] = "stanley"
# n1mm.radio_info["Freq"] = "1425700"
# n1mm.radio_info["TXFreq"] = "1425700"
# n1mm.radio_info["Mode"] = "USB"
# n1mm.radio_info["OpCall"] = "K6GTE"
# n1mm.radio_info["IsRunning"] = "True"
# n1mm.radio_info["IsTransmitting"] = "True"
# n1mm.radio_info["FunctionKeyCaption"] = "CQ FD"

# n1mm.send_radio()

# n1mm.contact_info["contestname"] = "ARRL-FIELD-DAY"
# n1mm.contact_info["NetBiosName"] = socket.gethostname()
# n1mm.contact_info["StationName"] = "stanley"
# n1mm.contact_info["mycall"] = "K6GTE"
# n1mm.contact_info["operator"] = "Mike"
# n1mm.contact_info["call"] = "w5aw"
# n1mm.contact_info["ID"] = uuid.uuid4().hex
# n1mm.contact_info["band"] = "14"
# n1mm.contact_info["mode"] = "USB"
# n1mm.contact_info["rxfreq"] = "1425700"
# n1mm.contact_info["txfreq"] = "1425700"
# n1mm.contact_info["exchange1"] = "1D"
# n1mm.contact_info["section"] = "VA"
# n1mm.contact_info["points"] = "1"
# n1mm.contact_info["timestamp"] = str(datetime.now()).split(".")[0]
# n1mm.contact_info["IsRunQSO"] = "True"

# n1mm.send_lookup()

# n1mm.send_contact_info()
