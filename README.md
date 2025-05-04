# Webhook Delivery Service

A FastAPI-based service for reliably receiving, queueing, and delivering webhooks with retry capabilities.

## 🚀 Features
- Create, manage, and monitor webhook subscriptions
- Webhook delivery with automatic retries using exponential backoff
- Event type filtering for targeted delivery
- Payload signature verification using HMAC-SHA256
- Detailed delivery status tracking
- Background processing with Redis Queue (RQ)
- **Fully Dockerized**

---

## 🛠 Tech Stack
- **FastAPI** (API framework with async support)
- **PostgreSQL** (Database for subscriptions and delivery logs)
- **Redis** (Task queue and subscription caching)
- **Redis Queue (RQ)** (Background task processing with retries)
- **Docker & Docker Compose** (Containerization)

---

## 🏗️ System Architecture

```
┌───────────────────┐       ┌────────────────────┐       ┌──────────────────┐
│                   │       │                    │       │                  │
│   Client/Webhook  ├──────►│   FastAPI (API)    ├──────►│   PostgreSQL     │
│      Producer     │       │   - Ingestion      │       │   - Subscriptions│
│                   │       │   - CRUD Endpoints │       │   - Delivery Logs│
└───────────────────┘       └─────────┬──────────┘       └──────────────────┘
                                      │
                                      │ Async Tasks
                                      ▼
┌───────────────────┐       ┌────────────────────┐
│                   │       │                    │
│   RQ Workers      │◄──────┤      Redis         │
│   - Delivery      │       │   - Task Queue     │
│   - Retries       │       │   - Cache          │
│   - Log Cleanup   │       │                    │
└─────────┬─────────┘       └────────────────────┘
          │
          │ HTTP POST
          ▼
┌───────────────────┐
│                   │
│   Target URL      │
│   (Subscriber)    │
│                   │
└───────────────────┘
```

---

## 📖 API Documentation
### 🔹 FastAPI Swagger UI
- Access at `http://localhost:8000/docs` when running locally

### 🔹 Endpoints

#### **Subscription Management**
| Method | Endpoint | Description |
|--------|---------|-------------|
| `POST` | `/subscriptions/` | Create a new webhook subscription |
| `GET` | `/subscriptions/` | List all subscriptions |
| `GET` | `/subscriptions/{id}` | Get subscription details |
| `PUT` | `/subscriptions/{id}` | Update a subscription |
| `DELETE` | `/subscriptions/{id}` | Delete a subscription |

#### **Webhook Processing**
| Method | Endpoint | Description |
|--------|---------|-------------|
| `POST` | `/webhooks/ingest/{subscription_id}` | Receive and process a webhook |

#### **Status Monitoring**
| Method | Endpoint | Description |
|--------|---------|-------------|
| `GET` | `/status/delivery/{delivery_id}` | Get delivery attempt details |
| `GET` | `/status/subscription/{subscription_id}` | Get recent delivery attempts for a subscription |
| `GET` | `/health` | System health check |

---

## 🛠 Local Setup

