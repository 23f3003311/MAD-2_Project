import json
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt
from functools import wraps
from datetime import date, datetime
from extensions import db, cache
from models import CompanyProfile, PlacementDrive, Application, StudentProfile, User
company_bp = Blueprint("company", __name__, url_prefix="/api/company")
def _ok(data=None, msg="", status=200):
    return jsonify({"success": True, "data": data, "message": msg}), status
def _err(msg, status=400):
    return jsonify({"success": False, "message": msg}), status
def company_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get("role") != "company":
            return _err("Company access required.", 403)
        return fn(*args, **kwargs)
    return wrapper
def _get_company_profile():
    claims = get_jwt()
    user_id = int(claims.get("user_id"))
    return CompanyProfile.query.filter_by(user_id=user_id).first()
@company_bp.route("/profile", methods=["GET"])
@company_required
def get_profile():
    company = _get_company_profile()
    if not company:
        return _err("Company profile not found.", 404)
    return _ok(company.to_dict(include_user=True))
@company_bp.route("/profile", methods=["PUT"])
@company_required
def update_profile():
    company = _get_company_profile()
    if not company:
        return _err("Company profile not found.", 404)
    body = request.get_json(silent=True) or {}
    updatable = [
        "hr_contact", "hr_email", "phone", "website",
        "description", "industry", "headquarters", "founded_year"
    ]
    for field in updatable:
        if field in body:
            setattr(company, field, body[field])
    db.session.commit()
    cache.delete("admin:stats")
    return _ok(company.to_dict(include_user=True), msg="Profile updated.")
@company_bp.route("/dashboard", methods=["GET"])
@company_required
def dashboard():
    company = _get_company_profile()
    if not company:
        return _err("Profile not found.", 404)
    drives = PlacementDrive.query.filter_by(company_id=company.id).all()
    drive_stats = []
    for drive in drives:
        apps = Application.query.filter_by(drive_id=drive.id)
        drive_stats.append({
            **drive.to_dict(),
            "total": apps.count(),
            "applied": apps.filter_by(status="applied").count(),
            "shortlisted": apps.filter_by(status="shortlisted").count(),
            "selected": apps.filter_by(status="selected").count(),
            "rejected": apps.filter_by(status="rejected").count(),
        })
    return _ok({
        "company": company.to_dict(include_user=True),
        "drives": drive_stats,
        "total_drives": len(drives),
        "total_applicants": sum(d["total"] for d in drive_stats),
        "total_selected": sum(d["selected"] for d in drive_stats),
    })
@company_bp.route("/drives", methods=["GET"])
@company_required
def list_drives():
    company = _get_company_profile()
    if not company:
        return _err("Profile not found.", 404)
    if company.approval_status != "approved":
        return _err("Your company must be approved to manage drives.", 403)
    drives = PlacementDrive.query.filter_by(company_id=company.id)        .order_by(PlacementDrive.created_at.desc()).all()
    return _ok([d.to_dict() for d in drives])
@company_bp.route("/drives", methods=["POST"])
@company_required
def create_drive():
    company = _get_company_profile()
    if not company:
        return _err("Profile not found.", 404)
    if company.approval_status != "approved":
        return _err("Your company must be approved by admin before creating drives.", 403)
    body = request.get_json(silent=True) or {}
    required = ["job_title", "job_description", "deadline"]
    for field in required:
        if not body.get(field):
            return _err(f"'{field}' is required.")
    try:
        deadline = date.fromisoformat(body["deadline"])
    except ValueError:
        return _err("Invalid deadline format. Use YYYY-MM-DD.")
    if deadline <= date.today():
        return _err("Deadline must be a future date.")
    interview_date = None
    if body.get("interview_date"):
        try:
            interview_date = datetime.fromisoformat(body["interview_date"])
        except ValueError:
            return _err("Invalid interview_date format.")
    branches = body.get("eligible_branches", [])
    drive = PlacementDrive(
        company_id=company.id,
        job_title=body["job_title"],
        job_description=body["job_description"],
        min_cgpa=float(body.get("min_cgpa", 0.0)),
        eligible_year=body.get("eligible_year"),
        package=body.get("package", ""),
        location=body.get("location", ""),
        job_type=body.get("job_type", "Full-time"),
        deadline=deadline,
        interview_date=interview_date,
    )
    drive.set_eligible_branches(branches if isinstance(branches, list) else [])
    db.session.add(drive)
    db.session.commit()
    cache.delete("admin:stats")
    return _ok(drive.to_dict(), msg="Drive created and submitted for admin approval.", status=201)
