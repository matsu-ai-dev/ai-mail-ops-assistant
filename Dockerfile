# ==== 1. ベース ====
FROM python:3.12-slim

# ==== 2. 環境変数 ====
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# ==== 3. 作業ディレクトリ ====
WORKDIR /app

# ==== 4. 依存パッケージ ====
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==== 5. アプリ本体 ====
COPY . .

# ==== 6. ポート ====
EXPOSE 8000 8501

# ==== 7. 起動コマンド ====
CMD ["bash","-c","uvicorn app.main:app --host 0.0.0.0 --port 8000 & streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0"]
