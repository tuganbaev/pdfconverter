# PDF Converter - Deployment Guide

## Prerequisites
- Docker and Docker Compose installed on your system
- `.env` file configured with your environment variables

## Environment Setup

Create a `.env` file in the project root with the following variables:

```bash
# Django settings
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Database (if using external DB)
DATABASE_URL=postgres://user:password@host:5432/dbname

# Email settings (optional)
EMAIL_HOST=smtp.your-provider.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@domain.com
EMAIL_HOST_PASSWORD=your-email-password

# Static/Media files (if using external storage)
# AWS_ACCESS_KEY_ID=your-aws-key
# AWS_SECRET_ACCESS_KEY=your-aws-secret
# AWS_STORAGE_BUCKET_NAME=your-bucket-name
```

## Building the Docker Image

```bash
# Build the image
docker build -t pdfconverter:latest .

# Or build with a specific tag
docker build -t pdfconverter:v1.0.0 .
```

## Running with Docker Compose

### Development
```bash
docker-compose up -d
```

### Production
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Running Standalone Docker Container

```bash
# Run the container
docker run -d \
  --name pdfconverter \
  -p 8000:8000 \
  --env-file .env \
  pdfconverter:latest

# With volume mounts for persistent storage
docker run -d \
  --name pdfconverter \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/media:/app/media \
  -v $(pwd)/staticfiles:/app/staticfiles \
  pdfconverter:latest
```

## Database Migration

If this is a fresh deployment, run migrations:

```bash
# Using docker-compose
docker-compose exec web python manage.py migrate

# Using standalone container
docker exec pdfconverter python manage.py migrate
```

## Creating Superuser

```bash
# Using docker-compose
docker-compose exec web python manage.py createsuperuser

# Using standalone container
docker exec -it pdfconverter python manage.py createsuperuser
```

## Health Check

The application includes a health check endpoint at `/health/` that returns:
```json
{"status": "healthy"}
```

Docker health checks run automatically every 30 seconds.

## Production Considerations

1. **Database**: The current setup uses SQLite. For production, consider using PostgreSQL or MySQL.

2. **Static Files**: Consider using a CDN or external storage (AWS S3, etc.) for static and media files.

3. **SSL/TLS**: Use a reverse proxy (nginx) with SSL certificates.

4. **Scaling**: The gunicorn configuration uses 3 workers. Adjust based on your server resources.

5. **Monitoring**: Add monitoring and logging solutions for production.

6. **Backups**: Implement regular database and media file backups.

## Updating the Application

```bash
# Pull new code and rebuild
git pull origin main
docker build -t pdfconverter:latest .

# Stop and recreate containers
docker-compose down
docker-compose up -d

# Run any new migrations
docker-compose exec web python manage.py migrate
```

## Troubleshooting

### Check container logs
```bash
# Docker compose
docker-compose logs web

# Standalone container
docker logs pdfconverter
```

### Access container shell
```bash
# Docker compose
docker-compose exec web bash

# Standalone container
docker exec -it pdfconverter bash
```

### Common Issues

1. **Static files not loading**: Run `docker exec pdfconverter python manage.py collectstatic`
2. **Database connection issues**: Check your DATABASE_URL in .env
3. **Permission errors**: Ensure proper file permissions for media directory