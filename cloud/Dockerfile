FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

COPY alertam_cloud ./alertam_cloud

EXPOSE 8080

USER 10001:10001

HEALTHCHECK --interval=10s --timeout=3s --start-period=2s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/healthz', timeout=2).read()"

CMD ["python", "-m", "alertam_cloud"]
