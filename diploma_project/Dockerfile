FROM python:3.11-slim

WORKDIR /app

# Встановлюємо залежності
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо код проекту
COPY . .

# Порти: Web UI, Transfer, Discovery, Multicast
EXPOSE 8080 6000 5000

# Змінні середовища з дефолтами
ENV NODE_ID=node1
ENV WEB_PORT=8080

CMD ["sh", "-c", "python app.py ${NODE_ID} ${WEB_PORT}"]
