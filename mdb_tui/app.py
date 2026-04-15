"""Main TUI application for exploring Access databases."""

import pyodbc
import sys
import os
from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.widgets import Header, Footer, Tree, DataTable, Input, Label, Log
from textual.binding import Binding

# Simple logging to file (Textual Log widget will handle display)
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mdb-tui.debug.log')
    ]
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
        Binding("escape", "return_to_tree", "Return to Tree", show=False),
    ]
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
        self.tables = []
        self.current_table = None
        self.current_data = []
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
    
    #data-panel {
        width: 70%;
        dock: right;
    }
    """
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Container(
            Container(
                Label("Database Explorer", id="title"),
                Tree("Database Structure", id="db-tree"),
                id="tree-container"
            ),
            Container(
                ScrollableContainer(
                    DataTable(id="data-view"),
                    id="data-container"
                ),
                Label("Select a table or column to see details", id="column-summary"),
                id="data-panel"
            ),
            id="main-container"
        )
        yield Log(id="debug-log", max_lines=3)
        yield Footer()
    
    def on_mount(self) -> None:
        """Connect to database and load structure when app starts."""
        try:
            self._log_to_panel(f"Starting mdb-tui with database: {self.db_path}")
            self._log_to_panel(f"Current working directory: {os.getcwd()}")
            self._log_to_panel(f"Database file exists: {os.path.exists(self.db_path)}")
            
            # Check for .accdb files with 32-bit Python
            is_32bit = sys.maxsize <= 2**32
            if is_32bit and self.db_path.lower().endswith('.accdb'):
                logger.warning("32-bit Python detected with .accdb file - may not work with older drivers")
                self.notify("Warning: 32-bit Python with .accdb file may have limited compatibility", severity="warning")
            
            self.connect_to_database()
            self.load_database_structure()
            
            # Debug: log the tables we found
            self._log_to_panel(f"Found {len(self.tables)} tables: {self.tables}")
            
            self.update_tree_view()
            
            # Debug: check tree structure
            tree = self.query_one("#db-tree", Tree)
            self._log_to_panel(f"Tree root has {len(tree.root.children)} children")
            for i, child in enumerate(tree.root.children):
                self._log_to_panel(f"  Child {i}: {child.label} (data: {child.data})")
            
            # Set initial focus to tree view
            tree.focus()
            logger.info("Set initial focus to tree view")
            
            logger.info("Database connection and structure loading successful")
        except Exception as e:
            logger.error(f"Error connecting to database: {e}", exc_info=True)
            self.app.exit(f"Error connecting to database: {e}")
    
    def connect_to_database(self):
        """Establish connection to Access database."""
        try:
            # Detect Python architecture
            is_32bit = sys.maxsize <= 2**32
            logger.info(f"Python architecture: {'32-bit' if is_32bit else '64-bit'}")
            
            # Try different driver names for Windows/Linux compatibility
            # Order matters: try most likely drivers first
            if is_32bit:
                # 32-bit Python should use the older driver without *.accdb support
                drivers = [
                    "Microsoft Access Driver (*.mdb)",  # 32-bit driver (no accdb support)
                    "Microsoft Access Driver (*.mdb, *.accdb)",  # Try newer driver anyway
                    "Microsoft Access Text Driver (*.txt, *.csv)",
                    "ODBC Driver 17 for SQL Server"  # Fallback
                ]
            else:
                # 64-bit Python can use the newer driver with accdb support
                drivers = [
                    "Microsoft Access Driver (*.mdb, *.accdb)",  # 64-bit driver (preferred)
                    "Microsoft Access Driver (*.mdb)",  # Fallback to older driver
                    "Microsoft Access Text Driver (*.txt, *.csv)",
                    "ODBC Driver 17 for SQL Server"  # Fallback
                ]
            
            for driver in drivers:
                try:
                    connection_string = (
                        f"DRIVER={{{driver}}};"
                        f"DBQ={self.db_path};"
                        "ReadOnly=True;"
                    )
                    logger.info(f"Trying driver: {driver}")
                    self.connection = pyodbc.connect(connection_string)
                    logger.info(f"Successfully connected using driver: {driver}")
                    return
                except pyodbc.Error as e:
                    logger.debug(f"Driver {driver} failed: {e}")
                    continue
            
            # If no driver worked
            available_drivers = pyodbc.drivers()
            logger.error(f"No suitable driver found. Available drivers: {available_drivers}")
            raise Exception(f"No suitable ODBC driver found. Available drivers: {available_drivers}")
            
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def load_database_structure(self):
        """Load tables and views from the database."""
        cursor = self.connection.cursor()
        
        # Get tables
        cursor.tables(tableType="TABLE")
        self.tables = [row.table_name for row in cursor.fetchall()]
        
        # Get views
        cursor.tables(tableType="VIEW")
        views = [row.table_name for row in cursor.fetchall()]
        
        self.tables.extend(views)
    
    def update_tree_view(self):
        """Update the tree view with database structure."""
        tree = self.query_one("#db-tree", Tree)
        tree.clear()
        
        root = tree.root
        root.label = self.db_path
        root.allow_expand = True
        
        for table in self.tables:
            table_node = root.add(table)
            table_node.data = {"type": "table", "name": table}
            table_node.allow_expand = True
            # Add a placeholder child that will be replaced when expanded
            placeholder = table_node.add("Loading columns...")
            placeholder.data = {"type": "placeholder"}
    
    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """Handle table expansion to load columns."""
        node = event.node
        
        self._log_to_panel(f"Node expanded: {node.label} (type: {node.data.get('type') if node.data else 'no data'})")
        
        # Check if this is a table node being expanded
        if (node.data and node.data.get("type") == "table" and 
            node.children and node.children[0].data.get("type") == "placeholder"):
            
            table_name = node.data["name"]
            self._log_to_panel(f"Loading columns for table: {table_name}")
            
            try:
                columns = self._get_table_columns(table_name)
                self._log_to_panel(f"Found {len(columns)} columns: {columns}")
                
                # Remove the placeholder
                placeholder = node.children[0]
                placeholder.remove()
                
                # Add column nodes
                for column in columns:
                    column_node = node.add(f"📋 {column}")
                    column_node.data = {
                        "type": "column", 
                        "table": table_name,
                        "name": column
                    }
                    column_node.allow_expand = False
                    self._log_to_panel(f"Added column node: {column}", "DEBUG")
                    
            except Exception as e:
                self._log_to_panel(f"Error loading columns for table {table_name}: {e}", "ERROR")
                # Remove placeholder and add error node
                placeholder = node.children[0]
                placeholder.remove()
                error_node = node.add(f"❌ Error loading columns: {e}")
                error_node.data = {"type": "error"}
                error_node.allow_expand = False
        else:
            self._log_to_panel(f"Node not a table or already expanded: {node.label}", "DEBUG")
    
    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle table/column selection from tree view."""
        node = event.node
        
        if not node.data:
            return
        
        if node.data.get("type") == "table":
            # Table selected - load table data
            table_name = node.data["name"]
            if table_name != self.current_table:
                self.current_table = table_name
                self.load_table_data()
            
            # Focus on data table and update column summary
            self._focus_data_table()
            self._update_column_summary(None)  # Clear column-specific info
                
        elif node.data.get("type") == "column":
            # Column selected - load table data and highlight column
            table_name = node.data["table"]
            column_name = node.data["name"]
            
            if table_name != self.current_table:
                self.current_table = table_name
                self.load_table_data()
            
            # Focus on data table, highlight column, and update summary
            self._focus_data_table()
            self._highlight_column(column_name)
            self._update_column_summary(column_name)
    
    def load_table_data(self):
        """Load data from selected table."""
        if not self.current_table:
            return
        
        try:
            logger.info(f"Loading data from table: {self.current_table}")
            cursor = self.connection.cursor()
            
            # Properly quote the table name to prevent SQL injection
            # For Access, we use square brackets for quoting
            safe_table_name = self._quote_identifier(self.current_table)
            logger.debug(f"Using safe table name: {safe_table_name}")
            
            # Try TOP 100 for Access, fallback to LIMIT 100 for other databases
            try:
                cursor.execute(f"SELECT TOP 100 * FROM {safe_table_name}")
            except pyodbc.Error:
                cursor.execute(f"SELECT * FROM {safe_table_name} LIMIT 100")
            
            # Get column names
            columns = [column[0] for column in cursor.description]
            logger.debug(f"Columns: {columns}")
            
            # Get data
            self.current_data = cursor.fetchall()
            logger.info(f"Loaded {len(self.current_data)} rows from {self.current_table}")
            
            # Update data table
            self.update_data_table(columns)
        except Exception as e:
            logger.error(f"Error loading table data from {self.current_table}: {e}", exc_info=True)
            self.notify(f"Error loading table data: {e}", severity="error")
    
    def update_data_table(self, columns):
        """Update the data table widget with current data."""
        table = self.query_one("#data-view", DataTable)
        table.clear()
        
        # Add columns
        for col in columns:
            table.add_column(col)
        
        # Add rows
        for row in self.current_data:
            table.add_row(*[str(value) for value in row])
    
    def action_quit(self) -> None:
        """Quit the application."""
        if self.connection:
            self.connection.close()
        self.app.exit()
    
    def _log_to_panel(self, message: str, level: str = "INFO") -> None:
        """Write a message to the Textual Log widget."""
        try:
            # Use call_from_thread to ensure UI thread update
            def update_log():
                try:
                    log_widget = self.query_one("#debug-log", Log)
                    log_widget.write(f"[{level}] {message}\n")
                except Exception:
                    # Fallback if widget not available
                    if level == "INFO":
                        logger.info(message)
                    elif level == "ERROR":
                        logger.error(message)
                    elif level == "DEBUG":
                        logger.debug(message)
                    elif level == "WARNING":
                        logger.warning(message)
            self.call_from_thread(update_log)
        except Exception:
            # If all else fails (should never reach here)
            logger.error(f"Failed to log to panel: {message}")
    
    def action_return_to_tree(self) -> None:
        """Return focus to tree view (Escape key)."""
        logger.debug("Returning focus to tree view")
        tree = self.query_one("#db-tree", Tree)
        tree.focus()
    
    def action_down(self) -> None:
        """Move down (vim j)."""
        tree = self.query_one("#db-tree", Tree)
        data_table = self.query_one("#data-view", DataTable)
        
        if tree.has_focus:
            logger.debug("Moving down in tree view")
            tree.action_cursor_down()
        else:
            logger.debug("Moving down in data table")
            data_table.action_cursor_down()
    
    def action_up(self) -> None:
        """Move up (vim k)."""
        tree = self.query_one("#db-tree", Tree)
        data_table = self.query_one("#data-view", DataTable)
        
        if tree.has_focus:
            logger.debug("Moving up in tree view")
            tree.action_cursor_up()
        else:
            logger.debug("Moving up in data table")
            data_table.action_cursor_up()
    
    def action_left(self) -> None:
        """Move left/collapse (vim h)."""
        tree = self.query_one("#db-tree", Tree)
        data_table = self.query_one("#data-view", DataTable)
        
        if tree.has_focus:
            logger.debug("Collapsing node in tree view")
            cursor_node = tree.cursor_node
            # For tree view, left means collapse if expanded, otherwise move left
            if cursor_node and cursor_node.is_expanded:
                tree.action_toggle_node()
            elif cursor_node and cursor_node != tree.root:
                # Only try to move left if not on root node
                tree.action_cursor_left()
        else:
            logger.debug("Moving left in data table")
            data_table.action_cursor_left()
    
    def action_right(self) -> None:
        """Move right/expand (vim l) - expands table to show columns."""
        tree = self.query_one("#db-tree", Tree)
        data_table = self.query_one("#data-view", DataTable)
        
        if tree.has_focus:
            logger.debug("Expanding node in tree view")
            cursor_node = tree.cursor_node
            
            if cursor_node:
                # If it's a table node that's not expanded, expand it to show columns
                if (cursor_node.data and cursor_node.data.get("type") == "table" and 
                    not cursor_node.is_expanded):
                    tree.action_toggle_node()
                # For root node or if it's already a table node, just expand/collapse
                elif cursor_node == tree.root:
                    # If root is not expanded, expand it; else move cursor to first child if it exists
                    if not cursor_node.is_expanded:
                        tree.action_toggle_node()
                    elif cursor_node.children:
                        tree.cursor_line = 1  # Move to first child (root is line 0)
                        tree.refresh()
                elif cursor_node.children:
                    tree.action_cursor_right()
        else:
            logger.debug("Moving right in data table")
            data_table.action_cursor_right()
    
    def action_home(self) -> None:
        """Go to home (vim gg)."""
        tree = self.query_one("#db-tree", Tree)
        data_table = self.query_one("#data-view", DataTable)
        
        if tree.has_focus:
            logger.debug("Going to home in tree view")
            tree.action_cursor_home()
        else:
            logger.debug("Going to home in data table")
            data_table.action_cursor_home()
    
    def action_end(self) -> None:
        """Go to end (vim G)."""
        tree = self.query_one("#db-tree", Tree)
        data_table = self.query_one("#data-view", DataTable)
        
        if tree.has_focus:
            logger.debug("Going to end in tree view")
            tree.action_cursor_end()
        else:
            logger.debug("Going to end in data table")
            data_table.action_cursor_end()
    
    def _get_table_columns(self, table_name: str) -> list:
        """Get column names for a specific table."""
        if not table_name:
            logger.warning("Empty table name provided to _get_table_columns")
            return []
        
        try:
            logger.info(f"Getting columns for table: {table_name}")
            cursor = self.connection.cursor()
            # Pass the raw table name, not quoted, for pyodbc.columns()
            logger.info(f"Using raw table name for .columns(): {table_name}")
            cursor.columns(table=table_name)
            columns = []
            for row in cursor.fetchall():
                columns.append(row.column_name)
            logger.info(f"Successfully retrieved {len(columns)} columns: {columns}")
            return columns
            
        except Exception as e:
            logger.error(f"Error getting columns for table {table_name}: {e}", exc_info=True)
            raise Exception(f"Could not retrieve columns: {e}")
    
    def _focus_data_table(self) -> None:
        """Focus on the data table view."""
        try:
            data_table = self.query_one("#data-view", DataTable)
            data_table.focus()
            logger.debug("Focus set to data table")
        except Exception as e:
            logger.error(f"Error focusing data table: {e}")
    
    def _update_column_summary(self, column_name: str = None) -> None:
        """Update the column summary panel with statistics."""
        try:
            summary_label = self.query_one("#column-summary", Label)
            
            if not column_name or not self.current_table or not self.current_data:
                summary_label.update("Select a table or column to see details")
                return
            
            # Get column statistics
            stats = self._get_column_statistics(column_name)
            
            summary_text = f"📊 Column: {column_name}\n"
            summary_text += f"📋 Table: {self.current_table}\n"
            summary_text += f"📈 Rows: {stats['row_count']}\n"
            summary_text += f"🔢 Nulls: {stats['null_count']}\n"
            summary_text += f"🔡 Distinct: {stats['distinct_count']}\n"
            summary_text += f"🏷️ Type: {stats['data_type']}"
            
            summary_label.update(summary_text)
            logger.debug(f"Updated column summary for {column_name}")
            
        except Exception as e:
            logger.error(f"Error updating column summary: {e}")
            summary_label = self.query_one("#column-summary", Label)
            summary_label.update(f"Error: {e}")
    
    def _get_column_statistics(self, column_name: str) -> dict:
        """Calculate statistics for a specific column."""
        if not self.current_data or not column_name:
            return {
                'row_count': 0,
                'null_count': 0,
                'distinct_count': 0,
                'data_type': 'unknown'
            }
        
        try:
            # Get column index from the data table
            col_index = None
            try:
                data_table = self.query_one("#data-view", DataTable)
                for i, col in enumerate(data_table.columns):
                    # Compare after stripping emoji/prefix and whitespace from both sides
                    label_clean = col.label.strip()
                    target_clean = column_name.strip()
                    # Remove icons, like '📋', if present
                    if label_clean.startswith("📋"):
                        label_clean = label_clean.lstrip("📋 ").strip()
                    if label_clean == target_clean:
                        col_index = i
                        break
            except Exception as e:
                logger.debug(f"Could not get column index from DataTable: {e}")
                # Fallback: try to find column by name in the first row (if it exists)
                if self.current_data and len(self.current_data) > 0:
                    first_row = self.current_data[0]
                    for i, value in enumerate(first_row):
                        if str(value) == column_name:
                            col_index = i
                            break
            
            if col_index is None:
                logger.warning(f"Could not find column '{column_name}' in data")
                return {'row_count': 0, 'null_count': 0, 'distinct_count': 0, 'data_type': 'unknown'}
            
            # Calculate statistics
            values = []
            null_count = 0
            
            for row in self.current_data:
                value = row[col_index]
                if value is None or str(value).strip() == '':
                    null_count += 1
                else:
                    values.append(value)
            
            # Determine data type
            data_type = 'text'
            if values:
                first_val = values[0]
                if isinstance(first_val, (int, float)):
                    data_type = 'number'
                elif isinstance(first_val, bool):
                    data_type = 'boolean'
                elif hasattr(first_val, '__class__') and 'date' in str(first_val.__class__).lower():
                    data_type = 'date'
            
            return {
                'row_count': len(self.current_data),
                'null_count': null_count,
                'distinct_count': len(set(str(v) for v in values)),
                'data_type': data_type
            }
            
        except Exception as e:
            logger.error(f"Error calculating column statistics: {e}")
            return {
                'row_count': len(self.current_data) if self.current_data else 0,
                'null_count': 'N/A',
                'distinct_count': 'N/A',
                'data_type': 'unknown'
            }
    
    def _highlight_column(self, column_name: str) -> None:
        """Highlight the specified column in the data table."""
        if not column_name:
            return
        
        try:
            data_table = self.query_one("#data-view", DataTable)
            
            # Find the column index
            column_index = None
            for i, column in enumerate(data_table.columns):
                if column.label == column_name:
                    column_index = i
                    break
            
            if column_index is not None:
                logger.info(f"Highlighting column: {column_name} (index {column_index})")
                # Note: Textual DataTable doesn't have built-in column highlighting
                # We'll implement this by temporarily changing the column style
                # This is a basic implementation - could be enhanced
                self.notify(f"Column '{column_name}' selected", severity="information")
                
        except Exception as e:
            logger.error(f"Error highlighting column {column_name}: {e}")
    
    def _quote_identifier(self, identifier: str) -> str:
        """Properly quote SQL identifiers to prevent injection and handle special characters."""
        if not identifier:
            return ""
        
        # Always quote identifiers for safety
        # For Access databases, we use square brackets
        # Escape any existing brackets by doubling them
        safe_identifier = identifier.replace("]", "]]")
        
        # Always wrap in brackets for Access SQL
        return f"[{safe_identifier}]"


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
    if is_32bit and db_path.lower().endswith('.accdb'):
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
                print("No ODBC drivers found. Please install Microsoft Access Database Engine.")
        except Exception as e:
            logger.error(f"Could not check ODBC drivers: {e}")
            print("Could not check ODBC drivers. Please ensure pyodbc is installed correctly.")
        
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
