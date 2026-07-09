import os
import csv
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt
from functools import wraps
from datetime import date
from werkzeug.utils import secure_filename
from extensions import db, cache
from models import StudentProfile, PlacementDrive, Application, CompanyProfile, User
student_bp = Blueprint("student", __name__, url_prefix="/api/student")
def _ok(data=None, msg="", status=200):
    return jsonify({"success": True, "data": data, "message": msg}), status
def _err(msg, status=400):
    return jsonify({"success": False, "message": msg}), status
def student_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get("role") != "student":
            return _err("Student access required.", 403)
        return fn(*args, **kwargs)
    return wrapper
def _get_student_profile():
    claims = get_jwt()
    user_id = int(claims.get("user_id"))
    return StudentProfile.query.filter_by(user_id=user_id).first()
def allowed_file(filename):
    exts = current_app.config.get("ALLOWED_EXTENSIONS", {"pdf", "doc", "docx"})
    return "." in filename and filename.rsplit(".", 1)[1].lower() in exts
@student_bp.route("/profile", methods=["GET"])
@student_required
def get_profile():
    student = _get_student_profile()
    if not student:
        return _err("Student profile not found.", 404)
    return _ok(student.to_dict(include_user=True))
@student_bp.route("/profile", methods=["PUT"])
@student_required
def update_profile():
    student = _get_student_profile()
    if not student:
        return _err("Student profile not found.", 404)
    body = request.get_json(silent=True) or {}
    updatable = ["full_name", "phone", "address", "linkedin", "github", "skills", "cgpa", "branch", "year"]
    for field in updatable:
        if field in body:
            val = body[field]
            if field == "cgpa":
                val = float(val)
                if not (0.0 <= val <= 10.0):
                    return _err("CGPA must be between 0.0 and 10.0.")
            if field == "year":
                val = int(val)
                if val not in (1, 2, 3, 4):
                    return _err("Year must be 1, 2, 3, or 4.")
            setattr(student, field, val)
    db.session.commit()
    return _ok(student.to_dict(include_user=True), msg="Profile updated.")
@student_bp.route("/profile/resume", methods=["POST"])
@student_required
def upload_resume():
    student = _get_student_profile()
    if not student:
        return _err("Profile not found.", 404)
    if "resume" not in request.files:
        return _err("No file uploaded. Use field name 'resume'.")
    file = request.files["resume"]
    if file.filename == "":
        return _err("Empty filename.")
    if not allowed_file(file.filename):
        return _err("Only PDF, DOC, and DOCX files are allowed.")
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    filename = secure_filename(f"resume_{student.id}_{file.filename}")
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)
    student.resume_path = filepath
    student.resume_filename = file.filename
    db.session.commit()
    return _ok({"filename": file.filename}, msg="Resume uploaded successfully.")
@student_bp.route("/profile/resume", methods=["GET"])
@student_required
def download_resume():
    student = _get_student_profile()
    if not student or not student.resume_path:
        return _err("No resume found.", 404)
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(upload_dir, os.path.basename(student.resume_path))
@student_bp.route("/drives", methods=["GET"])
@student_required
def list_drives():
    student = _get_student_profile()
    if not student:
        return _err("Complete your profile first.", 404)
    q = request.args.get("q", "").strip()
    filter_eligible = request.args.get("eligible_only", "false").lower() == "true"
    cached_key = "drives:approved"
    drives_data = cache.get(cached_key)
    if not drives_data:
        drives = (
            PlacementDrive.query
            .join(CompanyProfile, PlacementDrive.company_id == CompanyProfile.id)
            .filter(
                PlacementDrive.status == "approved",
                PlacementDrive.deadline >= date.today(),
            )
            .order_by(PlacementDrive.deadline.asc())
            .all()
        )
        drives_data = [d.to_dict(include_company=True) for d in drives]
        cache.set(cached_key, drives_data, timeout=120)
    if q:
        drives_data = [
            d for d in drives_data
            if q.lower() in d["job_title"].lower()
            or q.lower() in d.get("company_name", "").lower()
            or q.lower() in d.get("location", "").lower()
        ]
    if filter_eligible:
        def is_eligible(d):
            if d["min_cgpa"] and student.cgpa < d["min_cgpa"]:
                return False
            if d["eligible_year"] and student.year != d["eligible_year"]:
                return False
            branches = d.get("eligible_branches", [])
            if branches and student.branch not in branches:
                return False
            return True
        drives_data = [d for d in drives_data if is_eligible(d)]
    applied_drive_ids = {a.drive_id for a in student.applications}
    for d in drives_data:
        d["already_applied"] = d["id"] in applied_drive_ids
        d["is_eligible"] = _check_eligibility(student, d)
    return _ok(drives_data)
