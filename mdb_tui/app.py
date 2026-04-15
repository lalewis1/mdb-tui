"""Main TUI application for exploring Access databases."""

import pyodbc
from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.widgets import Header, Footer, Tree, DataTable, Input, Label
from textual.binding import Binding


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
            self.connect_to_database()
            self.load_database_structure()
            self.update_tree_view()
        except Exception as e:
            self.app.exit(f"Error connecting to database: {e}")
    
    def connect_to_database(self):
        """Establish connection to Access database."""
        connection_string = (
            r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
            r"DBQ=" + self.db_path + ";"
            r"ReadOnly=True;"
        )
        self.connection = pyodbc.connect(connection_string)
    
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
            table_node.data = table
    
    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle table selection from tree view."""
        node = event.node
        if node.data and node.data != self.current_table:
            self.current_table = node.data
            self.load_table_data()
    
    def load_table_data(self):
        """Load data from selected table."""
        if not self.current_table:
            return
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"SELECT TOP 100 * FROM {self.current_table}")
            
            # Get column names
            columns = [column[0] for column in cursor.description]
            
            # Get data
            self.current_data = cursor.fetchall()
            
            # Update data table
            self.update_data_table(columns)
        except Exception as e:
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
    
    def action_down(self) -> None:
        """Move down (vim j)."""
        tree = self.query_one("#db-tree", Tree)
        if tree.has_focus:
            tree.action_cursor_down()
        else:
            data_table = self.query_one("#data-view", DataTable)
            data_table.action_cursor_down()
    
    def action_up(self) -> None:
        """Move up (vim k)."""
        tree = self.query_one("#db-tree", Tree)
        if tree.has_focus:
            tree.action_cursor_up()
        else:
            data_table = self.query_one("#data-view", DataTable)
            data_table.action_cursor_up()
    
    def action_left(self) -> None:
        """Move left (vim h)."""
        tree = self.query_one("#db-tree", Tree)
        if tree.has_focus:
            tree.action_cursor_left()
    
    def action_right(self) -> None:
        """Move right (vim l)."""
        tree = self.query_one("#db-tree", Tree)
        if tree.has_focus:
            tree.action_cursor_right()


def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: mdb-tui <database_path>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    app = DatabaseExplorer(db_path)
    app.run()


if __name__ == "__main__":
    main()