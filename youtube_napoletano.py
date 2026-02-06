#!/usr/bin/env python3
"""Entry point for YouTube Napoletano application"""

from youtube_napoletano.app import app

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8443)
