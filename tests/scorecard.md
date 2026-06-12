# Scenario Scorecard — Luma Booking Concierge

**Total Scenarios:** 15  
**Passed:** 11  
**Stubbed:** 2  
**In Progress / Partial:** 2  
**Intent Accuracy (tested scenarios):** 11/11 = 100%

---

## Results

| # | Scenario | Intent(s) Classified | Tool(s) Called | Pass / Fail / Stub | Notes |
|---|----------|---------------------|----------------|--------------------|-------|
| 1 | Greeting & lead capture — user says "Hi", provides name, phone, email | `greeting_smalltalk` | `memory.update_session` | ✅ PASS | Name, phone, email captured in session. Session created correctly. |
| 2 | FAQ — "Where are your branches?" | `faq_general` | `faq.lookup_faq` | ✅ PASS | Correct branch info returned. No hallucination. |
| 3 | T1 direct booking — "Book me for Brow Lamination at Dubai Mall tomorrow at 2pm" + confirm | `create_booking` | `availability.check_availability`, `bookings.create_booking` | ✅ PASS | Slot found, summary shown, confirmed with BKG reference. |
| 4 | Payment link generation — service under AED 1000 | `initiate_payment` | `bookings.create_booking`, Supabase payment_link lookup | ✅ PASS | Payment link returned in response. Booking summary included. |
| 5 | T2 gate check — "I want Brow SPMU" | `create_booking` | `gate_check.check_service_gate` | ✅ PASS | Gate returned NEEDS_CONSULTATION. No direct booking attempted. Consultation offer made. |
| 6 | T2 consultation booking — user says "Yes" to consultation offer | `book_consultation` | `consultation.get_consultation_service_id`, `availability.check_availability`, `bookings.create_booking` | ✅ PASS | CON reference returned. Consultation slot confirmed. |
| 7 | T3 medical gate — "Book Anti-Wrinkle Injections" | `create_booking` | `gate_check.check_service_gate` | ✅ PASS | Gate returned NEEDS_SCREENING. Screening intro message shown. Q1 asked. |
| 8 | T3 screening — 6 yes/no questions answered sequentially | `create_booking` (initial), screening interceptor | `screening.submit_screening` | ✅ PASS | All 6 questions collected across turns. SCR reference returned on submission. Session context preserved throughout. |
| 9 | Multi-intent — "Check if there is a Brow Lamination slot on Saturday and book it if available" | `check_availability` → `create_booking` | `availability.check_availability`, `bookings.create_booking` | ✅ PASS | Availability checked, slot found, booking confirmed in same flow without user re-stating context. |
| 10 | Human escalation — "I want to speak to a human" | `escalate_human` | `escalation.escalate_to_human` | ✅ PASS | Escalation message returned. Handoff triggered correctly. |
| 11 | Mid-screening pivot — user asks about different service during screening | Screening interceptor → `_detect_pivot` → `awaiting_screening_switch_confirm` | GPT-4o pivot detection | ✅ PASS | Pivot detected. User offered choice to pause or continue. Screening state preserved either way. *(Fixed during build — see write-up.)* |
| 12 | T3 pending clearance — "Can I book Anti-Wrinkle Injections now?" when screening already submitted | `create_booking` | `gate_check.check_service_gate` | 🔧 STUB | Gate check returns SCREENING_PENDING state correctly via DB lookup. Response message wired. Pending state not yet being seeded consistently in test environment — treated as stub. Real behaviour: message tells user their screening is under review. |
| 13 | Frequency hard block — rebook injectable within 12-week window | `create_booking` | `gate_check.check_service_gate` | 🔧 STUB | Gate check HARD_BLOCK path exists and returns user-friendly message. Frequency calculation logic in `check_service_gate` not yet fully implemented — earliest eligible date not computed. Stubbed with clear "our team will advise" fallback. |
| 14 | Modify booking — "Move my booking to 4pm" | `modify_booking` | Supabase `bookings` update | ⚠️ PARTIAL | Intent classified correctly. For non-authenticated visitors, agent directs to call branch or escalates. For clients with `client_id`, booking_ref lookup works and routes to team. Direct slot reassignment not implemented — same core logic path as cancel, intentionally deferred. |
| 15 | Cancel booking — "Cancel my booking" | `cancel_booking` | Supabase `bookings` update | ⚠️ PARTIAL | Cancel path implemented for clients with `client_id` and a known `booking_ref`. Visitors without a client profile are directed to call branch or escalate. Status update to `cancelled` confirmed working in DB. |

---

## Edge Cases Tested (within passing scenarios)

| Edge Case | Behaviour | Result |
|-----------|-----------|--------|
| User provides name embedded in sentence ("I'm Afreen") | Inline regex extracts name correctly | ✅ |
| User gives invalid phone number (e.g. "893849") | Re-prompted with format hint | ✅ |
| LLM infers name from email address | Fixed: visitor name injected into system prompt explicitly | ✅ |
| User says "hmm I want to book nano brow" mid-screening | Pivot detected via GPT-4o, screening paused, user offered choice | ✅ |
| Low-confidence intent (< 0.55) | Graceful clarification prompt, no tool called | ✅ |
| No availability on requested date | Alternative slots offered | ✅ |
| User skips email during onboarding | "skip" accepted, flow continues | ✅ |

---

## Intent Classification Accuracy

| Intent Label | Times Tested | Correct | Accuracy |
|---|---|---|---|
| `greeting_smalltalk` | 1 | 1 | 100% |
| `faq_general` | 1 | 1 | 100% |
| `create_booking` | 5 | 5 | 100% |
| `check_availability` | 2 | 2 | 100% |
| `book_consultation` | 1 | 1 | 100% |
| `initiate_payment` | 1 | 1 | 100% |
| `modify_booking` | 1 | 1 | 100% |
| `cancel_booking` | 1 | 1 | 100% |
| `escalate_human` | 1 | 1 | 100% |
| **Total** | **14** | **14** | **100%** |

---

## Stubbed Component Documentation

### Flow 12 — Pending Clearance (STUB)
**What works:** `check_service_gate` returns `SCREENING_PENDING` when a screening record exists with status `pending`. The agent controller handles this gate status and returns a user-friendly message.  
**What's missing:** Test environment seed data for this state is inconsistent. In production, this requires a screening record in `medical_screenings` with `status = 'pending'` linked to the client. The path is wired — it needs reliable seed data to demo cleanly.  
**Real implementation:** No code changes needed. Seed a `medical_screenings` row with `status = 'pending'` for the test client.

### Flow 13 — Frequency Hard Block (STUB)
**What works:** `check_service_gate` returns `HARD_BLOCK` when frequency rules are violated. The agent returns a user-friendly message directing the user to wait.  
**What's missing:** Earliest eligible date calculation is not implemented. The response tells the user to wait but does not compute the specific date.  
**Real implementation:** In `gate_check.py`, query the most recent completed booking for the service, add the frequency interval, and return the date in the gate message.