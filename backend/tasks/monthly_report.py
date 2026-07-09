import os
import io
import logging
from datetime import datetime, date
from extensions import celery
from flask_mail import Message
logger = logging.getLogger(__name__)
@celery.task(name="tasks.monthly_report.send_monthly_report", bind=True)
def send_monthly_report(self):
    from extensions import db, mail
    from models import Application, PlacementDrive, StudentProfile, CompanyProfile, User
    now = datetime.utcnow()
    report_month = now.month
    report_year = now.year
    month_name = datetime(report_year, report_month, 1).strftime("%B %Y")
    drives_this_month = PlacementDrive.query.filter(
        db.extract("month", PlacementDrive.created_at) == report_month,
        db.extract("year", PlacementDrive.created_at) == report_year,
    ).all()
    apps_this_month = Application.query.filter(
        db.extract("month", Application.applied_at) == report_month,
        db.extract("year", Application.applied_at) == report_year,
    ).all()
    selected = [a for a in apps_this_month if a.status == "selected"]
    shortlisted = [a for a in apps_this_month if a.status == "shortlisted"]
    rejected = [a for a in apps_this_month if a.status == "rejected"]
    applied = [a for a in apps_this_month if a.status == "applied"]
    total_students = StudentProfile.query.count()
    total_companies = CompanyProfile.query.filter_by(approval_status="approved").count()
    company_counts = {}
    for a in selected:
        cname = a.drive.company.company_name if a.drive and a.drive.company else "Unknown"
        company_counts[cname] = company_counts.get(cname, 0) + 1
    top_companies = sorted(company_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    html_report = _build_report_html(
        month_name=month_name,
        drives=drives_this_month,
        total_applied=len(apps_this_month),
        total_selected=len(selected),
        total_shortlisted=len(shortlisted),
        total_rejected=len(rejected),
        still_applied=len(applied),
        total_students=total_students,
        total_companies=total_companies,
        top_companies=top_companies,
        selected_apps=selected[:10],
    )
    pdf_bytes = _generate_pdf(html_report)
    admin_user = User.query.filter_by(role="admin").first()
    if not admin_user:
        logger.error("No admin user found.")
        return {"status": "error", "message": "No admin user found"}
    try:
        msg = Message(
            subject=f"📊 Monthly Placement Report — {month_name}",
            recipients=[admin_user.email],
            html=html_report,
        )
        if pdf_bytes:
            msg.attach(
                filename=f"placement_report_{report_year}_{report_month:02d}.pdf",
                content_type="application/pdf",
                data=pdf_bytes,
            )
        mail.send(msg)
        logger.info(f"Monthly report sent to {admin_user.email}")
        return {"status": "ok", "month": month_name, "pdf_attached": pdf_bytes is not None}
    except Exception as e:
        logger.error(f"Failed to send monthly report: {e}")
        return {"status": "error", "error": str(e)}
def _build_report_html(month_name, drives, total_applied, total_selected,
                        total_shortlisted, total_rejected, still_applied,
                        total_students, total_companies, top_companies, selected_apps):
    drives_rows = "".join([
        f"<tr><td>{d.job_title}</td><td>{d.company.company_name}</td>"
        f"<td>{d.package or 'N/A'}</td><td>{d.status}</td>"
        f"<td>{d.created_at.strftime('%d %b %Y')}</td></tr>"
        for d in drives
    ]) or "<tr><td colspan='5' style='text-align:center;color:#888'>No drives this month</td></tr>"
    selected_rows = "".join([
        f"<tr><td>{a.student.full_name}</td><td>{a.student.roll_number}</td>"
        f"<td>{a.drive.job_title}</td><td>{a.drive.company.company_name}</td>"
        f"<td>{a.drive.package or 'N/A'}</td></tr>"
        for a in selected_apps
    ]) or "<tr><td colspan='5' style='text-align:center;color:#888'>No selections this month</td></tr>"
    top_co_rows = "".join([
        f"<tr><td>{name}</td><td>{count}</td></tr>"
        for name, count in top_companies
    ]) or "<tr><td colspan='2' style='text-align:center;color:#888'>No data</td></tr>"
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; background: #f1f5f9; color: #1e293b; }}
            .container {{ max-width: 900px; margin: 30px auto; background: white; border-radius: 12px;
                          box-shadow: 0 4px 20px rgba(0,0,0,0.1); overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #1e3a8a, #3b82f6);
                       color: white; padding: 40px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 28px; }}
            .header p {{ margin: 8px 0 0; opacity: 0.85; font-size: 16px; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px;
                           background: #e2e8f0; margin: 0; }}
            .stat-box {{ background: white; padding: 24px; text-align: center; }}
            .stat-box .num {{ font-size: 36px; font-weight: 700; color: #2563eb; }}
            .stat-box .label {{ font-size: 13px; color: #64748b; margin-top: 4px; }}
            .section {{ padding: 30px 40px; }}
            .section h2 {{ font-size: 20px; color: #1e293b; border-left: 4px solid #2563eb;
                           padding-left: 12px; margin-bottom: 16px; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
            th {{ background: #f8fafc; color: #475569; padding: 10px 14px;
                  text-align: left; font-weight: 600; border-bottom: 2px solid #e2e8f0; }}
            td {{ padding: 10px 14px; border-bottom: 1px solid #f1f5f9; }}
            tr:hover td {{ background: #f8fafc; }}
            .badge {{ display: inline-block; padding: 3px 10px; border-radius: 999px;
                      font-size: 12px; font-weight: 600; }}
            .badge-green {{ background: #dcfce7; color: #15803d; }}
            .badge-blue {{ background: #dbeafe; color: #1d4ed8; }}
            .footer {{ background: #f8fafc; padding: 20px 40px; text-align: center;
                       color: #94a3b8; font-size: 13px; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 Monthly Placement Report</h1>
                <p>{month_name} | Institute Placement Cell</p>
            </div>
            <div class="stats-grid">
                <div class="stat-box"><div class="num">{len(drives)}</div><div class="label">Drives Conducted</div></div>
                <div class="stat-box"><div class="num">{total_applied}</div><div class="label">Applications</div></div>
                <div class="stat-box"><div class="num">{total_selected}</div><div class="label">Students Selected</div></div>
                <div class="stat-box"><div class="num">{total_companies}</div><div class="label">Active Companies</div></div>
            </div>
            <div class="section">
                <h2>Summary</h2>
                <table>
                    <tr><th>Metric</th><th>Count</th></tr>
                    <tr><td>Total Students on Platform</td><td>{total_students}</td></tr>
                    <tr><td>Applications — Applied</td><td>{still_applied}</td></tr>
                    <tr><td>Applications — Shortlisted</td><td>{total_shortlisted}</td></tr>
                    <tr><td>Applications — Selected</td><td><span class="badge badge-green">{total_selected}</span></td></tr>
                    <tr><td>Applications — Rejected</td><td>{total_rejected}</td></tr>
                    <tr><td>Placement Rate (this month)</td>
                        <td><strong>{f"{(total_selected/total_applied*100):.1f}%" if total_applied > 0 else "0.0%"}</strong></td></tr>
                </table>
            </div>
            <div class="section">
                <h2>Placement Drives This Month</h2>
                <table>
                    <tr><th>Job Title</th><th>Company</th><th>Package</th><th>Status</th><th>Posted</th></tr>
                    {drives_rows}
                </table>
            </div>
            <div class="section">
                <h2>Top Hiring Companies</h2>
                <table>
                    <tr><th>Company</th><th>Selections</th></tr>
                    {top_co_rows}
                </table>
            </div>
            <div class="section">
                <h2>Selected Students (Top 10)</h2>
                <table>
                    <tr><th>Name</th><th>Roll No</th><th>Job Title</th><th>Company</th><th>Package</th></tr>
                    {selected_rows}
                </table>
            </div>
            <div class="footer">
                <p>This report was auto-generated by the Placement Portal Application on
                   {datetime.utcnow().strftime('%d %B %Y at %H:%M UTC')}</p>
                <p>© Institute Placement Cell</p>
            </div>
        </div>
    </body>
    </html>
    """

def _generate_pdf(html_content: str):
    try:
        from xhtml2pdf import pisa
        buf = io.BytesIO()
        pisa.CreatePDF(html_content, dest=buf)
        return buf.getvalue()
    except ImportError:
        logger.warning("xhtml2pdf not installed. PDF will not be generated.")
        return None
    except Exception as e:
        logger.warning(f"PDF generation failed: {e}")
        return None
