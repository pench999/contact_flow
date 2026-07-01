FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/data /app/session_data

COPY . /app

ENV PORT=8080
ENV CONTACT_FLOW_DB_FILE=/app/data/contact_chart.db
ENV SESSION_DATA_DIR=/app/session_data

EXPOSE 8080

CMD ["sh", "-c", "python -c 'import contact; contact.init_db()' && gunicorn --bind 0.0.0.0:${PORT} --workers ${WEB_CONCURRENCY:-2} contact:app"]
