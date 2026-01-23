# Multi-stage build for frontend
FROM node:18-alpine AS build

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install all dependencies (including dev dependencies for build)
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage with Nginx
FROM nginx:alpine

# Copy built files from build stage
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

# # Create a simple nginx config for SPA
# RUN echo 'server { \
#     listen 80; \
#     server_name localhost; \
#     root /usr/share/nginx/html; \
#     index index.html; \
#     location / { \
#         try_files $uri $uri/ /index.html; \
#     } \
# }' > /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
