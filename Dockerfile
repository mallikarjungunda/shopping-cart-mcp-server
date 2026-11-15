FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE THIRD_PARTY_NOTICES.md ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd -m app
USER app
# The default bind address is loopback, which is unreachable from outside a container.
ENV HOST=0.0.0.0
EXPOSE 8000
CMD ["shopping-cart-mcp"]
