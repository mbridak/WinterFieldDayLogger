"""
callsign lookup classes for:
QRZ
HamDB
HamQTH
"""

import logging
from bs4 import BeautifulSoup as bs
import requests


class HamDBlookup:
    """
    Class manages HamDB lookups.
    """

    def __init__(self) -> None:
        self.url = "https://api.hamdb.org/"
        self.error = False

    def lookup(self, call: str) -> tuple:
        """
        Lookup a call on QRZ
        """
        logging.info("Hamdblookup-lookup: %s", call)
        grid = False
        name = False
        error_text = False
        nickname = False

        try:
            self.error = False
            query_result = requests.get(
                self.url + call + "/xml/wfd_logger", timeout=10.0
            )
        except requests.exceptions.Timeout as exception:
            self.error = True
            return grid, name, nickname, exception
        if query_result.status_code == 200:
            self.error = False
            root = bs(query_result.text, "xml")
            if root.messages.find("status"):
                error_text = root.messages.status.text
                logging.debug("HamDB: %s", error_text)
                if error_text != "OK":
                    self.error = False
            if root.find("callsign"):
                logging.debug("HamDB: found callsign field")
                if root.callsign.find("grid"):
                    grid = root.callsign.grid.text
                if root.callsign.find("fname"):
                    name = root.callsign.fname.text
                if root.callsign.find("name"):
                    if not name:
                        name = root.callsign.find("name").string
                    else:
                        name = f"{name} {root.find('name').string}"
                if root.callsign.find("nickname"):
                    nickname = root.callsign.nickname.text
        else:
            self.error = True
            error_text = str(query_result.status_code)
        logging.info("HamDB-lookup: %s %s %s %s", grid, name, nickname, error_text)
        return grid, name, nickname, error_text


class QRZlookup:
    """
    Class manages QRZ lookups. Pass in a username and password at instantiation.
    """

    def __init__(self, username: str, password: str) -> None:
        self.session = False
        self.expiration = False
        self.error = (
            False  # "password incorrect", "session timeout", and "callsign not found".
        )
        self.username = username
        self.password = password
        self.qrzurl = "https://xmldata.qrz.com/xml/134/"
        self.message = False
        self.lastresult = False
        self.getsession()

    def getsession(self) -> None:
        """
        Get QRZ session key.
        Stores key in class variable 'session'
        Error messages returned by QRZ will be in class variable 'error'
        Other messages returned will be in class variable 'message'
        """
        logging.info("QRZlookup-getsession:")
        self.error = False
        self.message = False
        self.session = False
        try:
            payload = {"username": self.username, "password": self.password}
            query_result = requests.get(self.qrzurl, params=payload, timeout=10.0)
            root = bs(query_result.text, "xml")
            if root.session.find("key"):
                self.session = root.session.key.text
            if root.session.find("subexp"):
                self.expiration = root.session.subexp.text
            if root.session.find("error"):
                self.error = root.session.error.text
            if root.session.find("message"):
                self.message = root.session.message.text
            logging.info(
                "QRZlookup-getsession: key:%s error:%s message:%s",
                self.session,
                self.error,
                self.message,
            )
        except requests.exceptions.RequestException as exception:
            logging.info("QRZlookup-getsession: %s", exception)
            self.session = False
            self.error = f"{exception}"

    def lookup(self, call: str) -> tuple:
        """
        Lookup a call on QRZ
        """
        logging.info("QRZlookup-lookup: %s", call)
        grid = False
        name = False
        error_text = False
        nickname = False
        if self.session:
            payload = {"s": self.session, "callsign": call}
            try:
                query_result = requests.get(self.qrzurl, params=payload, timeout=10.0)
            except requests.exceptions.Timeout as exception:
                self.error = True
                return grid, name, nickname, exception
            root = bs(query_result.text, "xml")
            if not root.session.key:  # key expired get a new one
                logging.info("QRZlookup-lookup: no key, getting new one.")
                self.getsession()
                if self.session:
                    payload = {"s": self.session, "callsign": call}
                    query_result = requests.get(
                        self.qrzurl, params=payload, timeout=3.0
                    )
            grid, name, nickname, error_text = self.parse_lookup(query_result)
        logging.info("QRZ-lookup: %s %s %s %s", grid, name, nickname, error_text)
        return grid, name, nickname, error_text

    def parse_lookup(self, query_result):
        """
        Returns gridsquare and name for a callsign looked up by qrz or hamdb.
        Or False for both if none found or error.
        """
        logging.info("QRZlookup-parse_lookup:")
        grid = False
        name = False
        error_text = False
        nickname = False
        if query_result.status_code == 200:
            root = bs(query_result.text, "xml")
            if root.session.find("error"):
                error_text = root.session.error.text
                self.error = error_text
            if root.find("callsign"):
                if root.callsign.find("grid"):
                    grid = root.callsign.grid.text
                if root.callsign.find("fname"):
                    name = root.callsign.fname.text
                if root.find("name"):
                    if not name:
                        name = root.find("name").string
                    else:
                        name = f"{name} {root.find('name').string}"
                if root.callsign.find("nickname"):
                    nickname = root.callsign.nickname.text
        logging.info(
            "QRZlookup-parse_lookup: %s %s %s %s", grid, name, nickname, error_text
        )
        return grid, name, nickname, error_text


