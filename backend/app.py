import os
import sys
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
sys.path.insert(0, os.path.dirname(__file__))
from flask import Flask, redirect, render_template, url_for, send_from_directory
from flask_cors import CORS
from celery.schedules import crontab
from config import Config
from extensions import db, jwt, cache, mail, celery
def make_celery(app: Flask) -> None:
    celery.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_RESULT_BACKEND"],
        timezone=app.config["CELERY_TIMEZONE"],
        enable_utc=app.config["CELERY_ENABLE_UTC"],
        beat_schedule={
            "monthly-report": {
                "task": "tasks.monthly_report.send_monthly_report",
                "schedule": crontab(day_of_month=9, hour=19, minute=44),
            },
        },
    )
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask
def create_app(config_class=Config) -> Flask:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    FRONTEND_DIR = os.path.join(BASE_DIR, '..', 'frontend', 'src')
    app = Flask(
        __name__,
        template_folder=FRONTEND_DIR,
        static_folder=FRONTEND_DIR,
        static_url_path='/static',
    )
    app.config.from_object(config_class)
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
    db.init_app(app)
    jwt.init_app(app)
    cache.init_app(app)
    mail.init_app(app)
    make_celery(app)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["EXPORT_FOLDER"], exist_ok=True)
    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.company import company_bp
    from routes.student import student_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(company_bp)
    app.register_blueprint(student_bp)
    @app.route("/")
    def index():
        return redirect("/login")
    @app.route("/login")
    def login_page():
        return render_template("login.html")
    @app.route("/register")
    def register_page():
        return render_template("register.html")
    @app.route("/admin/dashboard")
    def admin_dashboard():
        return render_template("admin/dashboard.html")
    @app.route("/admin/companies")
    def admin_companies():
        return render_template("admin/companies.html")
    @app.route("/admin/students")
    def admin_students():
        return render_template("admin/students.html")
    @app.route("/admin/drives")
    def admin_drives():
        return render_template("admin/drives.html")
    @app.route("/company/dashboard")
    def company_dashboard():
        return render_template("company/dashboard.html")
    @app.route("/company/drives")
    def company_drives():
        return render_template("company/drives.html")
    @app.route("/company/applications")
    def company_applications():
        return render_template("company/applications.html")
    @app.route("/student/dashboard")
    def student_dashboard():
        return render_template("student/dashboard.html")
    @app.route("/student/profile")
    def student_profile():
        return render_template("student/profile.html")
    @app.route("/student/applications")
    def student_applications():
        return render_template("student/applications.html")
    @app.route("/uploads/<path:filename>")
    def serve_upload(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_data):
        return {"success": False, "message": "Token has expired. Please log in again."}, 401
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return {"success": False, "message": "Invalid token."}, 401
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return {"success": False, "message": "Authorization token required."}, 401
    if not os.environ.get("CELERY_WORKER"):
        with app.app_context():
            import models  
            try:
                db.create_all()
                _seed_admin(app)
            except Exception as e:
                app.logger.warning(f"Database initialization skipped or failed: {e}")
    return app
def _seed_admin(app: Flask) -> None:
    from models import User
    if not User.query.filter_by(role="admin").first():
        admin = User(
            email=app.config["ADMIN_EMAIL"],
            role="admin",
            is_active=True,
        )
        admin.set_password(app.config["ADMIN_PASSWORD"])
        db.session.add(admin)
        db.session.commit()
        print(f"[PPA] Admin seeded: {app.config['ADMIN_EMAIL']}")
if __name__ == "__main__":
    flask_app = create_app()
    flask_app.run(debug=True, port=5001)
