FROM python:3.11-alpine as builder
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
RUN apk add --no-cache postgresql-dev gcc python3-dev musl-dev
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --prefix=/install -r requirements.txt

FROM python:3.11-alpine
WORKDIR /app
RUN apk add --no-cache libpq
COPY --from=builder /install /usr/local
COPY . .
RUN adduser -D appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
