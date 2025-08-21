FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy application code
COPY . .

# Expose port
EXPOSE 5155

# Run the development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5155"]