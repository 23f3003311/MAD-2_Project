import os
import logging
from datetime import date, timedelta
import requests
from extensions import celery
from flask_mail import Message
logger = logging.getLogger(__name__)
@celery.task(name="tasks.daily_reminder.send_daily_reminders", bind=True)
def send_daily_reminders(self):
    from extensions import db, mail
    from models import StudentProfile, PlacementDrive, Application, User
    today = date.today()
    deadline_threshold = today + timedelta(days=3)
    upcoming_drives = PlacementDrive.query.filter(
        PlacementDrive.status == "approved",
        PlacementDrive.deadline >= today,
        PlacementDrive.deadline <= deadline_threshold,
    ).all()
    if not upcoming_drives:
        logger.info("No upcoming drives in the next 3 days.")
        return {"status": "ok", "drives_found": 0}
    students = (
        StudentProfile.query.join(User, StudentProfile.user_id == User.id)
        .filter(User.is_active == True, User.is_blacklisted == False)
        .all()
    )
    sent_count = 0
    for student in students:
        user = User.query.get(student.user_id)
        if not user or not user.email:
            continue
        applied_ids = {a.drive_id for a in Application.query.filter_by(student_id=student.id).all()}
        relevant_drives = [d for d in upcoming_drives if d.id not in applied_ids]
        if not relevant_drives:
            continue
        drive_list_html = "".join([
            f"<li><strong>{d.job_title}</strong> at {d.company.company_name} — "
            f"Deadline: <span style='color:red'>{d.deadline.strftime('%d %b %Y')}</span>"
            f" | Package: {d.package or 'N/A'}</li>"
            for d in relevant_drives
        ])
        html_body = f"""
        <div style="font-family: Arial; max-width: 600px; margin: auto;">
            <div style="background: #1e40af; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h2>⏰ Placement Drive Deadline Reminder</h2>
            </div>
            <div style="background: #f8fafc; padding: 20px; border-radius: 0 0 8px 8px;">
                <p>Hi <strong>{student.full_name}</strong>,</p>
                <p>The following placement drives are closing soon. Don't miss out!</p>
                <ul style="padding-left: 20px; line-height: 2;">
                    {drive_list_html}
                </ul>
                <a href="http://localhost:5000/student/dashboard"
                   style="background:#2563eb; color:white; padding:10px 20px;
                          border-radius:6px; text-decoration:none; display:inline-block; margin-top:10px;">
                    View All Drives
                </a>
                <p style="margin-top: 20px; color: #666; font-size: 12px;">
                    — Placement Portal Application | Institute Placement Cell
                </p>
            </div>
        </div>
        """
        try:
            msg = Message(
                subject=f"⏰ Deadline Reminder: {len(relevant_drives)} drive(s) closing soon!",
                recipients=[user.email],
                html=html_body,
            )
            mail.send(msg)
            sent_count += 1
        except Exception as e:
            logger.warning(f"Email failed for {user.email}: {e}")
    _notify_google_chat(upcoming_drives)
    logger.info(f"Daily reminder: {sent_count} emails sent for {len(upcoming_drives)} drives.")
    return {"status": "ok", "emails_sent": sent_count, "drives": len(upcoming_drives)}
def _notify_google_chat(drives):
    from flask import current_app
    webhook = current_app.config.get("GOOGLE_CHAT_WEBHOOK", "")
    if not webhook:
        return
    drive_lines = "\n".join([
        f"• *{d.job_title}* ({d.company.company_name}) — Deadline: {d.deadline.strftime('%d %b %Y')}"
        for d in drives
    ])
    payload = {
        "text": f"📢 *Daily Placement Reminder*\n{len(drives)} drive(s) closing in 3 days:\n{drive_lines}"
    }
    try:
        requests.post(webhook, json=payload, timeout=5)
    except Exception as e:
        logger.warning(f"Google Chat webhook failed: {e}")
