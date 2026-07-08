from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity, get_jwt
)
from datetime import datetime
from extensions import db
from models import User, CompanyProfile, StudentProfile
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
def _ok(data=None, msg="", status=200):
    return jsonify({"success": True, "data": data, "message": msg}), status
def _err(msg, status=400):
    return jsonify({"success": False, "message": msg}), status
@auth_bp.route("/register", methods=["POST"])
def register():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    role = body.get("role") or ""  
    if not email or not password or not role:
        return _err("email, password, and role are required.")
    if role not in ("student", "company"):
        return _err("role must be 'student' or 'company'.")
    if len(password) < 6:
        return _err("Password must be at least 6 characters.")
    if User.query.filter_by(email=email).first():
        return _err("An account with this email already exists.", 409)
    user = User(email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()  
    if role == "company":
        company_name = (body.get("company_name") or "").strip()
        if not company_name:
            db.session.rollback()
            return _err("company_name is required for company registration.")
        profile = CompanyProfile(
            user_id=user.id,
            company_name=company_name,
            hr_contact=body.get("hr_contact", ""),
            hr_email=email,
            website=body.get("website", ""),
            description=body.get("description", ""),
            industry=body.get("industry", ""),
        )
        db.session.add(profile)
    elif role == "student":
        full_name = (body.get("full_name") or "").strip()
        roll_number = (body.get("roll_number") or "").strip()
        branch = (body.get("branch") or "").strip()
        year = body.get("year")
        cgpa = body.get("cgpa", 0.0)
        if not full_name or not roll_number or not branch or not year:
            db.session.rollback()
            return _err("full_name, roll_number, branch, and year are required for student registration.")
        if StudentProfile.query.filter_by(roll_number=roll_number).first():
            db.session.rollback()
            return _err("A student with this roll number already exists.", 409)
        profile = StudentProfile(
            user_id=user.id,
            full_name=full_name,
            roll_number=roll_number,
            branch=branch,
            year=int(year),
            cgpa=float(cgpa),
            phone=body.get("phone", ""),
        )
        db.session.add(profile)
    db.session.commit()
    return _ok(msg="Registration successful. Please log in.", status=201)
@auth_bp.route("/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        return _err("Email and password are required.")
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return _err("Invalid email or password.", 401)
    if user.is_blacklisted:
        return _err("Your account has been blacklisted. Contact admin.", 403)
    if not user.is_active:
        return _err("Your account is inactive. Contact admin.", 403)
    if user.role == "company" and user.company_profile:
        if user.company_profile.approval_status == "pending":
            return _err("Your company registration is pending admin approval.", 403)
        if user.company_profile.approval_status == "rejected":
            return _err("Your company registration was rejected. Contact admin.", 403)
    user.last_login = datetime.utcnow()
    db.session.commit()
    additional_claims = {"role": user.role, "user_id": user.id}
    token = create_access_token(identity=str(user.id), additional_claims=additional_claims)
    profile_id = None
    name = user.email
    if user.role == "company" and user.company_profile:
        profile_id = user.company_profile.id
        name = user.company_profile.company_name
    elif user.role == "student" and user.student_profile:
        profile_id = user.student_profile.id
        name = user.student_profile.full_name
    return _ok({
        "token": token,
        "role": user.role,
        "user_id": user.id,
        "profile_id": profile_id,
        "name": name,
        "email": user.email,
    })
@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return _err("User not found.", 404)
    data = user.to_dict()
    if user.role == "company" and user.company_profile:
        data["profile"] = user.company_profile.to_dict()
    elif user.role == "student" and user.student_profile:
        data["profile"] = user.student_profile.to_dict()
    return _ok(data)
