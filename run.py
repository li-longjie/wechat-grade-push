from app import app
import logging
from config import LOGGING_CONFIG

if __name__ == "__main__":
    logging.basicConfig(**LOGGING_CONFIG)
    app.run(host='0.0.0.0', port=5000) 