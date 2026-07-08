from extensions import db
from datetime import datetime
class CompanyProfile(db.Model):
    __tablename__ = "company_profile"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False)
    company_name = db.Column(db.String(200), nullable=False)
    hr_contact = db.Column(db.String(100))
    hr_email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    website = db.Column(db.String(300))
    description = db.Column(db.Text)
    industry = db.Column(db.String(100))
    headquarters = db.Column(db.String(200))
    founded_year = db.Column(db.Integer)
    approval_status = db.Column(db.String(20), default="pending")  
    rejection_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = db.relationship("User", back_populates="company_profile")
    drives = db.relationship(
        "PlacementDrive", back_populates="company", cascade="all, delete-orphan"
    )
    def to_dict(self, include_user=False) -> dict:
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "company_name": self.company_name,
            "hr_contact": self.hr_contact,
            "hr_email": self.hr_email,
            "phone": self.phone,
            "website": self.website,
            "description": self.description,
            "industry": self.industry,
            "headquarters": self.headquarters,
            "founded_year": self.founded_year,
            "approval_status": self.approval_status,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "total_drives": len(self.drives) if self.drives else 0,
        }
        if include_user and self.user:
            data["email"] = self.user.email
            data["is_active"] = self.user.is_active
            data["is_blacklisted"] = self.user.is_blacklisted
        return data
    def __repr__(self) -> str:
        return f"<CompanyProfile {self.company_name}>"
