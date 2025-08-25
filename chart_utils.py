import os
import logging
from flask import session
from auth import Chart, db

GRAPH_FOLDER = os.path.join("static", "graphs")

def save_chart_metadata(filename, limit=3):
    """Save a new chart to DB and keep only the latest `limit` per user."""
    user_id = session.get("user_id")
    if not user_id:
        logging.warning("Chart saved but no user_id in session!")
        return

    # Add new chart
    new_chart = Chart(user_id=user_id, filename=filename)
    db.session.add(new_chart)
    db.session.commit()

    # Cleanup: keep only latest 3 charts of this user
    charts = Chart.query.filter_by(user_id=user_id)\
                        .order_by(Chart.created_at.desc()).all()
    for old in charts[limit:]:
        try:
            os.remove(os.path.join(GRAPH_FOLDER, old.filename))
            logging.info(f"Deleted old chart {old.filename}")
        except Exception as e:
            logging.warning(f"Could not delete old chart {old.filename}: {e}")
        db.session.delete(old)
    db.session.commit()