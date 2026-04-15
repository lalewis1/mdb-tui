"""Main TUI application for exploring Access databases."""

import pyodbc
import logging
import sys
import os
from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.widgets import Header, Footer, Tree, DataTable, Input, Label
from textual.binding import Binding

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mdb-tui.debug.log'),
        logging.StreamHandler()
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
        Binding("tab", "switch_focus", "Switch Focus", show=False),
    ]
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
        self.tables = []
        self.current_table = None
        self.current_data = []
        super().__init__()
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Container(
            Label("Database Explorer", id="title"),
            Tree("Database Structure", id="db-tree"),
            ScrollableContainer(
                DataTable(id="data-view"),
                id="data-container"
            ),
            id="main-container"
        )
        yield Footer()
    
    def on_mount(self) -> None:
        """Connect to database and load structure when app starts."""
        try:
            logger.info(f"Starting mdb-tui with database: {self.db_path}")
            logger.info(f"Current working directory: {os.getcwd()}")
            logger.info(f"Database file exists: {os.path.exists(self.db_path)}")
            
            # Check for .accdb files with 32-bit Python
            is_32bit = sys.maxsize <= 2**32
            if is_32bit and self.db_path.lower().endswith('.accdb'):
                logger.warning("32-bit Python detected with .accdb file - may not work with older drivers")
                self.notify("Warning: 32-bit Python with .accdb file may have limited compatibility", severity="warning")
            
            self.connect_to_database()
            self.load_database_structure()
            self.update_tree_view()
            
            # Set initial focus to tree view
            tree = self.query_one("#db-tree", Tree)
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
        
        # Check if this is a table node being expanded
        if (node.data and node.data.get("type") == "table" and 
            node.children and node.children[0].data.get("type") == "placeholder"):
            
            table_name = node.data["name"]
            logger.info(f"Loading columns for table: {table_name}")
            
            try:
                columns = self._get_table_columns(table_name)
                
                # Remove the placeholder
                node.remove(node.children[0])
                
                # Add column nodes
                for column in columns:
                    column_node = node.add(f"📋 {column}")
                    column_node.data = {
                        "type": "column", 
                        "table": table_name,
                        "name": column
                    }
                    column_node.allow_expand = False
                    
            except Exception as e:
                logger.error(f"Error loading columns for table {table_name}: {e}")
                # Remove placeholder and add error node
                node.remove(node.children[0])
                error_node = node.add(f"❌ Error loading columns: {e}")
                error_node.data = {"type": "error"}
                error_node.allow_expand = False
    
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
                
        elif node.data.get("type") == "column":
            # Column selected - load table data and highlight column
            table_name = node.data["table"]
            column_name = node.data["name"]
            
            if table_name != self.current_table:
                self.current_table = table_name
                self.load_table_data()
            
            # Highlight the selected column in the data table
            self._highlight_column(column_name)
    
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
    
    def action_switch_focus(self) -> None:
        """Switch focus between tree view and data table."""
        tree = self.query_one("#db-tree", Tree)
        data_table = self.query_one("#data-view", DataTable)
        
        if tree.has_focus:
            logger.debug("Switching focus from tree to data table")
            data_table.focus()
        else:
            logger.debug("Switching focus from data table to tree")
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
            # For tree view, left means collapse the current node
            if tree.cursor_node and tree.cursor_node.is_expanded:
                tree.action_toggle_node()
            else:
                # If node is already collapsed, move to parent
                if tree.cursor_node and tree.cursor_node.parent:
                    tree.cursor_node = tree.cursor_node.parent
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
                # If it's a table node, expand it to show columns
                if (cursor_node.data and cursor_node.data.get("type") == "table" and 
                    not cursor_node.is_expanded):
                    tree.action_toggle_node()
                # If it's already expanded and has children, move to first child
                elif cursor_node.children:
                    tree.cursor_node = cursor_node.children[0]
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
            return []
        
        try:
            cursor = self.connection.cursor()
            safe_table_name = self._quote_identifier(table_name)
            
            # Get column information from the table
            cursor.columns(table=safe_table_name)
            columns = []
            for row in cursor.fetchall():
                columns.append(row.column_name)
            
            return columns
            
        except Exception as e:
            logger.error(f"Error getting columns for table {table_name}: {e}")
            raise Exception(f"Could not retrieve columns: {e}")
    
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