"""
K6GTE, N1MM sending interface
Email: michael.bridak@gmail.com
GPL V3
"""

import logging
import socket

# pip3 install -U dicttoxml
from dicttoxml import dicttoxml

if __name__ == "__main__":
    print("I'm not the program you are looking for.")


class N1MM:
    """ "Send N1MM style packets"""

    radio_info = {
        "app": "K6GTE-WFD",
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
        "app": "K6GTE-WFD",
        "contestname": "Winter Field Day",
        "contestnr": "1",
        "timestamp": "",
        "mycall": "",
        "operator": "",
        "band": "",
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
        "app": "K6GTE-WFD",
        "timestamp": "",
        "call": "",
        "contestnr": "1",
        "StationName": "",
        "ID": "",
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
        self.contact_info["NetBiosName"] = socket.gethostname()

    def set_station_name(self, name):
        """Set the station name"""
        self.radio_info["StationName"] = name
        self.contact_info["StationName"] = name
        self.contactdelete["StationName"] = name

    def set_operator(self, name):
        """Set Operators Name"""
        self.contact_info["operator"] = name

    def send_radio(self):
        """Send XML data"""
        self._send(self.radio_port, self.radio_info, "RadioInfo")

    def send_contact_info(self):
        """Send XML data"""
        self._send(self.contact_port, self.contact_info, "contactinfo")

    def send_contactreplace(self):
        """Send replace"""
        self._send(self.contact_port, self.contact_info, "contactreplace")

    def send_contact_delete(self):
        """Send Delete"""
        self._send(self.contact_port, self.contactdelete, "contactdelete")

    def send_lookup(self):
        """Send lookup request"""
        self._send(self.lookup_port, self.contact_info, "lookupinfo")

    def _send(self, port, payload, package_name):
        """Send XML data"""
        logging_info = f"{package_name} - {payload}"
        logging.info("%s", logging_info)
        bytes_to_send = dicttoxml(payload, custom_root=package_name, attr_type=False)
        self.radio_socket.sendto(
            bytes_to_send,
            (self.ip_address, int(port)),
        )
