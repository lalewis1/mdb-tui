# mdb-tui

A read-only TUI application for exploring Microsoft Access databases from the command line.

## Features

- **Read-only access**: Safely explore database structure and data without risk of modification
- **Vim keybindings**: Familiar navigation with j, k, h, l, gg, G keys
- **Tree view**: Browse database tables and views in a hierarchical structure
- **Data preview**: View table contents with pagination
- **Cross-platform**: Works on Windows, Linux, and macOS (with appropriate ODBC drivers)

## Requirements

- Python 3.12+
- Microsoft Access ODBC Driver (for .mdb/.accdb files)
- uv package manager

### Windows Specific Requirements

For Windows, you need to install the appropriate Access Database Engine:

- **For Office 2010**: [Microsoft Access Database Engine 2010](https://www.microsoft.com/en-us/download/details.aspx?id=13255)
- **For Office 2016/2019/365**: [Microsoft Access Database Engine 2016](https://www.microsoft.com/en-us/download/details.aspx?id=54920)

### Important Notes About 32-bit vs 64-bit

**The application automatically detects your Python architecture and selects the appropriate driver:**

- **32-bit Python**: Uses `Microsoft Access Driver (*.mdb)` (older driver, no .accdb support)
- **64-bit Python**: Uses `Microsoft Access Driver (*.mdb, *.accdb)` (newer driver with .accdb support)

**Recommendations:**
- Use **64-bit Python** for best compatibility with both .mdb and .accdb files
- If you must use 32-bit Python, stick with .mdb files as the older driver may not support .accdb files
- Install the Access Database Engine version that matches your Python architecture (32-bit or 64-bit)

**Troubleshooting:**
- If you get driver not found errors, check your Python architecture: `python -c "import sys; print('32-bit' if sys.maxsize <= 2**32 else '64-bit')"`
- Install the corresponding version of Access Database Engine

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/mdb-tui.git
cd mdb-tui

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

## Usage

```bash
# Run with a database file
python main.py path/to/your/database.mdb

# Or use the installed command
mdb-tui path/to/your/database.accdb

# Windows example (Git Bash)
python main.py "C:/path/to/database.mdb"
```

### Debugging

If the application exits without error:

1. Check the debug log: `mdb-tui.debug.log`
2. Run with verbose logging: `python -m mdb_tui.app your_database.mdb`
3. Verify ODBC drivers are installed: `python -c "import pyodbc; print(pyodbc.drivers())"`
4. Check file permissions and path accessibility

## Keybindings

- `q`: Quit the application
- `j`: Move down (in tree or data view)
- `k`: Move up (in tree or data view)
- `h`: Move left/collapse (in tree view) or left (in data view)
- `l`: Move right/expand (in tree view) or right (in data view)
- `gg`: Go to top (home)
- `G`: Go to bottom (end)
- `/`: Search (not yet implemented)
- `Tab`: Switch focus between tree view and data table

### Enhanced Navigation Features

#### Tree View Navigation
- `j`/`k`: Move up/down between tables and columns
- `l` (right): Expand table to show column list
- `h` (left): Collapse expanded table or move to parent
- `Enter`: Select table or column
- `Tab`: Switch focus to data table

#### Data Table Navigation
- `j`/`k`: Move up/down between rows
- `h`/`l`: Move left/right between columns
- `gg`: Go to first row
- `G`: Go to last row
- `Tab`: Switch focus back to tree view

#### Advanced Features
1. **Expand Tables**: Press `l` on a table name to see its columns
2. **Column Selection**: Press `l` or `Enter` on a column name to:
   - Load the table data (if not already loaded)
   - Highlight/select the specific column
3. **Table Selection**: Press `Enter` on a table name to load its data
4. **Focus Management**: Use `Tab` to switch between tree and data views

### Example Workflow

1. **Browse Structure**: Use `j`/`k` to navigate tables
2. **Explore Table**: Press `l` to expand a table and see columns
3. **Select Column**: Press `Enter` on a column to load table and highlight column
4. **Analyze Data**: Use `Tab` to switch to data table, then `h`/`j`/`k`/`l` to navigate
5. **Switch Tables**: Use `Tab` to return to tree, select another table/column

## Navigation

1. Use arrow keys or vim keys (h,j,k,l) to navigate the tree view
2. Select a table to view its contents in the data panel
3. Use j/k to scroll through data rows
4. Press q to quit when done

## Notes

- **Security**: All table names are properly quoted and escaped to prevent SQL injection
- The application connects in read-only mode to prevent accidental modifications
- Only the first 100 rows of each table are displayed for performance
- You may need to install the appropriate ODBC driver for your operating system

## Known Limitations

1. **Column Highlighting**: Basic notification-based column selection (visual highlighting coming soon)
2. **Tree Navigation**: Uses Textual's built-in tree navigation (some advanced features may be limited)
3. **Large Databases**: May need optimization for databases with hundreds of tables

## Troubleshooting

### "AttributeError: property 'cursor_node' of 'Tree' object has no setter"
This error was fixed by using Textual's built-in tree navigation actions instead of direct cursor manipulation.

### "TypeError: TreeNode.remove() takes 1 positional argument but 2 were given"
This error was fixed by calling `node.remove()` instead of `parent.remove(child)`.

### If you encounter other issues:
1. Check `mdb-tui.debug.log` for detailed error information
2. Verify ODBC drivers are installed: `python -c "import pyodbc; print(pyodbc.drivers())"`
3. Try with a simple database file first
4. Report the issue with the debug log attached

## License

MIT