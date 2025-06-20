FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir .

# Use tini as init system to handle signals properly
RUN apt-get update && apt-get install -y tini
ENTRYPOINT ["/usr/bin/tini", "--"]

# Run the server
CMD ["python", "-m", "mcp_server_youtube.server"]
