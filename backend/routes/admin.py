from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from functools import wraps
from datetime import datetime, date
from extensions import db, cache
from models import User, CompanyProfile, StudentProfile, PlacementDrive, Application
admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")
def _ok(data=None, msg="", status=200):
    return jsonify({"success": True, "data": data, "message": msg}), status
def _err(msg, status=400):
    return jsonify({"success": False, "message": msg}), status
def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get("role") != "admin":
            return _err("Admin access required.", 403)
        return fn(*args, **kwargs)
    return wrapper
@admin_bp.route("/dashboard", methods=["GET"])
@admin_required
def dashboard():
    cached = cache.get("admin:stats")
    if cached:
        return _ok(cached)
    total_students = StudentProfile.query.count()
    total_companies = CompanyProfile.query.count()
    total_drives = PlacementDrive.query.count()
    total_applications = Application.query.count()
    pending_companies = CompanyProfile.query.filter_by(approval_status="pending").count()
    pending_drives = PlacementDrive.query.filter_by(status="pending").count()
    approved_companies = CompanyProfile.query.filter_by(approval_status="approved").count()
    approved_drives = PlacementDrive.query.filter_by(status="approved").count()
    selected_students = Application.query.filter_by(status="selected").count()
    shortlisted = Application.query.filter_by(status="shortlisted").count()
    rejected_apps = Application.query.filter_by(status="rejected").count()
    app_status_chart = {
        "applied": Application.query.filter_by(status="applied").count(),
        "shortlisted": shortlisted,
        "selected": selected_students,
        "rejected": rejected_apps,
    }
    top_companies = (
        db.session.query(CompanyProfile.company_name, db.func.count(PlacementDrive.id).label("cnt"))
        .join(PlacementDrive, PlacementDrive.company_id == CompanyProfile.id)
        .group_by(CompanyProfile.id)
        .order_by(db.desc("cnt"))
        .limit(5)
        .all()
    )
    top_companies_data = [{"name": r[0], "drives": r[1]} for r in top_companies]
    monthly_trend = []
    now = datetime.utcnow()
    for i in range(5, -1, -1):
        month = (now.month - i - 1) % 12 + 1
        year = now.year if now.month - i > 0 else now.year - 1
        count = Application.query.filter(
            db.extract("month", Application.applied_at) == month,
            db.extract("year", Application.applied_at) == year,
        ).count()
        monthly_trend.append({"month": f"{year}-{month:02d}", "count": count})
    stats = {
        "total_students": total_students,
        "total_companies": total_companies,
        "total_drives": total_drives,
        "total_applications": total_applications,
        "pending_companies": pending_companies,
        "pending_drives": pending_drives,
        "approved_companies": approved_companies,
        "approved_drives": approved_drives,
        "selected_students": selected_students,
        "app_status_chart": app_status_chart,
        "top_companies": top_companies_data,
        "monthly_trend": monthly_trend,
    }
    cache.set("admin:stats", stats, timeout=300)
    return _ok(stats)
@admin_bp.route("/companies", methods=["GET"])
@admin_required
def list_companies():
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    query = CompanyProfile.query.join(User, CompanyProfile.user_id == User.id)
    if q:
        query = query.filter(
            db.or_(
                CompanyProfile.company_name.ilike(f"%{q}%"),
                User.email.ilike(f"%{q}%"),
                CompanyProfile.industry.ilike(f"%{q}%"),
            )
        )
    if status_filter:
        query = query.filter(CompanyProfile.approval_status == status_filter)
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    return _ok({
        "companies": [c.to_dict(include_user=True) for c in paginated.items],
        "total": paginated.total,
        "pages": paginated.pages,
        "current_page": page,
    })
@admin_bp.route("/companies/<int:cid>/approve", methods=["PUT"])
@admin_required
def approve_company(cid):
    company = CompanyProfile.query.get_or_404(cid)
    company.approval_status = "approved"
    company.rejection_reason = None
    db.session.commit()
    cache.delete("admin:stats")
    return _ok(msg=f"{company.company_name} approved successfully.")
@admin_bp.route("/companies/<int:cid>/reject", methods=["PUT"])
@admin_required
def reject_company(cid):
    body = request.get_json(silent=True) or {}
    company = CompanyProfile.query.get_or_404(cid)
    company.approval_status = "rejected"
    company.rejection_reason = body.get("reason", "")
    db.session.commit()
    cache.delete("admin:stats")
    return _ok(msg=f"{company.company_name} rejected.")
@admin_bp.route("/companies/<int:cid>/blacklist", methods=["PUT"])
@admin_required
def blacklist_company(cid):
    company = CompanyProfile.query.get_or_404(cid)
    user = User.query.get(company.user_id)
    user.is_blacklisted = not user.is_blacklisted
    db.session.commit()
    status = "blacklisted" if user.is_blacklisted else "un-blacklisted"
    return _ok(msg=f"{company.company_name} {status}.")
@admin_bp.route("/companies/<int:cid>", methods=["GET"])
@admin_required
def get_company(cid):
    company = CompanyProfile.query.get_or_404(cid)
    data = company.to_dict(include_user=True)
    data["drives"] = [d.to_dict() for d in company.drives]
    return _ok(data)
