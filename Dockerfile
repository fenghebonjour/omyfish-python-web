FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Runs as root by default otherwise — a container breakout or dependency RCE would have full
# root inside the container for no benefit, since gunicorn doesn't need it to bind :8080
# (BACKLOG.md item G, WEAKNESS_AUDIT.md §1.4).
RUN addgroup --system --gid 1001 django && adduser --system --uid 1001 --gid 1001 django
USER django

EXPOSE 8080

CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8080"]
