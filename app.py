import os
import logging
import sys
from flask import Flask, request, jsonify, render_template

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')

@app.route('/')
def index():
    """Health check / Frontend page renderer."""
    return render_template('index.html')

@app.route('/download')
def download():
    """
    GET /download?url=
    API endpoint to extract video download info.
    """
    url = request.args.get('url')
    if not url:
        return jsonify({
            "success": False,
            "error": "Missing URL parameter"
        }), 400

    logger.info(f"Received download request for URL: {url}")
    
    import yt_dlp

    # Base options
    ydl_opts = {
        "quiet": True,
        "noplaylist": True,
        "socket_timeout": 15,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            }
        },
    }

    # Explicitly enable nodejs runtime for yt-dlp signature solving
    # yt-dlp 2025+ only enables deno by default, we must opt-in to nodejs
    import subprocess
    node_check = subprocess.run(["node", "--version"], capture_output=True, text=True)
    if node_check.returncode == 0:
        logger.info(f"Node.js detected: {node_check.stdout.strip()}")
        ydl_opts["js_runtimes"] = {"node": {}, "nodejs": {}}
    else:
        logger.warning("Node.js not found. YouTube signature solving may fail.")

    cookie_file = "cookies.txt"
    # Automatically write cookies.txt from environment variable if present (best practice for Render)
    cookies_b64 = os.environ.get("COOKIES_B64")
    if cookies_b64:
        import base64
        try:
            logger.info("Decoding COOKIES_B64 environment variable...")
            decoded_cookies = base64.b64decode(cookies_b64).decode('utf-8')
            with open(cookie_file, "w") as f:
                f.write(decoded_cookies)
            logger.info("Successfully created cookies.txt from environment variable.")
        except Exception as e:
            logger.error(f"Failed to decode COOKIES_B64: {str(e)}")

    # Check if URL is YouTube to apply specific bypass rules
    is_youtube = "youtube.com" in url.lower() or "youtu.be" in url.lower()

    # Use cookies.txt if available (essential for bypassing TikTok/social bot checks)
    if os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 0:
        if is_youtube:
            logger.info("YouTube URL detected. Skipping cookies.txt to allow clean android client extraction and avoid IP-mismatch block.")
        else:
            ydl_opts["cookiefile"] = cookie_file
            logger.info("Using cookies.txt for request authentication.")
    else:
        logger.warning("cookies.txt not found or is empty. Proceeding without authentication cookies.")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info without downloading the file
            info = ydl.extract_info(url, download=False)
            
            # Safe extraction of fields
            title = info.get('title', 'Video')
            thumbnail = info.get('thumbnail')
            
            # If thumbnail is not direct, look into thumbnails array
            if not thumbnail and info.get('thumbnails'):
                thumbnail = info.get('thumbnails')[-1].get('url')

            # Extract best direct URL
            video_url = None
            formats = info.get('formats', [])
            
            # 1. Look for combined format (both video and audio)
            combined = [f for f in formats if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('url')]
            if combined:
                # Sort by resolution (height) descending
                combined.sort(key=lambda f: f.get('height', 0) or 0, reverse=True)
                video_url = combined[0]['url']
            
            # 2. Look for the top-level 'url' if no combined formats are listed
            if not video_url:
                video_url = info.get('url')
                
            # 3. Fallback to any format containing a url
            if not video_url and formats:
                valid_formats = [f for f in formats if f.get('url')]
                if valid_formats:
                    # Prefer formats with video track
                    video_only = [f for f in valid_formats if f.get('vcodec') != 'none']
                    if video_only:
                        video_only.sort(key=lambda f: f.get('height', 0) or 0, reverse=True)
                        video_url = video_only[0]['url']
                    else:
                        video_url = valid_formats[0]['url']

            if not video_url:
                logger.error("Could not find a direct download URL in the video metadata.")
                return jsonify({
                    "success": False,
                    "error": "Could not extract direct video URL. The service might restrict direct downloads."
                }), 400

            logger.info(f"Successfully processed video extraction: '{title}'")
            return jsonify({
                "success": True,
                "title": title,
                "thumbnail": thumbnail,
                "url": video_url
            })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"yt-dlp extraction error: {error_msg}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Extraction failed: {error_msg}"
        }), 500

if __name__ == '__main__':
    # Default Flask local execution
    app.run(host='0.0.0.0', port=5000, debug=True)
