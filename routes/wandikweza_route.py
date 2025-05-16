from flask import Blueprint
from services.patient_categories_service import save_patient_category_data

wandikweza_bp = Blueprint('wandikweza', __name__)

@wandikweza_bp.route('/save_patient_data', methods=['GET'])
def save_patient_category_data_route():
    return save_patient_category_data()