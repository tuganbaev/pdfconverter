# CLAUDE.md

This file provides guidance to Claude Code when working with the PDF Converter project.

## Project Overview

PDF Converter is a Django web application that allows users to upload various document formats and convert them to PDF. The project runs as a single Docker container with all application files inside, while media and static files are written directly to the host server.

## Tech Stack

- **Backend**: Django 5.1.2, Python 3.12
- **Database**: PostgreSQL (can be containerized or external)
- **Storage**: Host filesystem for media/static files
- **Deployment**: Single Docker container
- **Frontend**: Bootstrap 5, vanilla JavaScript

## Architecture

### Single Container Design
- All application code, templates, and dependencies run inside one container
- Media and static files are mounted as volumes from host filesystem
- Container has direct write access to server's media/static directories
- No external object storage dependencies

## Project Structure

```
pdfconverter/
├── pdfconverter/          # Main Django project
│   ├── settings.py        # Django configuration
│   ├── urls.py           # Main URL routing
│   └── wsgi.py           # WSGI application
├── document/             # Core app for document handling
│   ├── models.py         # Document model with file fields
│   ├── views.py          # Upload, convert, download views
│   ├── urls.py           # Document-specific URLs
│   └── admin.py          # Admin interface
├── templates/            # HTML templates (inside container)
├── static/              # Static files (mounted from host)
├── media/               # Media files (mounted from host)
├── requirements.txt     # Python dependencies
├── Dockerfile           # Single container definition
├── docker-compose.yml   # Container orchestration
└── .env                 # Environment variables
```

## Volume Mounts

```yaml
volumes:
  - /var/www/pdfconverter/media:/app/media    # Media files on host
  - /var/www/pdfconverter/static:/app/static  # Static files on host
```

## Core Features

- **File Upload**: Support for PDF, DOCX, TXT, images
- **Document Management**: List, view, download documents
- **PDF Conversion**: Convert documents to PDF format
- **User Management**: Optional user authentication
- **Admin Interface**: Django admin for document management

## Development Commands

```bash
# Build and run container
docker-compose up --build

# Django management commands
docker exec -it pdfconverter python manage.py makemigrations
docker exec -it pdfconverter python manage.py migrate
docker exec -it pdfconverter python manage.py collectstatic --noinput

# Production deployment
docker-compose -f docker-compose.prod.yml up -d
```

## Environment Configuration

All configuration via `.env` file:
- Database connection settings
- Django secret key and debug settings
- Media and static file paths
- Allowed hosts configuration

## Key Models

- **Document**: Main model with file fields, conversion status, metadata
- Uses UUID primary keys for security
- FileField saves directly to mounted media volume

## Deployment Notes

### Single Container Benefits
- Simplified deployment and maintenance
- All dependencies contained in one image
- Easy backup and restoration
- Direct filesystem access for media/static

### Host Server Setup
```bash
# Create directories on host
mkdir -p /var/www/pdfconverter/media
mkdir -p /var/www/pdfconverter/static
chmod 755 /var/www/pdfconverter/media
chmod 755 /var/www/pdfconverter/static
```

### Container Configuration
- Runs as non-root user for security
- Has write permissions to mounted volumes
- Nginx/Apache on host serves static files directly
- Container handles Django application logic only

## File Processing

- Supported formats: PDF, DOCX, DOC, TXT, JPG, JPEG, PNG
- Maximum file size: 10MB
- Conversion handled via PyPDF2 and ReportLab libraries
- Files stored securely with UUID-based naming

## Development Notes

- Uses django-storages for S3-compatible file handling
- Bootstrap 5 for responsive UI
- Simple upload/convert/download workflow
- No complex user authentication by default (can be added)
- Admin interface for document management