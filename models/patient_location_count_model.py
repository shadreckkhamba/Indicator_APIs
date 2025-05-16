from extensions.extensions import db, dt

class PatientLocationCount(db.Model):
    __tablename__ = 'patient_location_counts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    period_date = db.Column(db.DateTime, nullable=False, default=dt.utcnow, comment='Date of data snapshot')
    location = db.Column(db.String(100), nullable=False, comment='Location name (e.g. "Village A")')
    count = db.Column(db.Integer, nullable=False, default=0, comment='Patient count for this location')

    created_at = db.Column(db.DateTime, default=dt.utcnow)
    updated_at = db.Column(db.DateTime, default=dt.utcnow, onupdate=dt.utcnow)

    def __repr__(self):
        return f"<LocationCount {self.location}: {self.count} on {self.period_date}>"
    