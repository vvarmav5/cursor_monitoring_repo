import sqlite3


def connect(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(path):
    connection = connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS admin (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                ssh_user TEXT NOT NULL,
                ssh_password TEXT NOT NULL
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def admin_hash(connection):
    row = connection.execute(
        "SELECT password_hash FROM admin WHERE id = 1"
    ).fetchone()
    if row is None:
        return None
    return row["password_hash"]


def save_admin(connection, password_hash):
    connection.execute(
        "INSERT INTO admin (id, username, password_hash) VALUES (1, ?, ?)",
        ("admin", password_hash),
    )
    connection.commit()


def list_servers(connection):
    return connection.execute(
        """
        SELECT id, display_name, host, port, ssh_user
        FROM servers
        ORDER BY id
        """
    ).fetchall()


def add_server(connection, display_name, host, port, ssh_user, ssh_password):
    cursor = connection.execute(
        """
        INSERT INTO servers (display_name, host, port, ssh_user, ssh_password)
        VALUES (?, ?, ?, ?, ?)
        """,
        (display_name, host, port, ssh_user, ssh_password),
    )
    connection.commit()
    return cursor.lastrowid


def delete_server(connection, server_id):
    connection.execute("DELETE FROM servers WHERE id = ?", (server_id,))
    connection.commit()


def get_server_summary(connection, server_id):
    return connection.execute(
        """
        SELECT id, display_name, host, port, ssh_user
        FROM servers
        WHERE id = ?
        """,
        (server_id,),
    ).fetchone()


def get_server_login(connection, server_id):
    return connection.execute(
        """
        SELECT id, host, port, ssh_user, ssh_password
        FROM servers
        WHERE id = ?
        """,
        (server_id,),
    ).fetchone()
