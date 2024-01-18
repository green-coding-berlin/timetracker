"""
This module contains a Caribou migration.

Migration Name: my_first_migration
Migration Version: 20240116160225
"""

def upgrade(connection):
    # connection is a plain old sqlite3 database connection
    sql = """CREATE TABLE IF NOT EXISTS appdata
            (id INTEGER PRIMARY KEY,
            time INT,
            application STRING,
            title STRING,
            positionX INT,
            positionY INT,
            sizeX INT,
            sizeY INT
            ) """
    connection.execute(sql)

    connection.commit()

def downgrade(connection):
    connection.execute('DROP TABLE appdata')