### 1️⃣ Prerequisites
- Install **Docker**: [Docker Install Guide](https://docs.docker.com/get-docker/)
- Install **Docker Compose**: [Docker Compose Install Guide](https://docs.docker.com/compose/install/)

### 2️⃣ Configure Environment
The project includes a .env file with default configurations:

```
# Database
DATABASE_URL=postgresql://user:password@db/webhooks
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_DB=webhooks

# Redis
REDIS_URL=redis://redis:6379/0

# Application settings
LOG_LEVEL=INFO
WEBHOOK_MAX_RETRIES=5
WEBHOOK_RETRY_DELAY=60
```

### 3️⃣ Run with Docker Compose
```sh
docker-compose up --build
```

The API will run on `http://localhost:8000`.

---

## 📡 API Usage Examples

### **1️⃣ Create a Webhook Subscription**
```sh
curl -X POST "http://localhost:8000/subscriptions/" \
     -H "Content-Type: application/json" \
     -d '{
           "target_url": "http://example.com/webhook",
           "secret": "my_secret_key",
           "event_types": ["user.created", "user.updated"]
         }'
```

### **2️⃣ Send a Webhook to a Subscription**
```sh
curl -X POST "http://localhost:8000/webhooks/ingest/{subscription_id}" \
     -H "Content-Type: application/json" \
     -d '{
           "event": "user.created",
           "data": {
             "id": 123,
             "name": "John Doe",
             "email": "john@example.com"
           }
         }'
```

### **3️⃣ Check Delivery Status**
```sh
curl -X GET "http://localhost:8000/status/delivery/{delivery_id}"
```

### **4️⃣ View Recent Deliveries for a Subscription**
```sh
curl -X GET "http://localhost:8000/status/subscription/{subscription_id}"
```

### **5️⃣ Check System Health**
```sh
curl -X GET "http://localhost:8000/health"
```

---

## Live Deployment: 

[Webhook Delivery Service](https://webhook-service-web.onrender.com/)

---

## 🏗️ Workflow

1. Create webhook subscription with target URL and optional secret
2. When an event is received, it's validated and stored
3. A background task is enqueued for delivery
4. The RQ worker attempts delivery with signature verification
5. Failed deliveries are retried automatically with exponential backoff
6. All attempts are logged and can be queried via API
7. Old delivery logs are automatically cleaned up after 72 hours

---

## 💻 Development

### Database Choice

PostgreSQL was an excellent choice for this webhook delivery service for several reasons:

- **Structured Data with Flexibility**: PostgreSQL handles both structured data (subscriptions) and flexible JSON data (webhook payloads) in one database.

- **Relational Model for Webhooks**: Our data naturally forms relationships (subscriptions → deliveries → delivery attempts). 

- **JSON Support**: The `event_types` and `payload` fields store JSON data directly, without needing to define every possible field in advance.

### Scaling for Production

As your webhook traffic grows, these PostgreSQL features become valuable:

1. **Indexing Strategy**: Indexes on frequently queried columns (`subscription_id`, `timestamp`) significantly speed up status lookups as volume grows.

2. **Read Replicas**: When query volume becomes high, read-only copies of the database can handle reporting/status queries while the main database focuses on new webhooks.

PostgreSQL provides the perfect balance of features for a this webhook delivery service that needs to handle relationships, flexible payloads, and time-based operations in a single, reliable system.

### Database Schema

#### **Subscriptions Table**
```sql
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY,
    target_url VARCHAR NOT NULL,
    secret VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    event_types JSON
);
```

#### **Deliveries Table**
```sql
CREATE TABLE deliveries (
    id UUID PRIMARY KEY,
    subscription_id UUID REFERENCES subscriptions(id),
    payload JSON NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR DEFAULT 'pending'
);
```

#### **Delivery Attempts Table**
```sql
CREATE TABLE delivery_attempts (
    id UUID PRIMARY KEY,
    delivery_id UUID REFERENCES deliveries(id),
    subscription_id UUID REFERENCES subscriptions(id),
    attempt_number INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    status_code INTEGER,
    success BOOLEAN NOT NULL,
    error VARCHAR
);
```

### Project Structure
```
.
├── app/
│   ├── api/
│   │   ├── status.py       # Status endpoints
│   │   ├── subscriptions.py # Subscription management
│   │   └── webhooks.py     # Webhook ingestion
│   ├── utils/
│   │   ├── logging.py      # Logging utilities
│   │   └── security.py     # Signature generation/verification
│   ├── worker/
│   │   └── tasks.py        # Background tasks with RQ
│   ├── crud.py            # Database operations
│   ├── database.py        # Database connection
│   ├── main.py           # Application entry point
│   ├── models.py         # SQLAlchemy models
│   └── schemas.py        # Pydantic schemas
├── .env                  # Environment variables
├── docker-compose.yml    # Docker Compose configuration
├── Dockerfile            # Docker image definition
└── requirements.txt      # Python dependencies
```

---

## ⚙️ Configuration Options

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:password@db/webhooks` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `LOG_LEVEL` | Application logging level | `INFO` |
| `WEBHOOK_MAX_RETRIES` | Maximum delivery attempts | `5` |
| `WEBHOOK_RETRY_DELAY` | Base delay between retries (seconds) | `60` |

---

## 📌 Design Choices & Assumptions

### Key Design Choices
- **FastAPI**: Chosen for async support and high concurrency during webhook ingestion
- **PostgreSQL**: Relational structure suits subscriptions (CRUD) and logs (time-series)
- **Redis**: Used for low-latency task queuing and caching subscription details
- **Redis Queue (RQ)**: Implements reliable background processing with built-in retry mechanisms
- **Exponential Backoff**: Prevents overwhelming failing endpoints with retry intervals of 10s, 30s, 60s, 5min, and 15min

### Assumptions
- **Traffic Volume**: System designed to handle ~5,000 webhooks/day
- **Security**: Webhook payloads are signed using HMAC-SHA256 when a secret is provided
- **Log Retention**: Delivery logs are stored for 72 hours for debugging purposes
- **Error Handling**: Network timeouts (10s) prevent workers from hanging indefinitely

### Scalability Considerations
- Horizontal scaling through additional RQ workers
- Database indexes on `subscription_id` and `timestamp` for performance
- Redis caching to reduce database load for subscription lookups
- Background job cleanup using APScheduler to prevent database bloat

---
## 📌 Cost analysis

| Component | Resource Specs | Free Tier Allowance | Cost |
|-----------|----------------|---------------------|------|
| Web Service | 256MB RAM, 1 shared vCPU | 750 hours/month (≈31 days) | $0 |
| Worker Service | 256MB RAM, 1 shared vCPU | 750 hours/month | $0 |
| PostgreSQL | Render (1 GB) | 1 free instance | $0 |
| Redis | Redis Cloud (30MB) | 1 free instance | $0 |

### Assumptions:
- 24x7 operation (744 hours/month)
- 5,000 webhooks/day (150k/month)
- 1.2 delivery attempts/webhook (180k total attempts)
- Moderate traffic patterns

This cost analysis demonstrates how the service can run at no cost during initial deployment by leveraging cloud provider free tiers.

---

## 📌 Credits where due
DeepSeek and CoPilot (dev related help)