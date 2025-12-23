FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY init-db.sh /app/
RUN chmod +x /app/init-db.sh

COPY . .

RUN mkdir -p logs

RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

USER botuser

CMD ["/app/init-db.sh"]
