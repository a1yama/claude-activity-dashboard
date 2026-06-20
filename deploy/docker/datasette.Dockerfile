FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir "datasette>=0.65" "datasette-dashboards>=0.6"
ENV TZ=Asia/Tokyo
EXPOSE 8765
CMD ["datasette", "serve", "--immutable", "/data/claude_activity.db", \
     "--metadata", "/app/metadata.yml", \
     "--plugins-dir", "/app/plugins", \
     "--host", "0.0.0.0", "--port", "8765", \
     "--cors"]