def _check_eligibility(student, drive_dict) -> dict:
    issues = []
    if drive_dict.get("min_cgpa") and student.cgpa < drive_dict["min_cgpa"]:
        issues.append(f"Min CGPA required: {drive_dict['min_cgpa']}")
    if drive_dict.get("eligible_year") and student.year != drive_dict["eligible_year"]:
        issues.append(f"Required year: {drive_dict['eligible_year']}")
    branches = drive_dict.get("eligible_branches", [])
    if branches and student.branch not in branches:
        issues.append(f"Required branches: {', '.join(branches)}")
    return {"eligible": len(issues) == 0, "issues": issues}
@student_bp.route("/drives/<int:did>", methods=["GET"])
@student_required
def get_drive(did):
    drive = PlacementDrive.query.filter_by(id=did, status="approved").first()
    if not drive:
        return _err("Drive not found.", 404)
    student = _get_student_profile()
    data = drive.to_dict(include_company=True)
    data["already_applied"] = Application.query.filter_by(
        student_id=student.id, drive_id=did
    ).first() is not None
    data["eligibility"] = _check_eligibility(student, data)
    return _ok(data)
@student_bp.route("/drives/<int:did>/apply", methods=["POST"])
@student_required
def apply_drive(did):
    student = _get_student_profile()
    if not student:
        return _err("Complete your profile before applying.", 404)
    user = User.query.get(student.user_id)
    if user.is_blacklisted:
        return _err("Your account is blacklisted. Contact admin.", 403)
    drive = PlacementDrive.query.filter_by(id=did, status="approved").first()
    if not drive:
        return _err("Drive not found or not approved.", 404)
    if drive.deadline < date.today():
        return _err("Application deadline has passed.")
    existing = Application.query.filter_by(student_id=student.id, drive_id=did).first()
    if existing:
        return _err("You have already applied for this drive.", 409)
    issues = []
    if drive.min_cgpa and student.cgpa < drive.min_cgpa:
        issues.append(f"Your CGPA ({student.cgpa}) is below the minimum required ({drive.min_cgpa})")
    branches = drive.get_eligible_branches()
    if branches and student.branch not in branches:
        issues.append(f"Your branch ({student.branch}) is not eligible for this drive")
    if drive.eligible_year and student.year != drive.eligible_year:
        issues.append(f"Your year ({student.year}) does not match required year ({drive.eligible_year})")
    if issues:
        return _err("Not eligible: " + "; ".join(issues), 422)
    application = Application(student_id=student.id, drive_id=did)
    db.session.add(application)
    db.session.commit()
    cache.delete("admin:stats")
    return _ok(application.to_dict(), msg="Application submitted successfully!", status=201)
@student_bp.route("/applications", methods=["GET"])
@student_required
def list_applications():
    student = _get_student_profile()
    if not student:
        return _err("Profile not found.", 404)
    apps = Application.query.filter_by(student_id=student.id)        .order_by(Application.applied_at.desc()).all()
    return _ok([a.to_dict(include_drive=True) for a in apps])
@student_bp.route("/export-csv", methods=["POST"])
@student_required
def trigger_export():
    from tasks.export_csv import export_student_applications
    student = _get_student_profile()
    if not student:
        return _err("Profile not found.", 404)
    task = export_student_applications.delay(student.id, student.user_id)
    return _ok({"task_id": task.id}, msg="Export started. You'll be notified when it's ready.", status=202)
@student_bp.route("/export-status/<task_id>", methods=["GET"])
@student_required
def export_status(task_id):
    from extensions import celery
    result = celery.AsyncResult(task_id)
    response = {
        "task_id": task_id,
        "state": result.state,
        "ready": result.ready(),
    }
    if result.ready() and result.successful():
        filename = result.result
        export_dir = current_app.config["EXPORT_FOLDER"]
        filepath = os.path.join(export_dir, secure_filename(filename))
        
        # Directory/file readiness check
        if not os.path.exists(filepath):
            # File is not fully written to disk yet
            response["ready"] = False
            response["state"] = "PENDING"
        else:
            response["result"] = filename
            response["download_url"] = f"/api/student/download-export/{filename}"
    elif result.failed():
        response["error"] = str(result.result)
    return _ok(response)
@student_bp.route("/download-export/<filename>", methods=["GET"])
def download_export(filename):
    export_dir = current_app.config["EXPORT_FOLDER"]
    safe_name = secure_filename(filename)
    return send_from_directory(export_dir, safe_name, as_attachment=True, mimetype="text/csv")
