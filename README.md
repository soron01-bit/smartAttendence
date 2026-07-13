# Smart Attendance System

A web-based Smart Attendance System built with **Django**, **HTML**, **CSS**, and **JavaScript** that uses **face detection** and **blink-based liveness verification** before marking attendance.

## Features

- Face detection using webcam
- Blink detection for basic liveness verification
- Automatic attendance marking after successful verification
- Student registration with face data
- Attendance records management
- Responsive user interface
- Django admin panel for managing data
- Web-based application (accessible from desktop and mobile browser)

## Tech Stack

### Backend
- Django
- Python

### Frontend
- HTML
- CSS
- JavaScript

### Database
- SQLite

### AI / Computer Vision
- face-api.js

## Project Structure

```text
SmartAttendance/
│
├── attendance/
├── templates/
├── static/
├── media/
├── manage.py
└── requirements.txt
```

## Installation

Clone the repository

```bash
git clone https://github.com/your-username/SmartAttendance.git
```

Move into the project directory

```bash
cd SmartAttendance
```

Install dependencies

```bash
pip install -r requirements.txt
```

Run migrations

```bash
python manage.py migrate
```

Start the server

```bash
python manage.py runserver
```

Open in browser

```
http://127.0.0.1:8000/
```

## How It Works

1. Register a student.
2. Open the attendance page.
3. The webcam detects the face.
4. The system waits for a blink.
5. If verification succeeds, attendance is marked.

## Future Improvements

- Better liveness detection
- Anti-photo spoof detection
- PostgreSQL support
- Firebase integration
- Face recognition optimization for large datasets
- QR-based backup attendance
- Attendance analytics dashboard


## Author

**Sharan Sarkar**

B.Tech CSE Student
