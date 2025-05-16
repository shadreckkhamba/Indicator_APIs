from extensions.extensions import db

class PatientRefundCount(db.Model):
    __tablename__ = 'patient_refund_count'

    id = db.Column(db.Integer, primary_key=True)
    period_date = db.Column(db.DateTime, nullable=False)
    count = db.Column(db.Integer, nullable=False)