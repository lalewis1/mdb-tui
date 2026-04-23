"""Database operations for Access database exploration."""

import logging
import sys
from typing import Any, Dict, List

import pyodbc

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Handles all database operations for Access databases."""

    def __init__(self, db_path: str, user: str = None, password: str = None):
        self.db_path = db_path
        self.user = user
        self.password = password
        self.connection = None
        self.is_32bit = sys.maxsize <= 2**32

    def connect(self) -> None:
        """Establish connection to Access database."""
        try:
            drivers = self._get_driver_list()

            for driver in drivers:
                try:
                    connection_string = f"DRIVER={{{driver}}};DBQ={self.db_path};"
                    if self.user:
                        connection_string += f"UID={self.user};"
                    if self.password:
                        connection_string += f"PWD={{{self.password}}};"
                    connection_string += "ReadOnly=True;"
                    logger.info(f"Trying driver: {driver}")
                    self.connection = pyodbc.connect(connection_string)
                    logger.info(f"Successfully connected using driver: {driver}")
                    return
                except pyodbc.Error as e:
                    logger.debug(f"Driver {driver} failed: {e}")
                    continue

            # If no driver worked
            available_drivers = pyodbc.drivers()
            logger.error(
                f"No suitable driver found. Available drivers: {available_drivers}"
            )
            raise Exception(
                f"No suitable ODBC driver found. Available drivers: {available_drivers}"
            )

        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def _get_driver_list(self) -> List[str]:
        """Get appropriate driver list based on Python architecture."""
        if self.is_32bit:
            return [
                "Microsoft Access Driver (*.mdb)",
                "Microsoft Access Driver (*.mdb, *.accdb)",
                "Microsoft Access Text Driver (*.txt, *.csv)",
                "ODBC Driver 17 for SQL Server",
            ]
        else:
            return [
                "Microsoft Access Driver (*.mdb, *.accdb)",
                "Microsoft Access Driver (*.mdb)",
                "Microsoft Access Text Driver (*.txt, *.csv)",
                "ODBC Driver 17 for SQL Server",
            ]

    def get_tables(self) -> List[Dict[str, str]]:
        """Get list of tables and views from database."""
        if not self.connection:
            raise Exception("Database not connected")

        cursor = self.connection.cursor()

        # Get tables
        cursor.tables(tableType="TABLE")
        tables = [
            {"name": row.table_name, "type": "TABLE"} for row in cursor.fetchall()
        ]

        # Get views
        cursor.tables(tableType="VIEW")
        views = [{"name": row.table_name, "type": "VIEW"} for row in cursor.fetchall()]

        return tables + views

    def get_table_columns(self, table_name: str) -> List[str]:
        """Get column names for a specific table."""
        if not self.connection:
            raise Exception("Database not connected")
        if not table_name:
            logger.warning("Empty table name provided")
            return []

        # First try: use SELECT TOP 1 * FROM table
        try:
            logger.info(f"Getting columns for table: {table_name}")
            cursor = self.connection.cursor()
            safe_table_name = self._quote_identifier(table_name)

            sql = f"SELECT TOP 1 * FROM {safe_table_name}"
            cursor.execute(sql)
            try:
                return [column[0] for column in cursor.description]
            except Exception:
                # https://github.com/mkleehammer/pyodbc/issues/328#issuecomment-629641164
                def decode_sketchy_utf8(raw_bytes):
                    null_terminated_bytes = raw_bytes.split(b'\x00')[0]
                    return null_terminated_bytes.decode('utf-8')

                self.connection.add_output_converter(pyodbc.SQL_VARCHAR, decode_sketchy_utf8)
                columns = [column[0] for column in cursor.description]
                self.connection.remove_output_converter(pyodbc.SQL_VARCHAR)
                return columns

        except pyodbc.ProgrammingError as e:
            # Access may throw "too few parameters" for views with parameter queries
            # Fall back to cursor.columns() metadata API
            logger.warning(f"SQL query failed for {table_name}, falling back to cursor.columns(): {e}")
            try:
                cursor2 = self.connection.cursor()
                cursor2.columns(table=table_name)
                try:
                    return [row.column_name for row in cursor2.fetchall()]
                except Exception:
                    self.connection.add_output_converter(pyodbc.SQL_VARCHAR, decode_sketchy_utf8)
                    columns = [row.column_name for row in cursor2.fetchall()]
                    self.connection.remove_output_converter(pyodbc.SQL_VARCHAR)
                    return columns
            except Exception as e2:
                logger.error(f"cursor.columns() also failed for {table_name}: {e2}")
                raise

        except Exception as e:
            logger.error(f"Error getting columns for table {table_name}: {e}")
            raise

    def get_table_data(self, table_name: str, limit: int = 100) -> Dict[str, Any]:
        """Get data from a table with optional limit."""
        if not self.connection:
            raise Exception("Database not connected")

        try:
            cursor = self.connection.cursor()
            safe_table_name = self._quote_identifier(table_name)

            sql = f"SELECT TOP {limit} * FROM {safe_table_name}"
            cursor.execute(sql)
            try:
                columns = [column[0] for column in cursor.description]
                data = cursor.fetchall()
            except Exception:
                # https://github.com/mkleehammer/pyodbc/issues/328#issuecomment-629641164
                def decode_sketchy_utf8(raw_bytes):
                    null_terminated_bytes = raw_bytes.split(b'\x00')[0]
                    return null_terminated_bytes.decode('utf-8')

                self.connection.add_output_converter(pyodbc.SQL_VARCHAR, decode_sketchy_utf8)
                columns = [column[0] for column in cursor.description]
                data = cursor.fetchall()
                self.connection.remove_output_converter(pyodbc.SQL_VARCHAR)

            return {"columns": columns, "data": data, "sql": sql}

        except Exception as e:
            logger.error(f"Error getting data from table {table_name}: {e}")
            raise

    def _get_type_name(self, type_code: int) -> str:
        """Map pyodbc type code to human-readable type name."""
        type_map = {
            pyodbc.SQL_CHAR: "CHAR",
            pyodbc.SQL_VARCHAR: "VARCHAR",
            pyodbc.SQL_WVARCHAR: "VARCHAR",
            pyodbc.SQL_LONGVARCHAR: "LONGVARCHAR",
            pyodbc.SQL_WLONGVARCHAR: "TEXT",
            pyodbc.SQL_DECIMAL: "DECIMAL",
            pyodbc.SQL_NUMERIC: "NUMERIC",
            pyodbc.SQL_SMALLINT: "SMALLINT",
            pyodbc.SQL_INTEGER: "INTEGER",
            pyodbc.SQL_REAL: "REAL",
            pyodbc.SQL_FLOAT: "FLOAT",
            pyodbc.SQL_DOUBLE: "DOUBLE",
            pyodbc.SQL_BIT: "BOOLEAN",
            pyodbc.SQL_TINYINT: "TINYINT",
            pyodbc.SQL_BIGINT: "BIGINT",
            pyodbc.SQL_TYPE_DATE: "DATE",
            pyodbc.SQL_TYPE_TIME: "TIME",
            pyodbc.SQL_TYPE_TIMESTAMP: "DATETIME",
            pyodbc.SQL_BINARY: "BINARY",
            pyodbc.SQL_VARBINARY: "VARBINARY",
            pyodbc.SQL_LONGVARBINARY: "BLOB",
        }
        return type_map.get(type_code, f"UNKNOWN({type_code})")

    def get_column_statistics(
        self, table_name: str, column_name: str
    ) -> Dict[str, Any]:
        """Get statistics for a specific column."""
        if not self.connection:
            raise Exception("Database not connected")

        try:
            cursor = self.connection.cursor()
            safe_table = self._quote_identifier(table_name)
            safe_column = self._quote_identifier(column_name)

            # Get column type from SELECT TOP 1 * query
            data_type = "unknown"
            try:
                sql_columns = f"SELECT TOP 1 * FROM {safe_table}"
                cursor.execute(sql_columns)
                for col in cursor.description:
                    if col[0] == column_name:
                        data_type = self._get_type_name(col[1])
                        break
            except pyodbc.ProgrammingError as e:
                # Access may throw "too few parameters" for views with parameter queries
                # Fall back to cursor.columns() metadata API for type info
                logger.warning(f"SQL query failed for {table_name}, falling back to cursor.columns(): {e}")
                try:
                    cursor2 = self.connection.cursor()
                    cursor2.columns(table=table_name)
                    for row in cursor2.fetchall():
                        if row.column_name == column_name:
                            data_type = str(row.type_name)
                            break
                except Exception as e2:
                    logger.error(f"cursor.columns() also failed for {table_name}: {e2}")

            # Count rows and nulls
            row_count = 0
            null_count = 0
            distinct_count = 0
            try:
                sql = (
                    f"SELECT COUNT(*) as row_count, "
                    f"SUM(IIF({safe_column} IS NULL OR {safe_column}='',1,0)) as null_count "
                    f"FROM {safe_table}"
                )
                cursor.execute(sql)
                result = cursor.fetchone()
                row_count = (
                    int(result.row_count) if result and result.row_count is not None else 0
                )
                null_count = (
                    int(result.null_count)
                    if result and result.null_count is not None
                    else 0
                )

                # Count distinct values
                distinct_sql = (
                    f"SELECT COUNT(*) AS distinct_count FROM "
                    f"(SELECT DISTINCT {safe_column} FROM {safe_table} "
                    f"WHERE {safe_column} IS NOT NULL AND {safe_column} <> '') AS DQ"
                )
                cursor.execute(distinct_sql)
                distinct_result = cursor.fetchone()
                distinct_count = (
                    int(distinct_result.distinct_count)
                    if distinct_result and distinct_result.distinct_count is not None
                    else 0
                )
            except pyodbc.ProgrammingError as e:
                logger.warning(f"Stats queries failed for {table_name}.{column_name}: {e}")

            return {
                "row_count": row_count,
                "null_count": null_count,
                "distinct_count": distinct_count,
                "data_type": data_type,
                "stats_sql": sql if 'sql' in locals() else "",
                "distinct_sql": distinct_sql if 'distinct_sql' in locals() else "",
            }

        except Exception as e:
            logger.error(f"Error getting column statistics: {e}")
            raise

    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def _quote_identifier(self, identifier: str) -> str:
        """Properly quote SQL identifiers for Access."""
        if not identifier:
            return ""

        # Escape existing brackets by doubling them
        safe_identifier = identifier.replace("]", "]]")

        # Wrap in brackets for Access SQL
        return f"[{safe_identifier}]"

    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self.connection is not None
