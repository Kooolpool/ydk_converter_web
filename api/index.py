# api/index.py
import os
import sys
from flask import Flask

# Add the parent directory to the path so we can import our app
current_dir = os.path.dirname(__file__)
parent_dir = os.path.join(current_dir, '..')
sys.path.insert(0, parent_dir)

# Import your existing Flask app
try:
    from app import app
except ImportError:
    # Fallback if import fails
    app = Flask(__name__)
    
    @app.route('/')
    def hello():
        return "YDK Converter is loading..."

# Export the app for Vercel
app = app