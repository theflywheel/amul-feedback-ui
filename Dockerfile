FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py
COPY templates /app/templates
COPY static /app/static
COPY scripts /app/scripts
COPY data /app/data
COPY docs /app/docs

EXPOSE 5001

CMD ["/app/scripts/docker_entrypoint.sh"]
