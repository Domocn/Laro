#!/bin/sh

# Replace placeholders in build artifacts with environment variables
if [ -d "/usr/share/nginx/html" ]; then
  echo "Injecting runtime environment variables..."
  find /usr/share/nginx/html -type f \( -name "*.html" -o -name "*.js" \) | xargs sed -i "s|__REACT_APP_OPENPANEL_URL__|${REACT_APP_OPENPANEL_URL:-}|g"
  find /usr/share/nginx/html -type f \( -name "*.html" -o -name "*.js" \) | xargs sed -i "s|__REACT_APP_OPENPANEL_CLIENT_ID__|${REACT_APP_OPENPANEL_CLIENT_ID:-}|g"
  # Also handle backend URL injection if it's used elsewhere (though arguably it should be handled similarly)
  find /usr/share/nginx/html -type f \( -name "*.html" -o -name "*.js" \) | xargs sed -i "s|%REACT_APP_BACKEND_URL%|${REACT_APP_BACKEND_URL:-}|g"
  find /usr/share/nginx/html -type f \( -name "*.html" -o -name "*.js" \) | xargs sed -i "s|%REACT_APP_REVENUECAT_WEB_API_KEY%|${REACT_APP_REVENUECAT_WEB_API_KEY:-}|g"
  find /usr/share/nginx/html -type f \( -name "*.html" -o -name "*.js" \) | xargs sed -i "s|%REACT_APP_CAST_APP_ID%|${REACT_APP_CAST_APP_ID:-}|g"
fi

# Execute the CMD
exec "$@"
