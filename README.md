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
```

## Keybindings

- `q`: Quit the application
- `j`: Move down (in tree or data view)
- `k`: Move up (in tree or data view)
- `h`: Move left/collapse (in tree view)
- `l`: Move right/expand (in tree view)
- `gg`: Go to top
- `G`: Go to bottom
- `/`: Search (not yet implemented)

## Navigation

1. Use arrow keys or vim keys (h,j,k,l) to navigate the tree view
2. Select a table to view its contents in the data panel
3. Use j/k to scroll through data rows
4. Press q to quit when done

## Notes

- The application connects in read-only mode to prevent accidental modifications
- Only the first 100 rows of each table are displayed for performance
- You may need to install the appropriate ODBC driver for your operating system

## License

MIT