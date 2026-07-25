# Jeea You — Backend & Applied AI Portfolio

A multilingual portfolio web application showcasing my professional backend development experience and applied AI projects.

The portfolio combines Java and Spring Boot experience with Python-based AI services, including music analysis, audio source separation, computer vision, multilingual content management, résumé generation, and interactive web interfaces.

## Portfolio Overview

The application includes:

* A project-focused home page
* An About page with experience and strengths
* A technical Skills page with category filtering
* A development Archive page
* A multilingual résumé page
* Korean, English, and Chinese language support
* Database-driven project, archive, and résumé content
* Desktop-focused web interface
* Modular Flask Blueprint architecture

## Main Projects

### 1. MusicAI — AI Music Analysis Platform

MusicAI is an AI-powered web application that analyses uploaded music files and presents technical audio information through an interactive dashboard.

#### Main Features

* MP3 and WAV file upload
* Original-audio analysis
* Vocal and instrumental source separation using Demucs
* Musical key and scale analysis
* Tempo and beat analysis
* Energy, RMS, and dynamic-range analysis
* Spectral-feature analysis
* Vocal pitch and vocal-range analysis
* Instrument classification
* Genre and mood estimation
* Audio-feature visualisation
* Long-running background analysis
* Per-file progress tracking
* Analysis cancellation
* Multilingual progress messages
* Database storage for analysis results

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
* FFmpeg
* HTML
* CSS
* JavaScript
* Chart.js

---

### 2. EyeCareX — Interactive Eye Health Tests

EyeCareX is a web-based application that provides interactive eye-health demonstrations using browser input and computer-vision technology.

#### Main Features

* Visual acuity test
* Colour-vision test
* Astigmatism test
* Cataract test
* Glaucoma test
* Macular-health test
* Camera-based interaction
* Face and hand tracking
* Multilingual interface
* Responsive test screens

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

HandEmote is a computer-vision application that detects hand landmarks and recognises gestures through a live camera feed.

#### Main Features

* Real-time hand detection
* Hand-landmark tracking
* Gesture recognition
* Camera-based interaction
* Responsive result display
* Multilingual page support

#### Technologies

* Python
* Flask
* OpenCV
* MediaPipe
* cvzone
* HTML
* CSS
* JavaScript

## Portfolio Features

### Multilingual Content

* Korean, English, and Chinese support
* Database-driven localisation
* Language-specific project and résumé content
* Multilingual analysis progress messages

### Résumé Management

* Database-driven résumé sections
* In-browser multilingual résumé editing
* PDF résumé generation using WeasyPrint
* Résumé download
* Résumé email delivery using SMTP
* Print-specific UK CV layout
* Responsive screen layout

### Project and Archive Management

* Dynamic project navigation
* Database-driven archive items
* Category filtering
* Sorting and pagination
* Responsive project cards
* Reusable portfolio components

## Technical Skills

### Backend

* Java
* Spring
* Spring Boot
* Python
* Flask
* REST API
* Flask-SQLAlchemy
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
* Jinja2
* Chart.js

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
* FFmpeg

### Development and Infrastructure

* Git
* GitHub
* VS Code
* Eclipse
* Maven
* Gradle
* Tomcat
* WebLogic
* SMTP
* WeasyPrint

## Application Architecture

The portfolio uses Flask Blueprints to separate the main portfolio pages and individual applications.

Core responsibilities include:

* Routing and template rendering
* Database-driven multilingual content
* Project and archive management
* Long-running audio-analysis workflows
* Analysis progress and cancellation handling
* Résumé editing and persistence
* PDF generation
* SMTP email delivery
* Responsive frontend rendering

## Project Structure

```text
Portfolio/
├── project/
│   ├── templates/
│   │   ├── components/
│   │   ├── mainpage.html
│   │   ├── about.html
│   │   ├── skills.html
│   │   ├── archive.html
│   │   └── resume.html
│   ├── static/
│   │   ├── assets/
│   │   │   ├── css/
│   │   │   ├── js/
│   │   │   └── images/
│   │   └── fonts/
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

## Main Routes

| Route              | Description             |
| ------------------ | ----------------------- |
| `/`                | Portfolio home page     |
| `/about`           | About and experience    |
| `/skills`          | Technical skills        |
| `/archive`         | Development archive     |
| `/resume`          | Multilingual résumé     |
| `/resume/update`   | Résumé update API       |
| `/resume/download` | Résumé PDF download API |
| `/resume/send`     | Résumé email API        |

Additional routes are provided by the MusicAI, EyeCareX, and HandEmote Blueprints.

## Local Installation

### 1. Clone the repository

```bash
git clone https://github.com/JeeaYou/Portfolio.git
cd Portfolio
```

### 2. Create and activate a virtual environment

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

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install system dependencies

MusicAI requires FFmpeg.

macOS:

```bash
brew install ffmpeg
```

Ubuntu or Debian:

```bash
sudo apt update
sudo apt install ffmpeg
```

Résumé PDF generation uses WeasyPrint. Depending on the operating system, additional libraries may be required.

macOS:

```bash
brew install weasyprint
```

Alternatively:

```bash
brew install glib pango cairo gdk-pixbuf libffi
```

## Environment Variables

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

## Database Setup

Create the MySQL database before starting the application.

```sql
CREATE DATABASE project
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

The application also requires tables and initial data for:

* Projects
* Navigation and translations
* Archive items
* Résumé content
* Music-analysis jobs
* Music-analysis results

## Run the Application

```bash
python run.py
```

Open the application in a browser:

```text
http://127.0.0.1:5001
```

## Project Purpose

This portfolio was created to demonstrate more than a collection of screenshots.

It shows how I:

* Design and implement backend services
* Build database-driven multilingual applications
* Integrate AI, audio-processing, and computer-vision libraries
* Manage long-running analysis tasks
* Store and present technical results
* Generate and deliver résumé documents
* Build responsive and reusable frontend components
* Organise a growing Flask application using modular architecture

My goal is to continue developing backend and applied AI services that turn technical models and data-processing functions into practical products.

## Author

**Jeea You**

Backend Developer focused on Java, Spring Boot, Python, Flask, SQL, and applied AI services.

* GitHub: [JeeaYou](https://github.com/JeeaYou)
* Repository: [Portfolio](https://github.com/JeeaYou/Portfolio)
