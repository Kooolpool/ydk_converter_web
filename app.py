from collections import Counter
from flask import Flask, request, render_template, send_file, after_this_request
import json
import os

import requests
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024  # Limit upload size to 1MB
app.config['UPLOAD_FOLDER'] = 'downloads'  # Store files in a downloads folder
app.secret_key = os.urandom(24)  # Required for session management

# Create downloads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Load card database once
try:
    with open('cardinfo.json', 'r', encoding='utf-8') as f:
        card_data = json.load(f)
    
    # Create ID → name mapping
    id_to_name = {str(card["id"]): card["name"] for card in card_data["data"]}
    logger.info(f"Successfully loaded {len(id_to_name)} cards from database")
except Exception as e:
    logger.error(f"Failed to load card database: {str(e)}")
    id_to_name = {}

def card_info_json(card_id: str):
    """Fetch card information from the YGOProDeck API."""
    try:
        response = requests.get(
            f"https://db.ygoprodeck.com/api/v7/cardinfo.php?id={card_id}",
            timeout=10 # Set a timeout for the request
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"API request failed for card ID {card_id}: {str(e)}")
        raise

def allowed_file(filename):
    """Check if the uploaded file has a .ydk extension."""
    return filename and filename.lower().endswith('.ydk')

def convert_ydk_to_text(file_stream):
    """Convert a YDK file to human-readable text format."""
    deck_sections = {"main": [], "extra": [], "side": []}
    current_section = None
    
    try:
        # First pass: collect all card IDs in their respective sections
        content = file_stream.read().decode('utf-8')
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith("#created"):
                continue
            if line == "#main":
                current_section = "main"
            elif line == "#extra":
                current_section = "extra"
            elif line == "!side":
                current_section = "side"
            elif line.isdigit() and current_section:
                name = id_to_name.get(line)
            # If name is not found, try fetching from API
                if name is None:
                    try:
                        api_data = card_info_json(line)
                        name = api_data["data"][0]["name"]
                        id_to_name[line] = name  # Cache for future lookups
                    except Exception as e:
                        name = f"Unknown Card ({line})"
                deck_sections[current_section].append(name)

        # Second pass: count cards and build output
        output = []
        for section_name in ["Main", "Extra", "Side"]:
            
            output.append(f"\n{section_name} Deck:")
            section_cards = deck_sections[section_name.lower()]
            card_counts = Counter(section_cards)
            for card_name in sorted(card_counts.keys()):
                count = card_counts[card_name]
                output.append(f"  {card_name} x{count}")
            
            # Add spacing between sections
            output.append("")
        
        return "\n".join(output).strip()

    except Exception as e:
        logger.error(f"Error converting YDK file: {str(e)}")
        raise ValueError("Invalid YDK file format")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html")

    # Check if a file was uploaded
    if "ydk_file" not in request.files:
        return render_template("index.html", error="No file uploaded.")
    
    ydk_file = request.files["ydk_file"]
    
    # Check if a file was selected
    if ydk_file.filename == "":
        return render_template("index.html", error="No file selected.")
        
    # Validate file extension
    if not allowed_file(ydk_file.filename):
        return render_template("index.html", error="Only .ydk files are allowed.")
        
    try:
        # Convert the deck
        readable_text = convert_ydk_to_text(ydk_file)
        
        # Create a unique filename based on timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"deck_{timestamp}.txt"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Save the file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(readable_text)
            
        logger.info(f"Successfully converted deck file: {ydk_file.filename}")
        return render_template("result.html", text=readable_text, download_path=filename)
        
    except Exception as e:
        logger.error(f"Error processing file {ydk_file.filename}: {str(e)}")
        return render_template("index.html", error="Error processing the deck file. Please try again.")

@app.route("/download/<filename>")
def download(filename):
    """Handle file downloads with proper error handling."""
    try:
        # Security check: ensure the filename is safe
        if '..' in filename or filename.startswith('/'):
            logger.error(f"Invalid filename requested: {filename}")
            return "Access denied", 403
            
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(filepath):
            logger.error(f"Download file not found: {filepath}")
            return "File not found", 404
            
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain'
        )
    except Exception as e:
        logger.error(f"Error downloading file {filename}: {str(e)}")
        return "Error downloading file", 500

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file size exceeding the limit."""
    return render_template("index.html", error="File too large. Maximum size is 1MB."), 413

@app.errorhandler(500)
def internal_server_error(error):
    """Handle internal server errors."""
    logger.error(f"Internal server error: {str(error)}")
    return render_template("index.html", error="An internal error occurred. Please try again."), 500

if __name__ == "__main__":
    # Create log directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Start the application
    logger.info("Starting application...")
    app.run(host='0.0.0.0', port=5000)
