# run.py
from app import create_app

app = create_app()

def start_background_services():
    """
    Start all background threads/services.
    Called per worker process (Gunicorn or dev server).
    """
    from services.unified_data_service import start_unified_data_service
    start_unified_data_service()

# Dev server
if __name__ == "__main__":
    start_background_services()
    app.run(host="0.0.0.0", port=5001, debug=True)

# Gunicorn import: start background threads automatically per worker
else:
    start_background_services()