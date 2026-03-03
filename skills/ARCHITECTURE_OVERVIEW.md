# Architecture Overview — Alça Finanças

**Last Updated:** 2026-02-27
**Architect:** Skills System Team
**Status:** Active

---

## Table of Contents

1. [Big Picture](#big-picture)
2. [System Context](#system-context)
3. [Container Diagram](#container-diagram)
4. [Data Flow](#data-flow)
5. [Security Flow](#security-flow)
6. [Deployment Architecture](#deployment-architecture)
7. [Sequence Diagrams](#sequence-diagrams)

---

## Big Picture

**Alça Finanças** is a personal finance SaaS platform built as a **modular monolith** with clear skill boundaries, enabling future extraction into microservices.

### Key Characteristics
- **Single-Tenant Today:** Each user has isolated data via `user_id` filtering
- **Multi-Tenant Ready:** Database schema and RLS designed for multi-tenancy
- **Skills-Based:** Logical boundaries enable independent evolution
- **Cloud-Native:** Containerized, stateless, horizontally scalable

### Technology Stack
- **Backend:** Python 3.9+, Flask 3.0, Supabase (PostgreSQL)
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS
- **Database:** Supabase PostgreSQL with Row Level Security (RLS)
- **Auth:** JWT + bcrypt (custom) OR Supabase Auth, OAuth (Google)
- **Infrastructure:** Docker, Docker Compose, Nginx/Traefik, GitHub Actions
- **Domain:** alcahub.cloud
- **VPS:** Ubuntu 24.04

---

## System Context

```mermaid
graph TB
    User[👤 User<br/>Web Browser]
    Admin[👤 Admin<br/>Admin Panel]
    EmailProvider[📧 Email Provider<br/>SMTP]
    GoogleOAuth[🔐 Google OAuth<br/>External]
    Supabase[🗄️ Supabase<br/>Database + Auth]

    System[🏦 Alça Finanças<br/>Personal Finance Platform]

    User -->|Uses| System
    Admin -->|Manages| System
    System -->|Sends emails| EmailProvider
    System -->|Authenticates via| GoogleOAuth
    System -->|Stores/retrieves data| Supabase

    style System fill:#4a90e2,stroke:#2c5f8d,stroke-width:3px,color:#fff
    style User fill:#95d5b2,stroke:#52b788,stroke-width:2px
    style Admin fill:#95d5b2,stroke:#52b788,stroke-width:2px
    style EmailProvider fill:#ffb703,stroke:#fb8500,stroke-width:2px
    style GoogleOAuth fill:#ffb703,stroke:#fb8500,stroke-width:2px
    style Supabase fill:#8338ec,stroke:#5a189a,stroke-width:2px,color:#fff
```

### External Systems
- **Supabase:** PostgreSQL database + Auth service
- **Google OAuth:** Social login
- **Email Provider:** Password recovery, notifications (SMTP)

### Users
- **End Users:** Manage personal finances
- **Admins:** Manage users, view logs, system stats

---

## Container Diagram

```mermaid
graph TB
    subgraph "User Devices"
        Browser[🌐 Web Browser<br/>React SPA]
    end

    subgraph "Alça Finanças Platform"
        Frontend[🎨 Frontend<br/>React + TypeScript + Vite<br/>Port 3000]
        Backend[⚙️ Backend API<br/>Flask + Python<br/>Port 8001]
        OpenClaw[🤖 OpenClaw Service<br/>Internal Microservice<br/>Port 18789]
        Chatbot[💬 Chatbot Service<br/>FastAPI<br/>Optional]
    end

    subgraph "Data Layer"
        Supabase[(🗄️ Supabase PostgreSQL<br/>Database + Auth)]
    end

    subgraph "External Services"
        Email[📧 Email SMTP]
        OAuth[🔐 Google OAuth]
    end

    Browser -->|HTTPS| Frontend
    Frontend -->|REST API| Backend
    Backend -->|SQL + Auth| Supabase
    Backend -->|Sends emails| Email
    Backend -->|OAuth flow| OAuth
    Backend -->|Internal API| OpenClaw
    Backend -->|Internal API| Chatbot

    style Frontend fill:#61dafb,stroke:#20232a,stroke-width:2px
    style Backend fill:#3776ab,stroke:#ffd43b,stroke-width:2px,color:#fff
    style Supabase fill:#8338ec,stroke:#5a189a,stroke-width:3px,color:#fff
    style OpenClaw fill:#52b788,stroke:#2d6a4f,stroke-width:2px
    style Chatbot fill:#52b788,stroke:#2d6a4f,stroke-width:2px
    style Browser fill:#95d5b2,stroke:#52b788,stroke-width:2px
    style Email fill:#ffb703,stroke:#fb8500,stroke-width:2px
    style OAuth fill:#ffb703,stroke:#fb8500,stroke-width:2px
```

### Containers

| Container | Technology | Purpose | Port |
|-----------|-----------|---------|------|
| **Frontend** | React 18 + Vite | Single-page application | 3000 |
| **Backend API** | Flask 3.0 | REST API, business logic | 8001 |
| **OpenClaw** | Python microservice | Internal automation | 18789 |
| **Chatbot** | FastAPI | AI chatbot (optional) | TBD |
| **Database** | Supabase PostgreSQL | Data persistence + Auth | External |

---

## Data Flow

### User Request Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Supabase

    User->>Frontend: Interact with UI
    Frontend->>Frontend: Validate input
    Frontend->>Backend: HTTP Request + JWT
    Backend->>Backend: Validate JWT
    Backend->>Backend: Authorize (user_id)
    Backend->>Supabase: Query (filtered by user_id)
    Supabase-->>Backend: Data
    Backend->>Backend: Transform/process
    Backend-->>Frontend: JSON Response
    Frontend->>Frontend: Update UI
    Frontend-->>User: Display result
```

### Key Points
1. **Frontend validates:** Client-side validation for UX
2. **Backend validates:** Server-side validation for security
3. **Authorization:** All queries filtered by `user_id` from JWT
4. **Transformation:** Business logic in backend services
5. **Stateless:** No session state on backend (JWT-based)

---

## Security Flow

### Authentication Flow (JWT)

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Supabase

    User->>Frontend: Enter email + password
    Frontend->>Backend: POST /api/auth/login
    Backend->>Supabase: Verify credentials
    Supabase-->>Backend: User data
    Backend->>Backend: Generate JWT (access + refresh)
    Backend-->>Frontend: {access_token, refresh_token}
    Frontend->>Frontend: Store tokens (localStorage)
    Frontend-->>User: Redirect to dashboard

    Note over Frontend,Backend: Subsequent requests include access_token

    Frontend->>Backend: GET /api/transactions<br/>Authorization: Bearer <token>
    Backend->>Backend: Validate JWT
    Backend->>Backend: Extract user_id from JWT
    Backend->>Supabase: SELECT * FROM transactions<br/>WHERE user_id = <id>
    Supabase-->>Backend: Transactions
    Backend-->>Frontend: JSON Response
```

### Authorization Layers

```mermaid
graph LR
    Request[HTTP Request] --> JWTCheck{JWT Valid?}
    JWTCheck -->|No| Reject401[401 Unauthorized]
    JWTCheck -->|Yes| ExtractUser[Extract user_id]
    ExtractUser --> RoleCheck{Admin Required?}
    RoleCheck -->|Yes| AdminCheck{is_admin?}
    AdminCheck -->|No| Reject403[403 Forbidden]
    AdminCheck -->|Yes| FilterData
    RoleCheck -->|No| FilterData[Filter by user_id]
    FilterData --> ExecuteQuery[Query Database]
    ExecuteQuery --> Response[Return Data]

    style Reject401 fill:#ff6b6b,stroke:#c92a2a,stroke-width:2px,color:#fff
    style Reject403 fill:#ff6b6b,stroke:#c92a2a,stroke-width:2px,color:#fff
    style Response fill:#51cf66,stroke:#2b8a3e,stroke-width:2px
```

### Security Layers
1. **Network:** HTTPS/TLS (production)
2. **Authentication:** JWT validation
3. **Authorization:** User-level filtering, admin role checks
4. **Input Validation:** Pydantic schemas
5. **Output Encoding:** JSON serialization
6. **Database:** RLS policies (backend bypasses with service_role)
7. **Rate Limiting:** Flask-Limiter on critical endpoints

---

## Deployment Architecture

### Production Deployment (VPS)

```mermaid
graph TB
    subgraph "Internet"
        Client[👤 User Browser]
    end

    subgraph "VPS Ubuntu 24.04 @ alcahub.cloud"
        ReverseProxy[🔀 Nginx/Traefik<br/>Port 80/443]

        subgraph "Docker Containers"
            FrontendContainer[🎨 Frontend<br/>nginx:alpine<br/>Port 3000]
            BackendContainer[⚙️ Backend<br/>Python + Gunicorn<br/>Port 8001]
            OpenClawContainer[🤖 OpenClaw<br/>Port 18789]
        end
    end

    subgraph "External Services"
        SupabaseCloud[(🗄️ Supabase<br/>Managed PostgreSQL)]
    end

    Client -->|HTTPS| ReverseProxy
    ReverseProxy -->|Proxy| FrontendContainer
    ReverseProxy -->|Proxy /api/*| BackendContainer
    BackendContainer -->|SQL| SupabaseCloud
    BackendContainer -->|Internal| OpenClawContainer

    style ReverseProxy fill:#4a90e2,stroke:#2c5f8d,stroke-width:3px,color:#fff
    style FrontendContainer fill:#61dafb,stroke:#20232a,stroke-width:2px
    style BackendContainer fill:#3776ab,stroke:#ffd43b,stroke-width:2px,color:#fff
    style SupabaseCloud fill:#8338ec,stroke:#5a189a,stroke-width:3px,color:#fff
    style OpenClawContainer fill:#52b788,stroke:#2d6a4f,stroke-width:2px
```

### CI/CD Pipeline

```mermaid
graph LR
    Dev[👨‍💻 Developer] -->|git push| GitHub[📦 GitHub]
    GitHub -->|Trigger| CI[🔄 GitHub Actions<br/>CI Workflow]

    CI --> Lint[🔍 Lint]
    CI --> Test[✅ Tests]
    CI --> Build[🏗️ Docker Build]
    CI --> Security[🔒 Security Scan]

    Lint --> CIPass{CI Pass?}
    Test --> CIPass
    Build --> CIPass
    Security --> CIPass

    CIPass -->|Yes| Deploy[🚀 Deploy Workflow]
    CIPass -->|No| Fail[❌ Fail]

    Deploy --> BuildImages[Build Docker Images]
    BuildImages --> SaveImages[Save .tar.gz]
    SaveImages --> SCPtoVPS[SCP to VPS]
    SCPtoVPS --> LoadImages[Load Images on VPS]
    LoadImages --> Restart[Restart Containers]
    Restart --> SmokeTests[🔥 Smoke Tests]
    SmokeTests --> Success[✅ Deployed]

    style CI fill:#4a90e2,stroke:#2c5f8d,stroke-width:2px,color:#fff
    style Deploy fill:#51cf66,stroke:#2b8a3e,stroke-width:2px
    style Fail fill:#ff6b6b,stroke:#c92a2a,stroke-width:2px,color:#fff
    style Success fill:#51cf66,stroke:#2b8a3e,stroke-width:2px
```

---

## Sequence Diagrams

### User Journey: Login

```mermaid
sequenceDiagram
    actor User
    participant Browser
    participant Frontend
    participant Backend
    participant Supabase

    User->>Browser: Navigate to /login
    Browser->>Frontend: Load Login Page
    Frontend-->>Browser: Render login form

    User->>Browser: Enter email + password
    Browser->>Frontend: Submit form
    Frontend->>Frontend: Client-side validation

    Frontend->>Backend: POST /api/auth/login<br/>{email, password}
    Backend->>Backend: Validate input (Pydantic)
    Backend->>Supabase: Check credentials
    Supabase-->>Backend: User record (if valid)

    alt Invalid credentials
        Backend-->>Frontend: 401 Unauthorized
        Frontend-->>Browser: Show error message
    else Valid credentials
        Backend->>Backend: Generate JWT (access + refresh)
        Backend-->>Frontend: 200 OK<br/>{access_token, refresh_token, user}
        Frontend->>Frontend: Store tokens (localStorage)
        Frontend->>Browser: Redirect to /dashboard
        Browser-->>User: Show dashboard
    end
```

### User Journey: Create Transaction

```mermaid
sequenceDiagram
    actor User
    participant Browser
    participant Frontend
    participant Backend
    participant Supabase

    User->>Browser: Navigate to /transactions
    Browser->>Frontend: Load Transactions Page
    Frontend->>Backend: GET /api/transactions<br/>Authorization: Bearer <token>
    Backend->>Backend: Validate JWT, extract user_id
    Backend->>Supabase: SELECT * FROM transactions<br/>WHERE user_id = <id>
    Supabase-->>Backend: Transaction list
    Backend-->>Frontend: 200 OK<br/>[{transaction}, ...]
    Frontend-->>Browser: Render transactions list

    User->>Browser: Click "New Transaction"
    Browser->>Frontend: Show transaction form

    User->>Browser: Fill form + submit
    Browser->>Frontend: Submit form data
    Frontend->>Frontend: Client-side validation

    Frontend->>Backend: POST /api/transactions<br/>{description, amount, type, ...}
    Backend->>Backend: Validate input (Pydantic)
    Backend->>Backend: Validate business rules<br/>(amount sign, date, etc.)

    alt Validation fails
        Backend-->>Frontend: 422 Unprocessable Entity<br/>{errors}
        Frontend-->>Browser: Show field errors
    else Validation passes
        Backend->>Supabase: INSERT INTO transactions<br/>(user_id, ...)
        Supabase-->>Backend: Created transaction
        Backend->>Backend: Update account balance (if applicable)
        Backend-->>Frontend: 201 Created<br/>{transaction}
        Frontend->>Frontend: Update UI (add to list)
        Frontend-->>Browser: Show success message
        Browser-->>User: Transaction created
    end
```

### Admin Journey: View User Details

```mermaid
sequenceDiagram
    actor Admin
    participant Browser
    participant Frontend
    participant Backend
    participant Supabase

    Admin->>Browser: Navigate to /admin/users/:id
    Browser->>Frontend: Load User Detail Page

    Frontend->>Backend: GET /api/users/:id/details<br/>Authorization: Bearer <token>
    Backend->>Backend: Validate JWT
    Backend->>Backend: Check is_admin flag

    alt Not admin
        Backend-->>Frontend: 403 Forbidden
        Frontend-->>Browser: Redirect to /dashboard
    else Is admin
        Backend->>Supabase: SELECT user details<br/>+ transaction stats<br/>+ account stats
        Supabase-->>Backend: User data + aggregates
        Backend-->>Frontend: 200 OK<br/>{user, stats}
        Frontend-->>Browser: Render user details
        Browser-->>Admin: Show user info
    end
```

### CSV Import Flow

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant Backend
    participant ImportService
    participant AccountDetector
    participant CategoryDetector
    participant Supabase

    User->>Frontend: Upload CSV file
    Frontend->>Backend: POST /api/transactions/import<br/>FormData(file)
    Backend->>Backend: Validate file (size, type)
    Backend->>ImportService: process_csv(file, user_id)

    ImportService->>ImportService: Parse CSV

    loop For each row
        ImportService->>ImportService: Validate row
        ImportService->>AccountDetector: detect_account(description)
        AccountDetector-->>ImportService: account_id or null

        alt Account not found
            ImportService->>Supabase: Create new account
            Supabase-->>ImportService: account_id
        end

        ImportService->>CategoryDetector: detect_category(description)
        CategoryDetector-->>ImportService: category_id or null

        ImportService->>ImportService: Build transaction object
    end

    ImportService->>Supabase: Bulk INSERT transactions
    Supabase-->>ImportService: Created count
    ImportService-->>Backend: {imported: N, errors: []}
    Backend-->>Frontend: 200 OK<br/>{imported, errors}
    Frontend-->>User: Show import summary
```

---

## Component Architecture

### Backend Layers

```mermaid
graph TB
    subgraph "Presentation Layer"
        Routes[Routes/Blueprints<br/>Flask routes]
    end

    subgraph "Business Logic Layer"
        Services[Services<br/>Business logic]
        Utils[Utils<br/>Helpers, decorators]
    end

    subgraph "Data Access Layer"
        Repositories[Repositories<br/>Data access]
        Schemas[Schemas<br/>Pydantic validation]
    end

    subgraph "External"
        Database[(Supabase<br/>PostgreSQL)]
    end

    Routes --> Services
    Routes --> Utils
    Services --> Repositories
    Services --> Schemas
    Repositories --> Database

    style Routes fill:#4a90e2,stroke:#2c5f8d,stroke-width:2px,color:#fff
    style Services fill:#52b788,stroke:#2d6a4f,stroke-width:2px
    style Repositories fill:#ffd43b,stroke:#3776ab,stroke-width:2px
    style Database fill:#8338ec,stroke:#5a189a,stroke-width:2px,color:#fff
```

### Frontend Architecture

```mermaid
graph TB
    subgraph "UI Layer"
        Pages[Pages<br/>Route pages]
        Components[Components<br/>Reusable UI]
    end

    subgraph "State Management"
        Contexts[Contexts<br/>Auth, Theme, etc.]
    end

    subgraph "Data Layer"
        API[API Utils<br/>HTTP client]
        Storage[Local Storage<br/>Tokens, cache]
    end

    Pages --> Components
    Pages --> Contexts
    Components --> Contexts
    Contexts --> API
    API --> Storage

    style Pages fill:#61dafb,stroke:#20232a,stroke-width:2px
    style Components fill:#61dafb,stroke:#20232a,stroke-width:2px
    style Contexts fill:#52b788,stroke:#2d6a4f,stroke-width:2px
    style API fill:#ffd43b,stroke:#3776ab,stroke-width:2px
```

---

## Technology Decisions

### Why Flask?
- Lightweight, flexible
- Mature ecosystem
- Easy to modularize with Blueprints
- Good for MVP and iterative development

### Why React?
- Component-based architecture
- Rich ecosystem
- TypeScript support
- Good developer experience

### Why Supabase?
- Managed PostgreSQL (no ops overhead)
- Built-in Auth
- Row Level Security
- Real-time subscriptions (future)
- Generous free tier

### Why Monolith (not microservices)?
- **Simplicity:** Single codebase, single deployment
- **Velocity:** Faster development, no inter-service communication overhead
- **Cost:** Lower infrastructure costs
- **Future-ready:** Skills architecture enables extraction when needed

---

## Scalability Considerations

### Current Bottlenecks
1. **Database:** Single Supabase instance (mitigated by managed service)
2. **Backend:** Single VPS instance (can scale horizontally)
3. **Frontend:** Static files (can use CDN)

### Scaling Strategy

#### Vertical Scaling (Phase 1)
- Upgrade VPS resources (CPU, RAM)
- Optimize database queries, add indexes
- Add Redis cache for frequently accessed data

#### Horizontal Scaling (Phase 2)
- Deploy multiple backend instances behind load balancer
- Use CDN for frontend static assets
- Read replicas for database (Supabase supports)

#### Service Extraction (Phase 3)
- Extract high-traffic skills into microservices:
  - `authentication` → Auth Service
  - `transactions` → Transactions Service
  - `reports` → Reports Service (async processing)
- Use message queue (RabbitMQ, Kafka) for async communication
- Implement API gateway

---

## Observability

### Monitoring Stack (Planned)
- **Logs:** Structured JSON logs → CloudWatch / Loki
- **Metrics:** Prometheus + Grafana
- **Traces:** OpenTelemetry → Jaeger / Tempo
- **Alerts:** Alertmanager → Slack / PagerDuty
- **Uptime:** UptimeRobot / Pingdom

### Key Dashboards
1. **System Health:** CPU, memory, disk, network
2. **API Performance:** Request rate, latency, error rate
3. **Business Metrics:** Transactions/day, users active, imports
4. **Security:** Failed auth attempts, rate limit hits

---

## Disaster Recovery

### Backup Strategy
- **Database:** Supabase automatic daily backups (7-day retention)
- **User Data Export:** `/api/auth/backup/export` endpoint
- **Recovery Time Objective (RTO):** <1 hour
- **Recovery Point Objective (RPO):** <24 hours

### Incident Response
1. **Detect:** Monitoring alerts
2. **Assess:** Check logs, metrics, traces
3. **Mitigate:** Rollback deployment, scale resources
4. **Resolve:** Fix root cause, deploy fix
5. **Postmortem:** Document incident, improve monitoring

---

## Future Architecture Vision

### Multi-Tenancy (Phase 4)
- Add `tenant_id` to all tables
- RLS policies filter by `tenant_id`
- Tenant-specific subdomains: `{tenant}.alcahub.cloud`
- Tenant management skill

### Real-Time Features (Phase 5)
- WebSockets via Supabase real-time
- Live transaction updates
- Collaborative budgeting

### Mobile App (Phase 6)
- React Native app (already scaffolded in `mobile/`)
- Shared API with web
- Offline-first with sync

---

**Next Review:** 2026-05-27 (Quarterly)

---

## References

- [Skills Registry](./SKILLS_REGISTRY.md)
- [Skills Dependency Graph](./SKILLS_DEPENDENCY_GRAPH.mmd)
- [Conventions](./CONVENTIONS.md)
- [ADR 0001: Skills Architecture](./ADRs/0001-skills-architecture.md)
