# Jeea You — Backend & AI Portfolio

A multilingual portfolio web application showcasing my backend development experience and AI-based application projects.

The portfolio combines Java/Spring backend experience with Python-based AI services, including music analysis, audio source separation, computer vision, and interactive web applications.

## Main Projects

### 1. MusicAI — Music Analysis Platform

MusicAI is an AI-powered web application that analyses uploaded music files and presents audio information through an interactive interface.

#### Main Features

* MP3 and WAV file upload
* Vocal and instrumental separation using Demucs
* Musical key and scale analysis
* Tempo and rhythm analysis
* Energy and dynamic-range analysis
* Vocal pitch and vocal-range analysis
* Instrument classification
* Genre and mood estimation
* Audio-feature visualisation
* Background analysis processing
* Per-file progress tracking
* Analysis cancellation
* Analysis result storage

#### Technologies

* Python
* Flask
* Flask-SQLAlchemy
* MySQL
* Librosa
* Demucs
* PyTorch
* torchcrepe
* Hugging Face Transformers
* Praat-Parselmouth
* HTML
* CSS
* JavaScript

---

### 2. EyeCareX — Interactive Eye Health Tests

EyeCareX is a web-based application that provides several interactive eye-health tests using camera input and computer-vision technology.

#### Main Features

* Visual acuity test
* Colour-vision test
* Astigmatism test
* Cataract test
* Glaucoma test
* Macular-health test
* Face and hand tracking
* Camera-based user interaction
* Multilingual interface

#### Technologies

* Python
* Flask
* OpenCV
* MediaPipe
* cvzone
* HTML
* CSS
* JavaScript

> EyeCareX is a portfolio demonstration project and is not intended to provide medical diagnoses.

---

### 3. HandEmote — Hand Gesture Recognition

HandEmote is a computer-vision project that detects hand landmarks and recognises user gestures through a live camera feed.

#### Main Features

* Real-time hand detection
* Hand-landmark tracking
* Gesture recognition
* Camera-based interaction
* Responsive result display

#### Technologies

* Python
* Flask
* OpenCV
* MediaPipe
* cvzone
* HTML
* CSS
* JavaScript

---

## Portfolio Features

* Korean, English, and Chinese language support
* Database-driven translation content
* Dynamic project and feature navigation
* Responsive desktop and mobile interface
* Editable multilingual résumé
* PDF résumé generation
* Résumé email delivery
* Music-analysis progress tracking
* Modular Flask Blueprint architecture

## Technical Skills

### Backend

* Java
* Spring
* Spring Boot
* Python
* Flask
* REST API
* SQLAlchemy
* JSP
* MyBatis
* JPA

### Frontend

* HTML
* CSS
* JavaScript
* jQuery
* Ajax
* Jinja

### Databases

* MySQL
* PostgreSQL
* Oracle
* Microsoft SQL Server

### AI, Audio and Computer Vision

* Librosa
* Demucs
* PyTorch
* torchcrepe
* Hugging Face Transformers
* Praat-Parselmouth
* OpenCV
* MediaPipe
* cvzone

### Development Tools

* Git
* GitHub
* VS Code
* Eclipse
* Maven
* Gradle
* Tomcat
* WebLogic

## Project Structure

```text
Portfolio/
├── project/
│   ├── templates/
│   ├── static/
│   ├── musicAI/
│   ├── eyecarex/
│   ├── handemote/
│   ├── models.py
│   ├── main.py
│   └── __init__.py
├── requirements.txt
├── run.py
├── .gitignore
└── README.md
```

## Local Installation

### 1. Clone the repository

```bash
git clone https://github.com/JeeaYou/Portfolio.git
cd Portfolio
```

### 2. Create a virtual environment

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install the dependencies

```bash
pip install -r requirements.txt
```

Some audio-analysis features may also require FFmpeg.

macOS:

```bash
brew install ffmpeg
```

Ubuntu or Debian:

```bash
sudo apt update
sudo apt install ffmpeg
```

### 4. Configure environment variables

Create a `.env` file in the project root.

```env
FLASK_SECRET_KEY=your-secret-key

MYSQL_USER=root
MYSQL_PASSWORD=your-mysql-password
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=project
```

The résumé email feature additionally requires:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@example.com
SMTP_PASSWORD=your-app-password
MAIL_FROM=your-email@example.com
```

Do not commit the `.env` file to GitHub.

### 5. Prepare the database

Create the MySQL database before starting the application.

```sql
CREATE DATABASE project
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

The application also requires its project, translation, résumé, and music-analysis tables and data.

### 6. Run the Flask application

```bash
python run.py
```

Open the following address in a browser:

```text
http://127.0.0.1:5001
```

## Project Purpose

This portfolio was developed to demonstrate more than a static collection of project screenshots.

It shows how I design and implement backend services, connect AI and audio-processing libraries to web applications, manage multilingual database content, process long-running analysis tasks, and present technical results through practical user interfaces.

My current goal is to continue developing backend and applied-AI services that turn technical models and data-processing functions into usable products.

## Author

**Jeea You**

Backend Developer focused on Java, Spring Boot, Python, Flask, and applied AI services.

* GitHub: [JeeaYou](https://github.com/JeeaYou)
* Repository: [Portfolio](https://github.com/JeeaYou/Portfolio)
