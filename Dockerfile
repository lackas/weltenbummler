FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
COPY weltenbummler ./weltenbummler
RUN pip install --no-cache-dir ".[serve]"
ENV WELTENBUMMLER_INSTANCE=/data
VOLUME /data
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--preload", "weltenbummler:create_app()"]