@admin_bp.route("/students", methods=["GET"])
@admin_required
def list_students():
    q = request.args.get("q", "").strip()
    branch_filter = request.args.get("branch", "")
    year_filter = request.args.get("year", "")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    query = StudentProfile.query.join(User, StudentProfile.user_id == User.id)
    if q:
        query = query.filter(
            db.or_(
                StudentProfile.full_name.ilike(f"%{q}%"),
                StudentProfile.roll_number.ilike(f"%{q}%"),
                User.email.ilike(f"%{q}%"),
            )
        )
    if branch_filter:
        query = query.filter(StudentProfile.branch == branch_filter)
    if year_filter:
        query = query.filter(StudentProfile.year == int(year_filter))
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    return _ok({
        "students": [s.to_dict(include_user=True) for s in paginated.items],
        "total": paginated.total,
        "pages": paginated.pages,
        "current_page": page,
    })
@admin_bp.route("/students/<int:sid>/blacklist", methods=["PUT"])
@admin_required
def blacklist_student(sid):
    student = StudentProfile.query.get_or_404(sid)
    user = User.query.get(student.user_id)
    user.is_blacklisted = not user.is_blacklisted
    db.session.commit()
    status = "blacklisted" if user.is_blacklisted else "un-blacklisted"
    return _ok(msg=f"{student.full_name} {status}.")
@admin_bp.route("/students/<int:sid>/activate", methods=["PUT"])
@admin_required
def toggle_student_active(sid):
    student = StudentProfile.query.get_or_404(sid)
    user = User.query.get(student.user_id)
    user.is_active = not user.is_active
    db.session.commit()
    status = "activated" if user.is_active else "deactivated"
    return _ok(msg=f"{student.full_name} {status}.")
@admin_bp.route("/students/<int:sid>", methods=["GET"])
@admin_required
def get_student(sid):
    student = StudentProfile.query.get_or_404(sid)
    data = student.to_dict(include_user=True)
    data["applications"] = [a.to_dict(include_drive=True) for a in student.applications]
    return _ok(data)
@admin_bp.route("/drives", methods=["GET"])
@admin_required
def list_drives():
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    query = PlacementDrive.query.join(CompanyProfile, PlacementDrive.company_id == CompanyProfile.id)
    if q:
        query = query.filter(
            db.or_(
                PlacementDrive.job_title.ilike(f"%{q}%"),
                CompanyProfile.company_name.ilike(f"%{q}%"),
            )
        )
    if status_filter:
        query = query.filter(PlacementDrive.status == status_filter)
    paginated = query.order_by(PlacementDrive.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return _ok({
        "drives": [d.to_dict(include_company=True) for d in paginated.items],
        "total": paginated.total,
        "pages": paginated.pages,
        "current_page": page,
    })
@admin_bp.route("/drives/<int:did>/approve", methods=["PUT"])
@admin_required
def approve_drive(did):
    drive = PlacementDrive.query.get_or_404(did)
    drive.status = "approved"
    drive.rejection_reason = None
    db.session.commit()
    cache.delete("admin:stats")
    cache.delete("drives:approved")
    return _ok(msg=f"Drive '{drive.job_title}' approved.")
@admin_bp.route("/drives/<int:did>/reject", methods=["PUT"])
@admin_required
def reject_drive(did):
    body = request.get_json(silent=True) or {}
    drive = PlacementDrive.query.get_or_404(did)
    drive.status = "rejected"
    drive.rejection_reason = body.get("reason", "")
    db.session.commit()
    cache.delete("admin:stats")
    return _ok(msg=f"Drive '{drive.job_title}' rejected.")
@admin_bp.route("/drives/<int:did>/close", methods=["PUT"])
@admin_required
def close_drive(did):
    drive = PlacementDrive.query.get_or_404(did)
    drive.status = "closed"
    db.session.commit()
    cache.delete("drives:approved")
    return _ok(msg=f"Drive '{drive.job_title}' closed.")
@admin_bp.route("/applications", methods=["GET"])
@admin_required
def list_applications():
    status_filter = request.args.get("status", "")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    query = Application.query
    if status_filter:
        query = query.filter(Application.status == status_filter)
    paginated = query.order_by(Application.applied_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return _ok({
        "applications": [a.to_dict(include_student=True, include_drive=True) for a in paginated.items],
        "total": paginated.total,
        "pages": paginated.pages,
        "current_page": page,
    })
@admin_bp.route("/search", methods=["GET"])
@admin_required
def search():
    q = request.args.get("q", "").strip()
    search_type = request.args.get("type", "all")  
    if not q:
        return _err("Query parameter 'q' is required.")
    result = {}
    if search_type in ("all", "company"):
        companies = CompanyProfile.query.filter(
            CompanyProfile.company_name.ilike(f"%{q}%")
        ).limit(10).all()
        result["companies"] = [c.to_dict(include_user=True) for c in companies]
    if search_type in ("all", "student"):
        students = StudentProfile.query.filter(
            db.or_(
                StudentProfile.full_name.ilike(f"%{q}%"),
                StudentProfile.roll_number.ilike(f"%{q}%"),
            )
        ).limit(10).all()
        result["students"] = [s.to_dict(include_user=True) for s in students]
    if search_type in ("all", "drive"):
        drives = PlacementDrive.query.filter(
            PlacementDrive.job_title.ilike(f"%{q}%")
        ).limit(10).all()
        result["drives"] = [d.to_dict(include_company=True) for d in drives]
    return _ok(result)
