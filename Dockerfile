FROM python:3.11

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    lsb-release \
    ca-certificates \
    apt-transport-https \
    && rm -rf /var/lib/apt/lists/*

RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg && \
    apt-get update && apt-get install -y google-cloud-cli

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY data /app/data
COPY . .


RUN mkdir -p instance

EXPOSE 5000

RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
