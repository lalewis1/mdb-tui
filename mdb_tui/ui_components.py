"""UI components for database explorer."""

import logging
from textual.widgets import DataTable, Tree, Label, Log
from textual.app import App
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class DatabaseTreeManager:
    """Manages the database structure tree view."""

    def __init__(self, app: App):
        self.app = app
        self.tree = None
        self.tables = []

    def initialize(self) -> None:
        """Initialize tree widget."""
        self.tree = self.app.query_one("#db-tree", Tree)
        if not self.tree:
            raise Exception("Tree widget not found")

    def update_tree(self, tables: List[Dict[str, str]]) -> None:
        """Update tree with database structure."""
        self.tables = tables
        self.tree.clear()

        root = self.tree.root
        root.label = self.app.db_path
        root.allow_expand = True

        for table_info in tables:
            table_name = table_info["name"]
            table_type = table_info.get("type", "TABLE")
            
            # Use different display for VIEW vs TABLE
            display_name = table_name
            if table_type == "VIEW":
                display_name = f"👁️  {display_name}"
            
            table_node = root.add(display_name)
            table_node.data = {"type": "table", "name": table_name, "table_type": table_type}
            table_node.allow_expand = True

            # Add placeholder child
            placeholder = table_node.add("Loading columns...")
            placeholder.data = {"type": "placeholder"}

    def expand_table_node(self, table_name: str, columns: List[str]) -> None:
        """Expand a table node to show its columns."""
        if not self.tree:
            return

        # Find the table node
        table_node = None
        for child in self.tree.root.children:
            if (
                child.data
                and child.data.get("type") == "table"
                and child.data.get("name") == table_name
            ):
                table_node = child
                break

        if not table_node:
            return

        # Remove placeholder
        if (
            table_node.children
            and table_node.children[0].data.get("type") == "placeholder"
        ):
            table_node.children[0].remove()

        # Add column nodes
        for column in columns:
            column_node = table_node.add(f"📋 {column}")
            column_node.data = {"type": "column", "table": table_name, "name": column}
            column_node.allow_expand = False

    def handle_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """Handle table expansion to load columns."""
        node = event.node

        if (
            node.data
            and node.data.get("type") == "table"
            and node.children
            and node.children[0].data.get("type") == "placeholder"
        ):

            table_name = node.data["name"]
            logger.info(f"Loading columns for table: {table_name}")

            try:
                columns = self.app.db_manager.get_table_columns(table_name)
                self.expand_table_node(table_name, columns)

            except Exception as e:
                logger.error(f"Error loading columns for table {table_name}: {e}")
                # Remove placeholder and add error node
                if node.children and node.children[0].data.get("type") == "placeholder":
                    node.children[0].remove()

                error_node = node.add(f"❌ Error loading columns: {e}")
                error_node.data = {"type": "error"}
                error_node.allow_expand = False


