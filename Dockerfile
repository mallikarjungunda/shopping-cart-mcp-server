FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE THIRD_PARTY_NOTICES.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[mock]" && useradd -m app
USER app
EXPOSE 8000
CMD ["shopping-cart-mcp"]
