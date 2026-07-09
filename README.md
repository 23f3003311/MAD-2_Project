# Placement Portal Application (PPA)

## 📖 Overview
The Placement Portal Application (PPA) is a centralized, web-based platform designed to streamline campus placements. It bridges the gap between students looking for opportunities, companies looking to hire, and administrators moderating the entire ecosystem. 

This project was built as part of the IIT Madras BS Degree Modern Application Development II (MAD-2) course.

---

## 🚀 Features

### Admin
- **Dashboard Analytics:** View system-wide statistics (Total students, companies, drives, applications).
- **Moderation:** Approve or reject company registrations and placement drives.
- **User Management:** Blacklist fraudulent companies or students.

### Company
- **Company Profile:** Manage company details, industry, and contact info.
- **Placement Drives:** Post job drives with eligibility criteria (CGPA, Branch, Year).
- **Application Tracking:** Review student applications, update statuses (Shortlisted, Selected, Rejected).
- **Export Data:** Request asynchronous CSV exports of all applicants for a drive.

### Student
- **Student Profile:** Build a comprehensive resume profile (Skills, CGPA, GitHub, LinkedIn).
- **Job Feed:** View approved placement drives that match their eligibility.
- **One-Click Apply:** Apply to drives instantly.
- **Application Status:** Track real-time progress on submitted applications.

### Automated Background Tasks (Celery & Redis)
- **Daily Reminders:** Scheduled task that sends a daily email to students who have incomplete applications or pending actions.
- **Monthly Reports:** Generates an HTML/PDF activity report and emails it to the Admin on the 1st of every month.
- **CSV Exports:** Asynchronously generates CSV files of applicants for companies without blocking the main thread.

---

## 🛠️ Technology Stack

- **Backend:** Flask (Python)
- **Frontend:** Vue.js 3 (CDN), HTML5, CSS3, Bootstrap 5
- **Database:** SQLite & SQLAlchemy (ORM)
- **Authentication:** Flask-JWT-Extended (Token-based Auth)
- **Message Broker & Cache:** Redis
- **Background Jobs:** Celery & Celery Beat

---

## ⚙️ How to Run the Project Locally

### 1. Clone the Repository
```bash
git clone https://github.com/23f3003311/MAD-2_Project.git
cd MAD-2_Project
```

### 2. Set Up Virtual Environment & Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory and add the following configurations:
```env
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret
DATABASE_URL=sqlite:///ppa.db
REDIS_URL=redis://127.0.0.1:6379/0

MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com

ADMIN_EMAIL=admin@admin.com
ADMIN_PASSWORD=Admin@123
```

### 4. Start Redis Server
Ensure you have Redis installed and running on your system.
```bash
redis-server
```

### 5. Run the Application
You will need to open **3 separate terminal windows/tabs**.

---

**🖥️ Terminal 1 — Backend (Flask API)**

```bash
cd backend
source ../.venv/bin/activate
flask --app app run
```
*The Flask API will be accessible at **http://127.0.0.1:5000***

---

**🌐 Terminal 2 — Frontend (Static File Server)**

The frontend uses Vue.js 3 via CDN — no build step is required. Serve the static files using Python's built-in HTTP server:

```bash
cd frontend/src
python3 -m http.server 8080
```
*The frontend will be accessible at **http://localhost:8080/login.html***

---

**⚙️ Terminal 3 — Celery Worker & Beat Scheduler**

Run both the worker and beat together using Celery's embedded beat flag:

```bash
cd backend
source ../.venv/bin/activate
celery -A celery_worker.celery worker --beat --loglevel=info
```

> **Note:** The `--beat` flag runs both the task worker and the scheduler (beat) in a single process, which is suitable for development. For production, run them as separate processes.

---

## 👨‍💻 Author
**Sibani Tiwari**  
IIT Madras BS Degree Student  
Roll No: 23f3003311
