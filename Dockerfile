FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/solver-web

COPY requirements.txt /app/solver-web/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/solver-web

CMD ["hypercorn", "--bind", "0.0.0.0:8080", "apps.api.app:app"]

