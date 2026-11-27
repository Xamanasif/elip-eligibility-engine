FROM node:22-slim AS web
WORKDIR /build
COPY web/package*.json ./
RUN npm ci
COPY web/tsconfig.json web/index.html ./
COPY web/src ./src
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY elip ./elip
COPY data ./data
COPY --from=web /build/dist ./web/dist
EXPOSE 8765
CMD ["python","-m","uvicorn","elip.app:app","--host","0.0.0.0","--port","8765"]
