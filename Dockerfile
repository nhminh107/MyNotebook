FROM python:3.12-slim
#Using uv in docker
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY BackEnd/pyproject.toml BackEnd/uv.lock ./BackEnd/

WORKDIR /app/BackEnd
RUN uv sync --locked --no-install-project

WORKDIR /app
COPY BackEnd ./BackEnd
COPY FrontEnd ./FrontEnd

ENV PATH="/app/BackEnd/.venv/bin:$PATH"
EXPOSE 8000

CMD ["uvicorn", "BackEnd.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
