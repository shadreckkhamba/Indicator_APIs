import requests
from flask import jsonify
from extensions.extensions import db, logger, VIRTUAL_SERVER_ADDRESS, dt
from models.patient_age_category_model import PatientAgeCategory
from models.patient_gender_count_model import PatientGenderCount
from models.patient_location_count_model import PatientLocationCount
from models.patient_refund_count_model import PatientRefundCount

from datetime import datetime
import os

log_file = 'logs/patient_service.log'
os.makedirs(os.path.dirname(log_file), exist_ok=True)

def log_message(message):
    try:
        with open(log_file, 'a') as f:
            f.write(f"{dt.now()} - {message}\n")
    except Exception as e:
        logger.error(f"Failed to write log: {e}")

def get_patient_categories_data():
    url = f"http://{VIRTUAL_SERVER_ADDRESS}/wandikweza/get_patient_data/"
    try:
        response = requests.get(url)
        response.raise_for_status()
        log_message(f"Fetched patient categories data from {url}")
        return response.json(), 200
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request error occurred: {req_err}")
        return {"error": "Request error occurred"}, 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": "Unexpected error"}, 500

from models.patient_refund_count_model import PatientRefundCount

# ...

def save_patient_category_data():
    data, status_code = get_patient_categories_data()
    if status_code != 200:
        return jsonify({"error": "Failed to fetch patient category data"}), status_code

    age_categories = data.get("age_categories", [])
    gender_counts = data.get("gender_counts", {})
    location_counts = data.get("location_counts", [])
    total_refund_patients = data.get("total_refund_patients")

    current_date = datetime.now()

    try:
        # Clear today's existing records
        db.session.query(PatientAgeCategory).filter(
            db.func.date(PatientAgeCategory.period_date) == current_date.date()
        ).delete()
        db.session.query(PatientGenderCount).filter(
            db.func.date(PatientGenderCount.period_date) == current_date.date()
        ).delete()
        db.session.query(PatientLocationCount).filter(
            db.func.date(PatientLocationCount.period_date) == current_date.date()
        ).delete()
        db.session.query(PatientRefundCount).filter(
            db.func.date(PatientRefundCount.period_date) == current_date.date()
        ).delete()

        # Save age categories
        for item in age_categories:
            label = item.get('category')
            count = int(item.get('total', 0))
            if label:
                db.session.add(PatientAgeCategory(
                    period_date=current_date,
                    label=label,
                    count=count
                ))

        # Save gender counts
        for gender, count in gender_counts.items():
            db.session.add(PatientGenderCount(
                period_date=current_date,
                gender=gender,
                count=int(count)
            ))

        # Save location counts
        for item in location_counts:
            location = item.get('village')
            count = int(item.get('total_patients', 0))
            if location:
                db.session.add(PatientLocationCount(
                    period_date=current_date,
                    location=location,
                    count=count
                ))

        # ✅ Save refund count
        if total_refund_patients is not None:
            db.session.add(PatientRefundCount(
                period_date=current_date,
                count=int(total_refund_patients)
            ))

        db.session.commit()
        logger.info("Patient categories saved/updated successfully")
        return jsonify({"message": "Patient categories saved/updated successfully"}), 200

    except Exception as e:
        logger.exception("Error saving patient category data")
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500