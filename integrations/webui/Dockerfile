FROM ghcr.io/open-webui/open-webui:v0.13.4-slim
COPY integrations/webui/retail-* /app/build/static/
# Keep upstream branding and bundles. Only add the versioned local sidebar overlay.
RUN python -c "from pathlib import Path; p=Path('/app/build/index.html'); s=p.read_text(); marker='<script defer src=\"/static/retail-navigation.js\"></script>'; p.write_text(s.replace('</head>', marker + '</head>'))"
