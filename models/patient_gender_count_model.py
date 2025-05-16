from extensions.extensions import db, dt

class PatientGenderCount(db.Model):
    __tablename__ = 'patient_gender_counts'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    period_date = db.Column(db.DateTime, nullable=False, default=dt.utcnow)
    gender = db.Column(db.String(10), nullable=False)
    count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=dt.utcnow)
    updated_at = db.Column(db.DateTime, default=dt.utcnow, onupdate=dt.utcnow)