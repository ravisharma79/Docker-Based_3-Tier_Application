# ── Backend Dockerfile (multi-stage, non-root) ───────────────────────────────

# ── Stage 1: builder — install dependencies ──────────────────────────────────
FROM python:3.12-alpine AS builder

WORKDIR /install

# Install build deps needed for mysql-connector-python
RUN apk add --no-cache gcc musl-dev

COPY requirements.txt .
RUN pip install --prefix=/install/deps --no-cache-dir -r requirements.txt


# ── Stage 2: runtime — lean final image ──────────────────────────────────────
FROM python:3.12-alpine AS runtime

# Create non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /install/deps /usr/local

# Copy application source
COPY app.py .

# Set ownership
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

ENV PORT=5000

EXPOSE 5000

CMD ["python", "app.py"]