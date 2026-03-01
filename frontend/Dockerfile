# Leichtgewichtiger nginx für ARM 32-Bit (Raspberry Pi 3B+)
FROM nginx:1.27-alpine

# Nginx-Konfiguration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Frontend-Dateien
COPY index.html /usr/share/nginx/html/
COPY static/    /usr/share/nginx/html/static/

EXPOSE 80
