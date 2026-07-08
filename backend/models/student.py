from extensions import db
from datetime import datetime
class StudentProfile(db.Model):
    __tablename__ = "student_profile"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    roll_number = db.Column(db.String(50), unique=True, nullable=False)
    branch = db.Column(db.String(100), nullable=False)
    cgpa = db.Column(db.Float, nullable=False, default=0.0)
    year = db.Column(db.Integer, nullable=False)  
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    linkedin = db.Column(db.String(300))
    github = db.Column(db.String(300))
    skills = db.Column(db.Text) 
    resume_path = db.Column(db.String(500))
    resume_filename = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = db.relationship("User", back_populates="student_profile")
    applications = db.relationship(
        "Application", back_populates="student", cascade="all, delete-orphan"
    )
    def to_dict(self, include_user=False) -> dict:
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "full_name": self.full_name,
            "roll_number": self.roll_number,
            "branch": self.branch,
            "cgpa": self.cgpa,
            "year": self.year,
            "phone": self.phone,
            "address": self.address,
            "linkedin": self.linkedin,
            "github": self.github,
            "skills": self.skills,
            "resume_filename": self.resume_filename,
            "has_resume": bool(self.resume_path),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_user and self.user:
            data["email"] = self.user.email
            data["is_active"] = self.user.is_active
            data["is_blacklisted"] = self.user.is_blacklisted
        return data
    def __repr__(self) -> str:
        return f"<StudentProfile {self.full_name} ({self.roll_number})>"
