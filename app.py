from flask import Flask, render_template, request, send_file, flash, redirect, url_for
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import img2pdf
import validators
import os
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

app = Flask(__name__)
# ApiFlash API configuration
API_KEY = os.getenv("APIFLASH_API_KEY")
BASE_URL = "https://api.apiflash.com/v1/urltoimage"
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# Default save location (user's Downloads folder)
DEFAULT_SAVE_PATH = str(Path.home() / "Downloads" / "Screenshots")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url")
        device = request.form.get("device")
        format_type = request.form.get("format")
        custom_width = request.form.get("width")
        custom_height = request.form.get("height")
        save_path = request.form.get("savepath")  # This should be the full path

        #  Validation
        if not url or not validators.url(url):
            flash(" Please enter a valid website URL.", "error")
            return redirect(url_for("index"))

        if not save_path:
            flash(" Please enter a save path before capturing the screenshot.", "error")
            return redirect(url_for("index"))

        # Use the provided path directly - normalize it and handle different formats
        save_path = save_path.strip()
        
        # Handle tilde expansion for home directory (e.g., ~/Downloads)
        if save_path.startswith('~'):
            save_path = os.path.expanduser(save_path)
        
        # Normalize the path (handles forward/backward slashes, .., etc.)
        save_path = os.path.normpath(save_path)
        
        # Convert to absolute path if it's relative
        if not os.path.isabs(save_path):
            # If it's just a folder name (no slashes), search for it in common locations
            if os.sep not in save_path and '/' not in save_path:
                # Just a folder name - try to find it in common locations
                folder_name = save_path
                save_path = None
                
                # Common locations to search (Windows)
                home = Path.home()
                search_locations = [
                    home,  # User's home directory
                    home / "Downloads",  # Downloads
                    home / "Desktop",  # Desktop
                    home / "Documents",  # Documents
                    Path("D:\\"),  # D drive root
                    Path("C:\\Users"),  # Users folder
                ]
                
                # Also check other drives if on Windows
                if os.name == 'nt':  # Windows
                    import string
                    for drive in string.ascii_uppercase:
                        drive_path = Path(f"{drive}:\\")
                        if drive_path.exists():
                            search_locations.append(drive_path)
                
                # Search for folder with this name (only direct children, not recursive)
                for location in search_locations:
                    if location.exists():
                        try:
                            potential_path = location / folder_name
                            if potential_path.exists() and potential_path.is_dir():
                                save_path = str(potential_path)
                                print(f" Found folder '{folder_name}' at: {save_path}")
                                break
                        except (PermissionError, OSError):
                            # Skip locations we can't access
                            continue
                
                # If not found, create it in user's home directory
                if save_path is None:
                    save_path = os.path.join(home, folder_name)
                    print(f" Folder '{folder_name}' not found in common locations. Will create at: {save_path}")
            else:
                # Relative path with slashes - join with home directory
                save_path = os.path.join(Path.home(), save_path)
            save_path = os.path.normpath(save_path)
        
        # If path is absolute, use it as-is
        print(f" Save path resolved to: {save_path}")
        
        if device == "custom":
            if not (custom_width and custom_height and custom_width.isdigit() and custom_height.isdigit()):
                flash(" Please enter valid numeric values for custom resolution.", "error")
                return redirect(url_for("index"))

        #  Predefined resolutions
        resolutions = {
            "mobile": (375, 812),
            "laptop": (1366, 768),
            "desktop": (1920, 1080),
        }

        width, height = resolutions.get(device, (1366, 768))
        if device == "custom":
            width, height = int(custom_width), int(custom_height)

        #  API Request to ApiFlash
        params = {
            "access_key": API_KEY,
            "url": url,
            "wait_until": "page_loaded",
            "fresh": True,
            "width": width,
            "height": height,
            "format": "png",
            "response_type": "image"
        }

        try:
            res = requests.get(BASE_URL, params=params, timeout=30)
        except requests.exceptions.RequestException as e:
            flash(f" Network error: {str(e)}", "error")
            return redirect(url_for("index"))

        if res.status_code != 200:
            flash("Screenshot failed! Check API key or URL.", "error")
            return redirect(url_for("index"))

        # Open screenshot
        img = Image.open(BytesIO(res.content))
        draw = ImageDraw.Draw(img)
        
        # Use a better font if available, fallback to default
        try:
            font = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()

        # Add watermark + timestamp + copyright
        watermark = "@soupDeVeLops"
        copyright_text = "© 2025 Screenshot Pro App"
        time_stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Get text sizes using getbbox (textsize is deprecated)
        try:
            wm_bbox = draw.textbbox((0, 0), watermark, font=font)
            wm_w, wm_h = wm_bbox[2] - wm_bbox[0], wm_bbox[3] - wm_bbox[1]
        except:
            wm_w, wm_h = 100, 15  # Fallback values

        # Draw text with shadow for better visibility
        shadow_color = (0, 0, 0)
        text_color = (255, 255, 255)
        
        # Watermark (bottom right)
        draw.text((img.width - wm_w - 14, img.height - wm_h - 14), watermark, fill=shadow_color, font=font)
        draw.text((img.width - wm_w - 15, img.height - wm_h - 15), watermark, fill=text_color, font=font)
        
        # Timestamp (bottom left)
        draw.text((11, img.height - wm_h - 14), time_stamp, fill=shadow_color, font=font)
        draw.text((10, img.height - wm_h - 15), time_stamp, fill=text_color, font=font)
        
        # Copyright (top left)
        draw.text((11, 11), copyright_text, fill=shadow_color, font=font)
        draw.text((10, 10), copyright_text, fill=text_color, font=font)

        # Export to selected format
        img_bytes = BytesIO()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if format_type == "png":
            filename = f"screenshot_{timestamp}.png"
            mime = "image/png"
            img.save(img_bytes, "PNG")
        elif format_type == "jpg":
            filename = f"screenshot_{timestamp}.jpg"
            mime = "image/jpeg"
            img.save(img_bytes, "JPEG")
        elif format_type == "pdf":
            img_bytes_png = BytesIO()
            img.save(img_bytes_png, "PNG")
            img_bytes_png.seek(0)
            img_bytes = BytesIO(img2pdf.convert(img_bytes_png.getvalue()))
            filename = f"screenshot_{timestamp}.pdf"
            mime = "application/pdf"
        else:
            filename = f"screenshot_{timestamp}.png"
            mime = "image/png"
            img.save(img_bytes, "PNG")

        img_bytes.seek(0)

        #  Save locally to user's chosen path
        try:
            # Create directory if it doesn't exist
            os.makedirs(save_path, exist_ok=True)
            save_full_path = os.path.join(save_path, filename)

            # Save the file locally
            with open(save_full_path, "wb") as f:
                f.write(img_bytes.getvalue())

            print(f" Screenshot saved locally at: {save_full_path}")
            
            # Flash success message
            flash(f" Screenshot saved successfully to {save_full_path}!", "success")
            
        except PermissionError:
            flash(f" Permission denied! Cannot write to: {save_path}", "error")
            return redirect(url_for("index"))
        except Exception as e:
            flash(f" Could not save file: {str(e)}", "error")
            return redirect(url_for("index"))

        # Send file to browser as download too
        img_bytes.seek(0)
        return send_file(img_bytes, as_attachment=True, download_name=filename, mimetype=mime)

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)