class DataTableManager:
    """Manages the data table view."""

    def __init__(self, app: App):
        self.app = app
        self.table = None
        self.current_table = None
        self.current_data = []
        self.current_columns = []

    def initialize(self) -> None:
        """Initialize data table widget."""
        self.table = self.app.query_one("#data-view", DataTable)
        if not self.table:
            raise Exception("DataTable widget not found")

    def load_table_data(self, table_name: str) -> None:
        """Load data from specified table."""
        if table_name == self.current_table:
            return

        try:
            logger.info(f"Loading data from table: {table_name}")
            result = self.app.db_manager.get_table_data(table_name)

            self.current_table = table_name
            self.current_columns = result["columns"]
            self.current_data = result["data"]

            # Update SQL panel
            self._update_sql_panel(result["sql"])

            # Update data table
            self.update_data_table()

        except Exception as e:
            logger.error(f"Error loading table data: {e}")
            self.app.notify(f"Error loading table data: {e}", severity="error")

    def update_data_table(self) -> None:
        """Update the data table with current data."""
        if not self.table:
            return

        # Remove all columns to ensure clean state
        for column in list(self.table.columns):
            self.table.remove_column(column)
        
        self.table.clear()

        # Add columns
        for col in self.current_columns:
            self.table.add_column(col)

        # Add rows
        for row in self.current_data:
            self.table.add_row(*[str(value) for value in row])

    def highlight_column(self, column_name: str) -> None:
        """Highlight specified column in data table."""
        if not column_name or not self.table:
            return

        try:
            # Strip the 📋 prefix if present (from tree view)
            clean_column_name = column_name.strip().lstrip("📋").strip()

            # Find column index
            column_index = None
            for i, column in enumerate(self.table.columns):
                if column.label == clean_column_name:
                    column_index = i
                    break

            if column_index is not None:
                logger.info(
                    f"Highlighting column: {clean_column_name} (index {column_index})"
                )
                self.app.notify(
                    f"Column '{clean_column_name}' selected", severity="info"
                )
                # Scroll to make the column visible
                if hasattr(self.table, 'cursor_column'):
                    self.table.cursor_column = column_index

        except Exception as e:
            logger.error(f"Error highlighting column {column_name}: {e}")

    def focus(self) -> None:
        """Focus on data table."""
        if self.table:
            self.table.focus()
            self.table.remove_class("unfocused-datatable")

    def _update_sql_panel(self, sql: str) -> None:
        """Update SQL panel with query."""
        try:
            sql_panel = self.app.query_one("#sql-panel", Label)
            sql_panel.update(f"SQL: {sql}")
        except Exception as e:
            logger.debug(f"Failed to update SQL panel: {e}")


class StatusManager:
    """Manages status and summary displays."""

    def __init__(self, app: App):
        self.app = app

    def update_column_summary(
        self,
        column_name: str = None,
        table_name: str = None,
        stats: Dict[str, Any] = None,
    ) -> None:
        """Update column summary panel."""
        try:
            summary_label = self.app.query_one("#column-summary", Label)

            if not column_name or not table_name or not stats:
                summary_label.update("")
                return

            summary_text = f"📊 Column: {column_name}\n"
            summary_text += f"📋 Table: {table_name}\n"
            summary_text += f"📈 Rows: {stats['row_count']}\n"
            summary_text += f"🔢 Nulls: {stats['null_count']}\n"
            summary_text += f"🔡 Distinct: {stats['distinct_count']}\n"
            summary_text += f"🏷️ Type: {stats['data_type']}"

            summary_label.update(summary_text)

        except Exception as e:
            logger.error(f"Error updating column summary: {e}")

    def update_sql_panel(self, sql: str, additional_sql: str = None) -> None:
        """Update SQL panel."""
        try:
            sql_panel = self.app.query_one("#sql-panel", Label)

            if additional_sql:
                sql_panel.update(f"Stats SQL: {sql}\nColumns SQL: {additional_sql}")
            else:
                sql_panel.update(f"SQL: {sql}")

        except Exception as e:
            logger.debug(f"Failed to update SQL panel: {e}")


class LoggerManager:
    """Manages logging to UI panel."""

    def __init__(self, app: App):
        self.app = app

    def log_to_panel(self, message: str, level: str = "INFO") -> None:
        """Write message to log widget."""
        try:

            def update_log():
                try:
                    log_widget = self.app.query_one("#debug-log", Log)
                    log_widget.write(f"[{level}] {message}\n")
                except Exception:
                    self._fallback_logging(message, level)

            self.app.call_from_thread(update_log)

        except Exception:
            self._fallback_logging(message, level)

    def _fallback_logging(self, message: str, level: str) -> None:
        """Fallback logging when UI logging fails."""
        if level == "INFO":
            logger.info(message)
        elif level == "ERROR":
            logger.error(message)
        elif level == "DEBUG":
            logger.debug(message)
        elif level == "WARNING":
            logger.warning(message)
