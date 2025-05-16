from extensions.extensions import db, dt

class PatientAgeCategory(db.Model):
    __tablename__ = 'patient_age_categories'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    period_date = db.Column(db.DateTime, nullable=False, default=dt.utcnow, comment='Date of data snapshot')
    label = db.Column(db.String(50), nullable=False, comment='Age group label (e.g. "Under 18")')
    count = db.Column(db.Integer, nullable=False, default=0, comment='Patient count for the age group')

    created_at = db.Column(db.DateTime, default=dt.utcnow)
    updated_at = db.Column(db.DateTime, default=dt.utcnow, onupdate=dt.utcnow)

    def __repr__(self):
        return f"<AgeCategory {self.label}: {self.count} on {self.period_date}>"