FROM python:3.9-slim

WORKDIR /usr/local/app

COPY requirements.txt .
RUN pip install --no-input --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501

CMD ["sh", "-c", "streamlit run main.py"]
