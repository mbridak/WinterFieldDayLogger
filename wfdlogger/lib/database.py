"""
K6GTE, Database class to store contacts
Email: michael.bridak@gmail.com
GPL V3
"""
import logging
import sqlite3

if __name__ == "__main__":
    print("I'm not the program you are looking for.")


class DataBase:
    """Database class for our database."""

    def __init__(self, database):
        """initializes DataBase instance"""
        self.database = database
        self.create_db()

    @staticmethod
    def row_factory(cursor, row):
        """
        cursor.description:
        (name, type_code, display_size,
        internal_size, precision, scale, null_ok)
        row: (value, value, ...)
        """
        return {
            col[0]: row[idx]
            for idx, col in enumerate(
                cursor.description,
            )
        }

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
                "frequency INTEGER DEFAULT 0, "
                "band text NOT NULL, "
                "mode text NOT NULL, "
                "power INTEGER NOT NULL, "
                "grid text NOT NULL, "
                "opname text NOT NULL,"
                "IsRunQSO INTEGER DEFAULT 0,"
                "unique_id text NOT NULL, "
                "dirty INTEGER DEFAULT 1);"
            )
            cursor.execute(sql_table)
            conn.commit()

    def log_contact(self, logme: tuple) -> None:
        """
        Inserts a contact into the db.
        pass in (hiscall, hisclass, hissection, frequency,band, mode, int(power),
        grid, opname, IsRunQSO, unique_id)
        """
        logging.info("%s", logme)
        try:
            with sqlite3.connect(self.database) as conn:
                sql = (
                    "INSERT INTO contacts"
                    "(callsign, class, section, frequency, date_time, "
                    "band, mode, power, grid, opname, IsRunQSO, unique_id, dirty) "
                    "VALUES(?,?,?,?,datetime('now'),?,?,?,?,?,?,?,1);"
                )
                logging.info("%s", sql)
                cur = conn.cursor()
                cur.execute(sql, logme)
                conn.commit()
        except sqlite3.Error as exception:
            logging.info("DataBase log_contact: %s", exception)

    def clear_dirty_flag(self, unique_id) -> None:
        """Clears the dirty flag."""
        if unique_id:
            try:
                with sqlite3.connect(self.database) as conn:
                    sql = f"update contacts set dirty=0 where unique_id='{unique_id}';"
                    cursor = conn.cursor()
                    cursor.execute(sql)
                    conn.commit()
            except sqlite3.Error as exception:
                logging.critical("%s", exception)

    def get_unique_id(self, contact) -> str:
        """get unique id"""
        unique_id = ""
        if contact:
            try:
                with sqlite3.connect(self.database) as conn:
                    sql = f"select unique_id from contacts where id={int(contact)}"
                    cursor = conn.cursor()
                    cursor.execute(sql)
                    unique_id = str(cursor.fetchone()[0])
            except sqlite3.Error as exception:
                logging.debug("%s", exception)
        return unique_id

    def delete_contact(self, contact) -> None:
        """Deletes a contact from the db."""
        if contact:
            try:
                with sqlite3.connect(self.database) as conn:
                    sql = f"delete from contacts where id={int(contact)};"
                    cur = conn.cursor()
                    cur.execute(sql)
                    conn.commit()
            except sqlite3.Error as exception:
                logging.info("DataBase delete_contact: %s", exception)

    def change_contact(self, qso):
        """Update an existing contact."""
        try:
            with sqlite3.connect(self.database) as conn:
                sql = (
                    f"update contacts set callsign = '{qso[0]}', class = '{qso[1]}', "
                    f"section = '{qso[2]}', date_time = '{qso[3]}', band = '{qso[4]}', "
                    f"mode = '{qso[5]}', power = '{qso[6]}', frequency = '{qso[7]}' "
                    f"where id='{qso[8]}';"
                )
                logging.info("%s\n%s", sql, qso)
                cur = conn.cursor()
                cur.execute(sql)
                conn.commit()
        except sqlite3.Error as exception:
            logging.info("DataBase change_contact: %s", exception)

    def stats(self) -> dict:
        """
        returns a dict with some stats:
        cwcontacts, phonecontacts, digitalcontacts, bandmodemult, last15, lasthour, highpower, qrp
        """
        with sqlite3.connect(self.database) as conn:
            cursor = conn.cursor()
            cursor.execute("select count(*) from contacts where mode = 'CW';")
            cwcontacts = str(cursor.fetchone()[0])
            cursor.execute("select count(*) from contacts where mode = 'PH';")
            phonecontacts = str(cursor.fetchone()[0])
            cursor.execute("select count(*) from contacts where mode = 'DI';")
            digitalcontacts = str(cursor.fetchone()[0])
            cursor.execute("select distinct band, mode from contacts;")
            bandmodemult = len(cursor.fetchall())
            cursor.execute(
                "SELECT count(*) FROM contacts "
                "where datetime(date_time) >=datetime('now', '-15 Minutes');"
            )
            last15 = str(cursor.fetchone()[0])
            cursor.execute(
                "SELECT count(*) FROM contacts "
                "where datetime(date_time) >=datetime('now', '-1 Hours');"
            )
            lasthour = str(cursor.fetchone()[0])
            cursor.execute(
                "select count(*) as qrpc from contacts where mode = 'CW' and power > 10;"
            )
            log = cursor.fetchall()
            qrpc = list(log[0])[0]
            cursor.execute(
                "select count(*) as qrpp from contacts where mode = 'PH' and power > 20;"
            )
            log = cursor.fetchall()
            qrpp = list(log[0])[0]
            cursor.execute(
                "select count(*) as qrpd from contacts where mode = 'DI' and power > 20;"
            )
            log = cursor.fetchall()
            qrpd = list(log[0])[0]
            cursor.execute(
                "select count(*) as highpower from contacts where power > 100;"
            )
            log = cursor.fetchall()
            highpower = bool(list(log[0])[0])
            qrp = not qrpc + qrpp + qrpd

            packaged_stats = {
                "cwcontacts": cwcontacts,
                "phonecontacts": phonecontacts,
                "digitalcontacts": digitalcontacts,
                "bandmodemult": bandmodemult,
                "last15": last15,
                "lasthour": lasthour,
                "highpower": highpower,
                "qrp": qrp,
            }

            return packaged_stats

    def get_band_mode_tally(self, band, mode):
        """
        returns list of dicts with amount of contacts and the maximum power used
        for a given band using a particular mode.
        Only showing contacts below 101 watts.
        """
        with sqlite3.connect(self.database) as conn:
            conn.row_factory = self.row_factory
            cursor = conn.cursor()
            cursor.execute(
                "select count(*) as tally, MAX(power) as mpow from contacts "
                f"where band = '{band}' AND mode ='{mode}' AND power < 101;"
            )
            return cursor.fetchone()

    def get_bands(self) -> list:
        """returns a list of dicts with bands"""
        with sqlite3.connect(self.database) as conn:
            conn.row_factory = self.row_factory
            cursor = conn.cursor()
            cursor.execute("select DISTINCT band from contacts;")
            return cursor.fetchall()

    def fetch_all_contacts_asc(self) -> list:
        """returns a list of dicts with contacts in the database."""
        with sqlite3.connect(self.database) as conn:
            conn.row_factory = self.row_factory
            cursor = conn.cursor()
            cursor.execute("select * from contacts order by date_time ASC;")
            return cursor.fetchall()

    def fetch_all_contacts_desc(self) -> list:
        """returns a list of dicts with contacts in the database."""
        with sqlite3.connect(self.database) as conn:
            conn.row_factory = self.row_factory
            cursor = conn.cursor()
            cursor.execute("select * from contacts order by date_time desc;")
            return cursor.fetchall()

    def fetch_last_contact(self) -> dict:
        """returns a list of dicts with last contact in the database."""
        with sqlite3.connect(self.database) as conn:
            conn.row_factory = self.row_factory
            cursor = conn.cursor()
            cursor.execute("select * from contacts order by date_time desc;")
            return cursor.fetchone()

    def fetch_all_dirty_contacts(self) -> list:
        """
        Return a list of dict, containing all contacts still flagged as dirty.\n
        Example:\n
        {\n
            'id': 2, 'callsign': 'N6QW', 'class': '1B', 'section': 'SB', \n
            'date_time': '2022-09-22 18:44:02', 'frequency': 1830000, 'band': '160', \n
            'mode': 'CW', 'power': 5, 'grid': 'DM04md', 'opname': 'PETER JULIANO', \n
            'unique_id': '6fe98693f3ac4250847a6e5ac9da650e', 'dirty': 1\n
        }\n
        """
        with sqlite3.connect(self.database) as conn:
            conn.row_factory = self.row_factory
            cursor = conn.cursor()
            cursor.execute("select * from contacts where dirty=1 order by id")
            return cursor.fetchall()

    def dup_check(self, acall: str) -> list:
        """returns a list of dicts with possible dups"""
        with sqlite3.connect(self.database) as conn:
            conn.row_factory = self.row_factory
            cursor = conn.cursor()
            cursor.execute(
                "select callsign, class, section, band, mode "
                f"from contacts where callsign like '{acall}' order by band;"
            )
            return cursor.fetchall()

    def count_all_dirty_contacts(self) -> dict:
        """
        Returns a dict containing the count of contacts still flagged as dirty.\n
        Example: {'alldirty': 3}
        """
        with sqlite3.connect(self.database) as conn:
            conn.row_factory = self.row_factory
            cursor = conn.cursor()
            cursor.execute("select count(*) as alldirty from contacts where dirty=1")
            return cursor.fetchone()

    def sections(self) -> list:
        """returns a list of dicts with sections worked."""
        with sqlite3.connect(self.database) as conn:
            conn.row_factory = self.row_factory
            cursor = conn.cursor()
            cursor.execute("select distinct section from contacts;")
            return cursor.fetchall()

    def contact_by_id(self, record) -> list:
        """returns a contact matching an id"""
        with sqlite3.connect(self.database) as conn:
            conn.row_factory = self.row_factory
            cursor = conn.cursor()
            cursor.execute(f"select * from contacts where id={record};")
            return cursor.fetchone()

    def get_unique_grids(self) -> list:
        """returns a list of dicts with unique gridsquares worked."""
        with sqlite3.connect(self.database) as conn:
            conn.row_factory = self.row_factory
            cursor = conn.cursor()
            cursor.execute("select DISTINCT grid from contacts;")
            return cursor.fetchall()
