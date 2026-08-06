FROM python:3.9-slim

WORKDIR /app

# Instala dependências do sistema necessárias para Matplotlib, C++ e fontes
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libfreetype6-dev \
    libpng-dev \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala dependências Python (Força Rebuild V1.0.5)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia os arquivos do projeto
COPY . .

# Comando de execução contínua 24/7
CMD ["python3", "main.py"]
