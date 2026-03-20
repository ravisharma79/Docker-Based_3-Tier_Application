# ── Frontend Dockerfile ──────────────────────────────────────────────────────
FROM nginx:alpine

# Install gettext for envsubst
RUN apk add --no-cache gettext

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy static assets and config template
COPY index.html          /usr/share/nginx/html/index.html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Use envsubst to render the template at container startup, then launch nginx.
# We pass '$BACKEND_URL' (single-quoted) so envsubst substitutes ONLY that
# variable and leaves all other nginx $variables (like $host, $uri) untouched.
CMD ["/bin/sh", "-c", \
    "envsubst '$BACKEND_URL' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]

EXPOSE 80