@company_bp.route("/drives/<int:did>", methods=["PUT"])
@company_required
def update_drive(did):
    company = _get_company_profile()
    drive = PlacementDrive.query.filter_by(id=did, company_id=company.id).first()
    if not drive:
        return _err("Drive not found.", 404)
    if drive.status == "approved":
        return _err("Cannot edit an approved drive. Contact admin.")
    body = request.get_json(silent=True) or {}
    updatable = ["job_title", "job_description", "package", "location", "job_type",
                 "min_cgpa", "eligible_year"]
    for field in updatable:
        if field in body:
            setattr(drive, field, body[field])
    if "eligible_branches" in body:
        drive.set_eligible_branches(body["eligible_branches"])
    if "deadline" in body:
        drive.deadline = date.fromisoformat(body["deadline"])
    if "interview_date" in body:
        drive.interview_date = datetime.fromisoformat(body["interview_date"]) if body["interview_date"] else None
    db.session.commit()
    return _ok(drive.to_dict(), msg="Drive updated.")
@company_bp.route("/drives/<int:did>/applications", methods=["GET"])
@company_required
def drive_applications(did):
    company = _get_company_profile()
    drive = PlacementDrive.query.filter_by(id=did, company_id=company.id).first()
    if not drive:
        return _err("Drive not found.", 404)
    status_filter = request.args.get("status", "")
    query = Application.query.filter_by(drive_id=did)
    if status_filter:
        query = query.filter_by(status=status_filter)
    apps = query.all()
    return _ok({
        "drive": drive.to_dict(),
        "applications": [a.to_dict(include_student=True) for a in apps],
        "total": len(apps),
    })
@company_bp.route("/applications/<int:aid>/status", methods=["PUT"])
@company_required
def update_application_status(aid):
    company = _get_company_profile()
    app = Application.query.get_or_404(aid)
    drive = PlacementDrive.query.filter_by(id=app.drive_id, company_id=company.id).first()
    if not drive:
        return _err("Unauthorized.", 403)
    body = request.get_json(silent=True) or {}
    new_status = body.get("status")
    if new_status not in Application.STATUS_CHOICES:
        return _err(f"Status must be one of: {Application.STATUS_CHOICES}")
    app.status = new_status
    app.notes = body.get("notes", app.notes)
    db.session.commit()
    cache.delete("admin:stats")
    return _ok(app.to_dict(), msg=f"Application status updated to '{new_status}'.")
@company_bp.route("/applications/<int:aid>/offer-letter", methods=["GET"])
@company_required
def generate_offer_letter(aid):
    from flask import render_template_string
    company = _get_company_profile()
    app = Application.query.get_or_404(aid)
    drive = PlacementDrive.query.filter_by(id=app.drive_id, company_id=company.id).first()
    if not drive:
        return _err("Unauthorized.", 403)
    if app.status != "selected":
        return _err("Offer letter can only be generated for selected candidates.")
    student = app.student
    offer_html = render_offer_letter(company, drive, student, app)
    return jsonify({"success": True, "data": {"html": offer_html}})
def render_offer_letter(company, drive, student, application):
    from datetime import date
    today = date.today().strftime("%d %B %Y")
    joining = drive.interview_date.strftime("%d %B %Y") if drive.interview_date else "To be communicated"
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {  font-family: Arial, sans-serif; margin: 60px; color: #333; line-height: 1.6; } 
            .header {  text-align: center; border-bottom: 3px solid #2563eb; padding-bottom: 20px; } 
            .company-name {  font-size: 28px; font-weight: bold; color: #2563eb; } 
            .title {  font-size: 20px; color: #555; } 
            .content {  margin-top: 40px; } 
            .field {  margin: 8px 0; } 
            .label {  font-weight: bold; } 
            .signature {  margin-top: 60px; } 
            .footer {  margin-top: 40px; font-size: 12px; color: #888; border-top: 1px solid #ddd; padding-top: 10px; } 
        </style>
    </head>
    <body>
        <div class="header">
            <div class="company-name">{company.company_name}</div>
            <div class="title">OFFER LETTER</div>
        </div>
        <div class="content">
            <p>Date: <strong>{today}</strong></p>
            <p>To,<br><strong>{student.full_name}</strong><br>Roll No: {student.roll_number}<br>Branch: {student.branch}</p>
            <p>Dear {student.full_name},</p>
            <p>We are pleased to offer you the position of <strong>{drive.job_title}</strong> at <strong>{company.company_name}</strong>.</p>
            <div class="field"><span class="label">Position:</span> {drive.job_title}</div>
            <div class="field"><span class="label">Package:</span> {drive.package or 'As per company standards'}</div>
            <div class="field"><span class="label">Location:</span> {drive.location or 'To be communicated'}</div>
            <div class="field"><span class="label">Job Type:</span> {drive.job_type}</div>
            <div class="field"><span class="label">Joining Date:</span> {joining}</div>
            <p style="margin-top:20px;">This offer is contingent upon successful completion of all background verification checks and submission of required documents. Please respond to confirm your acceptance within 7 working days.</p>
            <div class="signature">
                <p>Yours sincerely,</p>
                <br><br>
                <p><strong>________________________</strong><br>
                {company.hr_contact or 'HR Manager'}<br>
                {company.company_name}<br>
                {company.hr_email or ''}<br>
                {company.phone or ''}</p>
            </div>
        </div>
        <div class="footer">
            <p>This is an auto-generated offer letter from the Placement Portal Application. Application ID: #{application.id}</p>
        </div>
    </body>
    </html>
    """
