import os
import csv
import logging
from datetime import datetime
from extensions import celery
logger = logging.getLogger(__name__)
@celery.task(name="tasks.export_csv.export_student_applications", bind=True)
def export_student_applications(self, student_id: int, user_id: int):
    from flask import current_app
    from extensions import db, mail
    from models import Application, PlacementDrive, CompanyProfile, StudentProfile, User
    from flask_mail import Message
    try:
        student = StudentProfile.query.get(student_id)
        user = User.query.get(user_id)
        if not student or not user:
            raise ValueError("Student not found")
        apps = (
            Application.query.filter_by(student_id=student_id)
            .order_by(Application.applied_at.desc())
            .all()
        )
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"applications_{student.roll_number}_{timestamp}.csv"
        export_dir = current_app.config["EXPORT_FOLDER"]
        os.makedirs(export_dir, exist_ok=True)
        filepath = os.path.join(export_dir, filename)
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Application ID", "Student ID", "Student Name", "Roll Number",
                "Company Name", "Job Title", "Package", "Location",
                "Application Status", "Applied Date", "Last Updated"
            ])
            for app in apps:
                drive = app.drive
                company = drive.company if drive else None
                writer.writerow([
                    app.id,
                    student_id,
                    student.full_name,
                    student.roll_number,
                    company.company_name if company else "N/A",
                    drive.job_title if drive else "N/A",
                    drive.package if drive else "N/A",
                    drive.location if drive else "N/A",
                    app.status,
                    app.applied_at.strftime("%Y-%m-%d %H:%M") if app.applied_at else "N/A",
                    app.updated_at.strftime("%Y-%m-%d %H:%M") if app.updated_at else "N/A",
                ])
        
        # Directory/file readiness check
        import time
        for _ in range(10):
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                break
            time.sleep(0.5)
        else:
            if not os.path.exists(filepath):
                raise Exception("File was not created on disk in time.")

        logger.info(f"CSV export complete: {filename}")
        try:
            msg = Message(
                subject="✅ Your Application Export is Ready",
                recipients=[user.email],
                html=f"""
                <div style="font-family:Arial; max-width:500px; margin:auto;">
                    <div style="background:#1e40af; color:white; padding:20px; border-radius:8px 8px 0 0;">
                        <h2>✅ Export Ready</h2>
                    </div>
                    <div style="background:#f8fafc; padding:20px; border-radius:0 0 8px 8px;">
                        <p>Hi <strong>{student.full_name}</strong>,</p>
                        <p>Your application history CSV export is ready with
                           <strong>{len(apps)} application(s)</strong>.</p>
                        <p>Log in to your dashboard and click <strong>Download CSV</strong>
                           to get your file.</p>
                        <p style="margin-top:20px; color:#888; font-size:12px;">
                            — Placement Portal Application
                        </p>
                    </div>
                </div>
                """,
            )
            mail.send(msg)
        except Exception as mail_err:
            logger.warning(f"Email notification failed: {mail_err}")
        return filename
    except Exception as exc:
        logger.error(f"CSV export failed for student {student_id}: {exc}")
        raise self.retry(exc=exc, countdown=10, max_retries=2)
