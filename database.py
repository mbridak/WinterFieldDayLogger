"""Database class to store contacts"""
import logging
import sqlite3


class DataBase:
    """Database class for our database."""

    def __init__(self, database):
        """initializes DataBase instance"""
        self.database = database
        self.create_db()

    def create_db(self) -> None:
        """create a database and table if it does not exist"""
        with sqlite3.connect(self.database) as conn:
            cursor = conn.cursor()
            sql_table = (
                "CREATE TABLE IF NOT EXISTS contacts "
                "(id INTEGER PRIMARY KEY, "
                "callsign text NOT NULL, "
                "class text NOT NULL, "
                "section text NOT NULL, "
                "date_time text NOT NULL, "
                "band text NOT NULL, "
                "mode text NOT NULL, "
                "power INTEGER NOT NULL, "
                "grid text NOT NULL, "
                "opname text NOT NULL);"
            )
            cursor.execute(sql_table)
            conn.commit()

    def log_contact(self, logme: tuple) -> None:
        """
        Inserts a contact into the db.
        pass in (hiscall, hisclass, hissection, band, mode, int(power))
        """
        try:
            with sqlite3.connect(self.database) as conn:
                sql = (
                    "INSERT INTO contacts"
                    "(callsign, class, section, date_time, "
                    "band, mode, power, grid, opname) "
                    "VALUES(?,?,?,datetime('now'),?,?,?,?,?)"
                )
                cur = conn.cursor()
                cur.execute(sql, logme)
                conn.commit()
        except sqlite3.Error as exception:
            logging.debug("DataBase log_contact: %s", exception)

    def delete_contact(self, contact) -> None:
        """Deletes a contact from the db."""
        if contact:
            try:
                with sqlite3.connect(self.database) as conn:
                    sql = f"delete from contacts where id={int(contact)}"
                    cur = conn.cursor()
                    cur.execute(sql)
                    conn.commit()
            except sqlite3.Error as exception:
                logging.debug("DataBase delete_contact: %s", exception)

    def change_contact(self, qso):
        """Update an existing contact."""
        try:
            with sqlite3.connect(self.database) as conn:
                sql = (
                    f"update contacts set callsign = '{qso[1]}', class = '{qso[2]}', "
                    f"section = '{qso[3]}', date_time = '{qso[4]}', band = '{qso[5]}', "
                    f"mode = '{qso[6]}', power = '{qso[7]}'  where id='{qso[0]}'"
                )
                cur = conn.cursor()
                cur.execute(sql)
                conn.commit()
        except sqlite3.Error as exception:
            logging.debug("DataBase change_contact: %s", exception)

    def stats(self) -> tuple:
        """
        returns a tuple with some stats:
        cwcontacts, phonecontacts, digitalcontacts, bandmodemult, last15, lasthour, hignpower, qrp
        """
        with sqlite3.connect(self.database) as conn:
            cursor = conn.cursor()
            cursor.execute("select count(*) from contacts where mode = 'CW'")
            cwcontacts = str(cursor.fetchone()[0])
            cursor.execute("select count(*) from contacts where mode = 'PH'")
            phonecontacts = str(cursor.fetchone()[0])
            cursor.execute("select count(*) from contacts where mode = 'DI'")
            digitalcontacts = str(cursor.fetchone()[0])
            cursor.execute("select distinct band, mode from contacts")
            bandmodemult = len(cursor.fetchall())
            cursor.execute(
                "SELECT count(*) FROM contacts "
                "where datetime(date_time) >=datetime('now', '-15 Minutes')"
            )
            last15 = str(cursor.fetchone()[0])
            cursor.execute(
                "SELECT count(*) FROM contacts "
                "where datetime(date_time) >=datetime('now', '-1 Hours')"
            )
            lasthour = str(cursor.fetchone()[0])
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
            highpower = bool(list(log[0])[0])
            qrp = not qrpc + qrpp + qrpd

            return (
                cwcontacts,
                phonecontacts,
                digitalcontacts,
                bandmodemult,
                last15,
                lasthour,
                highpower,
                qrp,
            )

    def get_band_mode_tally(self, band, mode):
        """
        returns the amount of contacts and the maximum power used
        for a given band using a particular mode.
        """
        with sqlite3.connect(self.database) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "select count(*) as tally, MAX(power) as mpow from contacts "
                f"where band = '{band}' AND mode ='{mode}'"
            )
            return cursor.fetchone()

    def get_bands(self) -> tuple:
        """returns a list of bands"""
        with sqlite3.connect(self.database) as conn:
            cursor = conn.cursor()
            cursor.execute("select DISTINCT band from contacts")
            return cursor.fetchall()

    def fetch_all_contacts_asc(self) -> tuple:
        """returns a tuple of all contacts in the database."""
        with sqlite3.connect(self.database) as conn:
            cursor = conn.cursor()
            cursor.execute("select * from contacts order by date_time ASC")
            return cursor.fetchall()

    def fetch_all_contacts_desc(self) -> tuple:
        """returns a tuple of all contacts in the database."""
        with sqlite3.connect(self.database) as conn:
            cursor = conn.cursor()
            cursor.execute("select * from contacts order by date_time desc")
            return cursor.fetchall()

    def fetch_last_contact(self) -> tuple:
        """returns a tuple of all contacts in the database."""
        with sqlite3.connect(self.database) as conn:
            cursor = conn.cursor()
            cursor.execute("select * from contacts order by date_time desc")
            return cursor.fetchone()

    def dup_check(self, acall: str) -> tuple:
        """returns a list of possible dups"""
        with sqlite3.connect(self.database) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "select callsign, class, section, band, mode "
                f"from contacts where callsign like '{acall}' order by band"
            )
            return cursor.fetchall()

    def sections(self) -> tuple:
        """returns a list of sections worked."""
        with sqlite3.connect(self.database) as conn:
            cursor = conn.cursor()
            cursor.execute("select distinct section from contacts")
            return cursor.fetchall()

    def contact_by_id(self, record) -> tuple:
        """returns a contact matching an id"""
        with sqlite3.connect(self.database) as conn:
            cursor = conn.cursor()
            cursor.execute("select * from contacts where id=" + record)
            return cursor.fetchall()
