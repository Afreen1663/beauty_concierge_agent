# Luma Booking Concierge AI Agent

An AI-powered booking concierge for a luxury beauty and wellness brand in Dubai.

Luma acts as a conversational booking assistant that helps visitors and clients:

* Check service availability
* Create bookings
* Modify or cancel bookings
* Book consultations
* Complete medical screening workflows
* Receive payment links
* Ask FAQs about services, pricing, locations, and policies
* Escalate to a human receptionist when needed

The system uses FastAPI, OpenAI, and Supabase to deliver an end-to-end conversational booking experience.

---

# Live Deployment

### Production URL

https://beautyconciergeagent-production.up.railway.app/

### API Documentation

https://beautyconciergeagent-production.up.railway.app/docs

### Deployment Platform

* Railway
* FastAPI Backend
* Supabase Database
* OpenAI GPT-4o

---

# Key Features

## Visitor Onboarding

The chatbot automatically:

* Detects greetings
* Collects visitor details

  * Name
  * Phone Number
  * Email
* Creates a session
* Stores visitor information in Supabase

---

## Intelligent Intent Classification

The agent classifies user requests into workflows such as:

* Check Availability
* Create Booking
* Modify Booking
* Cancel Booking
* FAQ
* Consultation Booking
* Medical Screening
* Payment Request
* Human Escalation

---

## Service Tier Logic

### T1 — Standard Beauty Services

Examples:

* Brow Lamination
* Brow Tint
* Lash Tint
* Waxing

Workflow:

Availability → Booking → Payment Link → Confirmation

No pre-booking requirements.

---

### T2 — Semi-Permanent Makeup (SPMU)

Examples:

* Brow SPMU
* Lip Blush
* Nano Brows

Workflow:

Consultation Required → Patch Test → Clearance → Booking

The chatbot automatically checks if valid patch-test clearance exists before allowing booking.

---

### T3 — Medical / Injectable Services

Examples:

* Anti-Wrinkle Injections
* Lip Filler
* Thread Lift

Workflow:

Medical Screening → Clinical Review → Clearance → Booking

The chatbot asks six screening questions and stores responses in Supabase for practitioner review.

---

## Multi-Intent Handling

Example:

User:

"Check if there is a Brow Lamination slot on Saturday and book it if available."

The agent:

1. Checks availability
2. Applies gate checks
3. Books the appointment
4. Generates confirmation

All within a single conversation flow.

---

## Payment Rules

The system automatically applies payment policies:

| Booking Type        | Payment Rule         |
| ------------------- | -------------------- |
| Service ≤ AED 1,000 | Full payment upfront |
| Service > AED 1,000 | 20% deposit          |
| Package Booking     | 100% upfront         |
| Consultation        | Free                 |

Stripe is currently running in test mode using mock payment links.

---

## Human Escalation

The chatbot can escalate conversations when:

* User requests a human
* Confidence is low
* Request is out of scope
* System errors occur

---

# Technology Stack

| Layer           | Technology                    |
| --------------- | ----------------------------- |
| Backend API     | FastAPI                       |
| AI Engine       | OpenAI GPT-4o                 |
| Database        | Supabase PostgreSQL           |
| Hosting         | Railway                       |
| Payments        | Stripe Test Mode              |
| Session Storage | In-Memory + Supabase          |
| Frontend        | HTML / JavaScript Chat Widget |

---

# Project Structure

```text
beauty_concierge_agent/
│
├── api/
│   ├── main.py
│   ├── agent_controller.py
│   ├── intent_classifier.py
│   ├── response_generator.py
│   ├── memory.py
│   ├── database.py
│   ├── escalation.py
│   └── tools/
│       ├── availability.py
│       ├── bookings.py
│       ├── consultation.py
│       ├── faq.py
│       ├── gate_check.py
│       └── screening.py
│
├── db/
│   ├── schema.sql
│   └── seed_data.sql
│
├── requirements.txt
├── .env.example
└── README.md
```

---

# Requirements

* Python 3.11+
* OpenAI API Key
* Supabase Project
* Git
* Railway Account (for deployment)

---

# Installation

## Clone Repository

```bash
git clone https://github.com/Afreen1663/beauty_concierge_agent.git

cd beauty_concierge_agent
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Environment Variables

Create a `.env` file:

```env
OPENAI_API_KEY=your_openai_key

SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_service_role_key

STRIPE_SECRET_KEY=your_stripe_test_key
STRIPE_TEST_MODE=true

SESSION_SECRET=your_secret

ESCALATION_WEBHOOK_URL=http://localhost:8000/mock-escalation

DEFAULT_BRANCH_ID=your_default_branch_id
```

---

# Database Setup

This project uses Supabase PostgreSQL.

## Step 1 — Create Supabase Project

Create a new Supabase project and obtain:

* SUPABASE_URL
* SUPABASE_SERVICE_ROLE_KEY

---

## Step 2 — Run Schema Script

Open:

Supabase Dashboard → SQL Editor

Run:

```sql
db/schema.sql
```

This creates:

* services
* branches
* artists
* time_slots
* bookings
* sessions
* agent_logs
* medical_screenings
* spmu_clearances
* faqs

---

## Step 3 — Run Seed Data Script

After schema creation, run:

```sql
db/seed_data.sql
```

This populates:

* Branches
* Services
* Artists
* FAQ Data
* Consultation Records
* Screening Records
* Availability Slots

The seed script generates appointment availability required for demo scenarios.

---

# Running Locally

Start FastAPI:

```bash
uvicorn api.main:app --reload --port 8000
```

Application:

```text
http://localhost:8000
```

Swagger API Docs:

```text
http://localhost:8000/docs
```

---

# API

## POST /chat

Send a message to the booking assistant.

### Request

```json
{
  "session_id": "abc123",
  "message": "I want to book Brow Lamination"
}
```

### Response

```json
{
  "response": "We have availability this Saturday at 2:00 PM.",
  "session_id": "abc123"
}
```

---

# Logging

Every conversation turn is recorded in:

```text
agent_logs
```

including:

* User Message
* Intent
* Confidence Score
* Extracted Entities
* Tool Called
* Tool Result
* Agent Response
* Latency

This enables debugging and evaluation of agent performance.

---

# Demo Scenarios

The chatbot supports:

* Greeting & Lead Capture
* FAQ Questions
* T1 Direct Booking
* T2 Consultation Booking
* T2 Clearance Validation
* T3 Medical Screening
* Payment Link Generation
* Booking Modification
* Booking Cancellation
* Frequency Checks
* Multi-Intent Requests
* Human Escalation

---

# Known Limitations

* Stripe payments are mocked using test links.
* WhatsApp integration is currently sandbox/stubbed.
* Session state is partially stored in memory.
* Medical clearance approval is manually simulated.
* Patch-test completion is simulated through seeded records.

---

# Deployment

The application is deployed on Railway.

Production URL:

https://beautyconciergeagent-production.up.railway.app/

API Documentation:

https://beautyconciergeagent-production.up.railway.app/docs

---

# Author

Built as a Proof-of-Concept AI Booking Concierge for a luxury beauty and wellness brand using FastAPI, OpenAI, Supabase, and Railway.
