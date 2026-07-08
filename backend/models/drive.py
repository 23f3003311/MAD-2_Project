import json
from extensions import db
from datetime import datetime
class PlacementDrive(db.Model):
    __tablename__ = "placement_drive"
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company_profile.id", ondelete="CASCADE"), nullable=False)
    job_title = db.Column(db.String(200), nullable=False)
    job_description = db.Column(db.Text, nullable=False)
    eligible_branches = db.Column(db.Text, default="[]")  
    min_cgpa = db.Column(db.Float, default=0.0)
    eligible_year = db.Column(db.Integer)  
    package = db.Column(db.String(100))   
    location = db.Column(db.String(200))
    job_type = db.Column(db.String(50), default="Full-time")  
    deadline = db.Column(db.Date, nullable=False)
    interview_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="pending")  
    rejection_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    company = db.relationship("CompanyProfile", back_populates="drives")
    applications = db.relationship(
        "Application", back_populates="drive", cascade="all, delete-orphan"
    )
    def get_eligible_branches(self) -> list:
        try:
            return json.loads(self.eligible_branches) if self.eligible_branches else []
        except (json.JSONDecodeError, TypeError):
            return []
    def set_eligible_branches(self, branches: list) -> None:
        self.eligible_branches = json.dumps(branches)
    def to_dict(self, include_company=False) -> dict:
        data = {
            "id": self.id,
            "company_id": self.company_id,
            "job_title": self.job_title,
            "job_description": self.job_description,
            "eligible_branches": self.get_eligible_branches(),
            "min_cgpa": self.min_cgpa,
            "eligible_year": self.eligible_year,
            "package": self.package,
            "location": self.location,
            "job_type": self.job_type,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "interview_date": self.interview_date.isoformat() if self.interview_date else None,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "applicant_count": len(self.applications) if self.applications else 0,
        }
        if include_company and self.company:
            data["company_name"] = self.company.company_name
            data["company_logo"] = None 
        return data
    def __repr__(self) -> str:
        return f"<PlacementDrive {self.job_title} by company {self.company_id}>"
