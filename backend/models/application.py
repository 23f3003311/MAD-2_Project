from extensions import db
from datetime import datetime
class Application(db.Model):
    __tablename__ = "application"
    __table_args__ = (
        db.UniqueConstraint("student_id", "drive_id", name="uq_student_drive"),
    )
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("student_profile.id", ondelete="CASCADE"), nullable=False
    )
    drive_id = db.Column(
        db.Integer, db.ForeignKey("placement_drive.id", ondelete="CASCADE"), nullable=False
    )
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="applied")
    notes = db.Column(db.Text)  
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    student = db.relationship("StudentProfile", back_populates="applications")
    drive = db.relationship("PlacementDrive", back_populates="applications")
    STATUS_CHOICES = ["applied", "shortlisted", "selected", "rejected"]
    def to_dict(self, include_student=False, include_drive=False) -> dict:
        data = {
            "id": self.id,
            "student_id": self.student_id,
            "drive_id": self.drive_id,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "status": self.status,
            "notes": self.notes,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_student and self.student:
            data["student"] = self.student.to_dict(include_user=True)
        if include_drive and self.drive:
            data["drive"] = self.drive.to_dict(include_company=True)
        return data
    def __repr__(self) -> str:
        return f"<Application student={self.student_id} drive={self.drive_id} status={self.status}>"
