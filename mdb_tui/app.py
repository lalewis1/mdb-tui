"""Main TUI application for exploring Access databases."""

import logging
import os
import sys

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, ScrollableContainer
from textual.widgets import DataTable, Footer, Header, Label, Log, Tree

from .database import DatabaseManager
from .ui_components import (
    DatabaseTreeManager,
    DataTableManager,
    StatusManager,
    LoggerManager,
)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("mdb-tui.debug.log")],
)
logger = logging.getLogger(__name__)


class DatabaseExplorer(App):
    """A TUI application for exploring Access databases in read-only mode."""

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("j", "down", "Down", show=False),
        Binding("k", "up", "Up", show=False),
        Binding("h", "left", "Left", show=False),
        Binding("l", "right", "Right", show=False),
        Binding("gg", "home", "Home", show=False),
        Binding("G", "end", "End", show=False),
        Binding("/", "search", "Search", show=False),
        Binding("s", "show_stats", "Show Stats", show=True),
        Binding("escape", "return_to_tree", "Return to Tree", show=False),
    ]

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        self.tree_manager = None
        self.data_manager = None
        self.status_manager = None
        self.logger_manager = None
        super().__init__()

    CSS = """
    #debug-log {
        height: 3;
        min-height: 3;
        max-height: 3;
    }

    #main-container {
        height: 1fr;
    }

    #tree-container {
        width: 30%;
        dock: left;
    }

    DataTable.unfocused-datatable {
        background: $surface-darken-3 80%;
        color: $text 40%;
        opacity: 0.65;
        transition: opacity 0.15s;
    }
    """

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Container(
            Container(
                Label("Database Explorer", id="title"),
                Tree("Database Structure", id="db-tree"),
                Label("Select a table or column to see details", id="column-summary"),
                id="tree-container",
            ),
            Container(
                ScrollableContainer(DataTable(id="data-view"), id="data-container"),
                Label("", id="sql-panel"),
                id="data-panel",
            ),
            id="main-container",
        )
        yield Log(id="debug-log", max_lines=3)
        yield Footer()

    def on_mount(self) -> None:
        """Connect to database and load structure when app starts."""
        try:
            # Initialize UI managers
            self._initialize_ui_managers()

            self._log_to_panel(f"Starting mdb-tui with database: {self.db_path}")
            self._log_to_panel(f"Current working directory: {os.getcwd()}")
            self._log_to_panel(f"Database file exists: {os.path.exists(self.db_path)}")

            # Check for .accdb files with 32-bit Python
            is_32bit = sys.maxsize <= 2**32
            if is_32bit and self.db_path.lower().endswith(".accdb"):
                logger.warning(
                    "32-bit Python detected with .accdb file - may not work with older drivers"
                )
                self.notify(
                    "Warning: 32-bit Python with .accdb file may have limited compatibility",
                    severity="warning",
                )

            # Connect to database
            self.db_manager.connect()

            # Load database structure
            self.tables = self.db_manager.get_tables()
            self._log_to_panel(f"Found {len(self.tables)} tables: {self.tables}")

            # Update tree view
            self.tree_manager.update_tree(self.tables)

            # Debug: check tree structure
            self._log_to_panel(
                f"Tree root has {len(self.tree_manager.tree.root.children)} children"
            )
            for i, child in enumerate(self.tree_manager.tree.root.children):
                self._log_to_panel(f"  Child {i}: {child.label} (data: {child.data})")

            # Set initial focus to tree view
            self.tree_manager.tree.focus()
            logger.info("Set initial focus to tree view")

            logger.info("Database connection and structure loading successful")
        except Exception as e:
            logger.error(f"Error connecting to database: {e}", exc_info=True)
            self.app.exit(f"Error connecting to database: {e}")

    def _initialize_ui_managers(self) -> None:
        """Initialize all UI component managers."""
        self.tree_manager = DatabaseTreeManager(self)
        self.data_manager = DataTableManager(self)
        self.status_manager = StatusManager(self)
        self.logger_manager = LoggerManager(self)

        # Initialize each manager
        self.tree_manager.initialize()
        self.data_manager.initialize()

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """Handle table expansion to load columns."""
        self.tree_manager.handle_node_expanded(event)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle table/column selection from tree view."""
        node = event.node

        if not node.data:
            return

        if node.data.get("type") == "table":
            # Table selected - load table data
            table_name = node.data["name"]
            self.data_manager.load_table_data(table_name)
            self.data_manager.focus()
            self.status_manager.update_column_summary()

        elif node.data.get("type") == "column":
            # Column selected - load table data and highlight column
            table_name = node.data["table"]
            column_name = node.data["name"]

            self.data_manager.load_table_data(table_name)
            self.data_manager.focus()
            self.data_manager.highlight_column(column_name)
            self.status_manager.update_column_summary()

    def action_show_stats(self) -> None:
        """Show statistics for the current column (via key 's')."""
        # Try to get currently selected column, first from the tree view, then from data table
        column_name = None
        table_name = self.data_manager.current_table if self.data_manager else None

        try:
            # Try tree selection first
            tree = self.query_one("#db-tree", Tree)
            node = tree.cursor_node
            if node and node.data and node.data.get("type") == "column":
                column_name = node.data["name"]
                table_name = node.data["table"]
        except Exception:
            pass

        # If not found, try the focused data table column
        if not column_name and self.data_manager and self.data_manager.table:
            try:
                if self.data_manager.table.cursor_column is not None:
                    column_name = self.data_manager.table.columns[
                        self.data_manager.table.cursor_column
                    ].label
            except Exception:
                pass

        if not column_name or not table_name or not self.data_manager.current_data:
            self.status_manager.update_column_summary()
            return

        # Calculate stats
        try:
            stats = self.db_manager.get_column_statistics(table_name, column_name)
            self.status_manager.update_column_summary(
                column_name=column_name, table_name=table_name, stats=stats
            )
            self.status_manager.update_sql_panel(
                sql=stats["stats_sql"], additional_sql=stats["distinct_sql"]
            )
        except Exception as e:
            logger.error(f"Error calculating column stats: {e}")
            self.notify(f"Error calculating stats: {e}", severity="error")

    def action_quit(self) -> None:
        """Quit the application."""
        if self.db_manager:
            self.db_manager.close()
        self.app.exit()

    def _log_to_panel(self, message: str, level: str = "INFO") -> None:
        """Write a message to the Textual Log widget."""
        if self.logger_manager:
            self.logger_manager.log_to_panel(message, level)
        else:
            # Fallback logging
            if level == "INFO":
                logger.info(message)
            elif level == "ERROR":
                logger.error(message)
            elif level == "DEBUG":
                logger.debug(message)
            elif level == "WARNING":
                logger.warning(message)

    def action_return_to_tree(self) -> None:
        """Return focus to tree view (Escape key)."""
        logger.debug("Returning focus to tree view")
        if self.tree_manager and self.tree_manager.tree:
            self.tree_manager.tree.focus()
        if self.data_manager and self.data_manager.table:
            self.data_manager.table.add_class("unfocused-datatable")

    def action_down(self) -> None:
        """Move down (vim j)."""
        if (
            self.tree_manager
            and self.tree_manager.tree
            and self.tree_manager.tree.has_focus
        ):
            logger.debug("Moving down in tree view")
            self.tree_manager.tree.action_cursor_down()
        elif self.data_manager and self.data_manager.table:
            logger.debug("Moving down in data table")
            self.data_manager.table.action_cursor_down()

    def action_up(self) -> None:
        """Move up (vim k)."""
        if (
            self.tree_manager
            and self.tree_manager.tree
            and self.tree_manager.tree.has_focus
        ):
            logger.debug("Moving up in tree view")
            self.tree_manager.tree.action_cursor_up()
        elif self.data_manager and self.data_manager.table:
            logger.debug("Moving up in data table")
            self.data_manager.table.action_cursor_up()

    def action_left(self) -> None:
        """Move left/collapse (vim h)."""
        if (
            self.tree_manager
            and self.tree_manager.tree
            and self.tree_manager.tree.has_focus
        ):
            logger.debug("Collapsing node in tree view")
            cursor_node = self.tree_manager.tree.cursor_node
            # For tree view, left means collapse if expanded, otherwise move left
            if cursor_node and cursor_node.is_expanded:
                self.tree_manager.tree.action_toggle_node()
            elif cursor_node and cursor_node != self.tree_manager.tree.root:
                # Only try to move left if not on root node and there is a parent
                if (
                    getattr(cursor_node, "parent", None)
                    and cursor_node.parent != self.tree_manager.tree.root
                ):
                    self.tree_manager.tree.action_cursor_left()
                else:
                    logger.debug(
                        "No-op: 'h' pressed on node without parent (table or column)"
                    )
        elif self.data_manager and self.data_manager.table:
            logger.debug("Moving left in data table")
            self.data_manager.table.action_cursor_left()

    def action_right(self) -> None:
        """Move right/expand (vim l) - expands table to show columns."""
        if (
            self.tree_manager
            and self.tree_manager.tree
            and self.tree_manager.tree.has_focus
        ):
            logger.debug("Expanding node in tree view")
            cursor_node = self.tree_manager.tree.cursor_node

            if cursor_node:
                # If it's a table node that's not expanded, expand it to show columns
                if (
                    cursor_node.data
                    and cursor_node.data.get("type") == "table"
                    and not cursor_node.is_expanded
                ):
                    self.tree_manager.tree.action_toggle_node()
                # For root node or if it's already a table node, just expand/collapse
                elif cursor_node == self.tree_manager.tree.root:
                    # If root is not expanded, expand it; else move cursor to first child if it exists
                    if not cursor_node.is_expanded:
                        self.tree_manager.tree.action_toggle_node()
                    elif cursor_node.children:
                        self.tree_manager.tree.cursor_line = (
                            1  # Move to first child (root is line 0)
                        )
                        self.tree_manager.tree.refresh()
                elif cursor_node.children:
                    self.tree_manager.tree.action_cursor_right()
        elif self.data_manager and self.data_manager.table:
            logger.debug("Moving right in data table")
            self.data_manager.table.action_cursor_right()

    def action_home(self) -> None:
        """Go to home (vim gg)."""
        if (
            self.tree_manager
            and self.tree_manager.tree
            and self.tree_manager.tree.has_focus
        ):
            logger.debug("Going to home in tree view")
            self.tree_manager.tree.action_cursor_home()
        elif self.data_manager and self.data_manager.table:
            logger.debug("Going to home in data table")
            self.data_manager.table.action_cursor_home()

    def action_end(self) -> None:
        """Go to end (vim G)."""
        if (
            self.tree_manager
            and self.tree_manager.tree
            and self.tree_manager.tree.has_focus
        ):
            logger.debug("Going to end in tree view")
            self.tree_manager.tree.action_cursor_end()
        elif self.data_manager and self.data_manager.table:
            logger.debug("Going to end in data table")
            self.data_manager.table.action_cursor_end()

    def on_key(self, event):
        from textual.events import Key

        if isinstance(event, Key):
            if event.key == "s":
                # Always trigger stats for the current selection
                self.action_show_stats()
                event.stop()
                return
        super().on_key(event)


def main():
    """Main entry point."""
    import sys

    # Set up logging for the main function
    logger.info(f"mdb-tui starting with arguments: {sys.argv}")

    if len(sys.argv) != 2:
        logger.error("No database path provided")
        is_32bit = sys.maxsize <= 2**32
        print("Usage: mdb-tui <database_path>")
        print("Example: mdb-tui C:\\path\\to\\database.mdb")
        print(f"Current Python architecture: {'32-bit' if is_32bit else '64-bit'}")
        print("Debug log saved to mdb-tui.debug.log")
        sys.exit(1)

    db_path = sys.argv[1]

    # Check if file exists
    # Handle Windows paths and normalize path separators
    db_path = os.path.normpath(db_path)
    logger.info(f"Normalized database path: {db_path}")

    # Detect and log Python architecture
    is_32bit = sys.maxsize <= 2**32
    logger.info(f"Python architecture: {'32-bit' if is_32bit else '64-bit'}")

    # Warn about .accdb files with 32-bit Python
    if is_32bit and db_path.lower().endswith(".accdb"):
        logger.warning("32-bit Python with .accdb file - compatibility may be limited")

    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        print(f"Error: Database file not found: {db_path}")
        print("Debug log saved to mdb-tui.debug.log")

        # Show available ODBC drivers for debugging
        try:
            import pyodbc

            drivers = pyodbc.drivers()
            logger.info(f"Available ODBC drivers: {drivers}")
            if drivers:
                print(f"Available ODBC drivers: {', '.join(drivers)}")
            else:
                print(
                    "No ODBC drivers found. Please install Microsoft Access Database Engine."
                )
        except Exception as e:
            logger.error(f"Could not check ODBC drivers: {e}")
            print(
                "Could not check ODBC drivers. Please ensure pyodbc is installed correctly."
            )

        sys.exit(1)

    try:
        logger.info(f"Creating DatabaseExplorer for: {db_path}")
        app = DatabaseExplorer(db_path)
        logger.info("Starting Textual application")
        app.run()
    except Exception as e:
        logger.error(f"Application failed to start: {e}", exc_info=True)
        print(f"Error: {e}")
        print("Debug log saved to mdb-tui.debug.log")
        sys.exit(1)


if __name__ == "__main__":
    main()
