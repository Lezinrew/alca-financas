# Project Rules

This project is a financial SaaS platform.

Architecture principles:

- Backend: Flask API
- Bridge services: FastAPI
- Infrastructure: Docker Compose
- AI layer: OpenClaw Gateway

Rules:

1. Prefer modifying existing modules instead of creating new ones
2. Avoid introducing new frameworks
3. All endpoints must be RESTful
4. Code must be production-ready
5. Always handle errors explicitly
6. Avoid unnecessary dependencies
7. Keep functions small and testable