class HamQTH:
    """HamQTH lookup"""

    def __init__(self, username: str, password: str) -> None:
        """initialize HamQTH lookup"""
        self.username = username
        self.password = password
        self.url = "https://www.hamqth.com/xml.php"
        self.session = False
        self.error = False
        self.getsession()

    def getsession(self) -> None:
        """get a session key"""
        logging.info("HamQTH-getsession:")
        self.error = False
        # self.message = False
        self.session = False
        payload = {"u": self.username, "p": self.password}
        try:
            query_result = requests.get(self.url, params=payload, timeout=10.0)
        except requests.exceptions.Timeout:
            self.error = True
            return
        logging.info("hamqth-getsession:%s", query_result.status_code)
        root = bs(query_result.text, "xml")
        if root.find("session"):
            if root.session.find("session_id"):
                self.session = root.session.session_id.text
            if root.session.find("error"):
                self.error = root.session.error.text
        logging.info("hamqth session: %s", self.session)

    def lookup(self, call: str) -> tuple:
        """
        Lookup a call on HamQTH
        """
        grid, name, nickname, error_text = False, False, False, False
        if self.session:
            payload = {"id": self.session, "callsign": call, "prg": "wfd_curses"}
            try:
                query_result = requests.get(self.url, params=payload, timeout=10.0)
            except requests.exceptions.Timeout as exception:
                self.error = True
                return grid, name, nickname, exception
            logging.info("lookup resultcode: %s", query_result.status_code)
            root = bs(query_result.text, "xml")
            if not root.find("search"):
                if root.find("session"):
                    if root.session.find("error"):
                        if root.session.error.text == "Callsign not found":
                            error_text = root.session.error.text
                            return grid, name, nickname, error_text
                        if (
                            root.session.error.text
                            == "Session does not exist or expired"
                        ):
                            self.getsession()
                            query_result = requests.get(
                                self.url, params=payload, timeout=10.0
                            )
            grid, name, nickname, error_text = self.parse_lookup(query_result)
        logging.info("HamDB-lookup: %s %s %s %s", grid, name, nickname, error_text)
        return grid, name, nickname, error_text

    def parse_lookup(self, query_result) -> tuple:
        """
        Returns gridsquare and name for a callsign looked up by qrz or hamdb.
        Or False for both if none found or error.
        """
        grid, name, nickname, error_text = False, False, False, False
        root = bs(query_result.text, "xml")
        if root.find("session"):
            if root.session.find("error"):
                error_text = root.session.error.text
        if root.find("search"):
            if root.search.find("grid"):
                grid = root.search.grid.text
            if root.search.find("nick"):
                nickname = root.search.nick.text
            if root.search.find("adr_name"):
                name = root.search.adr_name.text
        return grid, name, nickname, error_text
