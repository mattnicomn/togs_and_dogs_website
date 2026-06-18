import sys
import os

# Set required environment variables before any backend code is imported
os.environ.setdefault('DATA_TABLE_NAME', 'test-table')

# Add src/backend to sys.path so handlers and common can be imported
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src/backend'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

