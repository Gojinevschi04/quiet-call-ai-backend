"""Seed demo data for testing/demo purposes.

Creates:
- 2 admin users + 8 regular users (10 total)
- 20+ tasks across all statuses
- Call sessions + transcript log lines for completed/failed tasks
"""

import asyncio
from datetime import datetime, timedelta

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import engine
from app.modules.auth.service import AuthService
from app.modules.calls.models import CallSession, LogLine
from app.modules.calls.schema import Speaker
from app.modules.tasks.models import Task
from app.modules.tasks.schema import TaskStatus
from app.modules.templates.models import DialogTemplate
from app.modules.users.models import User
from app.modules.users.schema import UserRole

SECONDS_BETWEEN_LINES = 8

DEMO_USERS = [
    {
        "email": "ana.gojinevschi@isa.utm.md",
        "role": UserRole.ADMIN,
        "password": "admin1234",
        "phone_number": "+37360000001",
    },
    {
        "email": "annagojinevschi@gmail.com",
        "role": UserRole.ADMIN,
        "password": "admin1234",
        "phone_number": "+37360000010",
    },
    {
        "email": "ana@example.com",
        "role": UserRole.USER,
        "password": "password123",
        "phone_number": "+37360000002",
    },
    {
        "email": "john@example.com",
        "role": UserRole.USER,
        "password": "password123",
        "phone_number": "+37360000003",
    },
    {
        "email": "maria@example.com",
        "role": UserRole.USER,
        "password": "password123",
        "phone_number": "+37360000004",
    },
    {
        "email": "alex@example.com",
        "role": UserRole.USER,
        "password": "password123",
        "phone_number": "+37360000005",
    },
    {
        "email": "elena@example.com",
        "role": UserRole.USER,
        "password": "password123",
        "phone_number": "+37360000006",
    },
    {
        "email": "dmitri@example.com",
        "role": UserRole.USER,
        "password": "password123",
        "phone_number": "+37360000007",
    },
    {
        "email": "natalia@example.com",
        "role": UserRole.USER,
        "password": "password123",
        "phone_number": "+37360000008",
    },
    {
        "email": "victor@example.com",
        "role": UserRole.USER,
        "password": "password123",
        "phone_number": "+37360000009",
    },
]


async def seed_users(session: AsyncSession) -> dict[str, int]:
    """Returns dict of email → user_id."""
    user_ids: dict[str, int] = {}
    for user_data in DEMO_USERS:
        result = await session.exec(select(User).where(User.email == user_data["email"]))
        existing = result.first()
        if existing:
            print(f"  SKIP user: '{user_data['email']}' (id={existing.id})")
            user_ids[user_data["email"]] = existing.id
            continue
        user = User(
            email=user_data["email"],
            role=user_data["role"],
            hashed_password=AuthService.hash_password(user_data["password"]),
            phone_number=user_data["phone_number"],
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        print(f"  CREATED user: '{user.email}' (id={user.id}, role={user.role})")
        user_ids[user_data["email"]] = user.id
    return user_ids


def _get_template_id(
    template_map: dict[str, DialogTemplate], name: str, fallback: DialogTemplate
) -> int:
    return template_map.get(name, fallback).id


async def seed_tasks(session: AsyncSession, users: dict[str, int]) -> list[Task]:
    result = await session.exec(select(func.count()).select_from(Task))
    count = result.one()
    if count >= 10:
        print(f"  SKIP tasks: {count} tasks already exist")
        return []

    result = await session.exec(select(DialogTemplate))
    templates = list(result.all())
    if not templates:
        print("  SKIP tasks: no templates — run 'make db.seed' first")
        return []

    template_name_to_id: dict[str, int] = {t.name: t.id for t in templates}
    fallback_template_id = templates[0].id
    now = datetime.now()

    tasks_data = [
        # --- Ana (heavy user) ---
        {
            "phone": "+37322123456",
            "status": TaskStatus.COMPLETED,
            "tpl": "Make appointment",
            "user": "ana@example.com",
            "slots": {
                "preferred_date": "2026-03-20",
                "preferred_time": "10:00",
                "service_type": "dental",
                "patient_name": "Ana G.",
            },
            "summary": "Appointment confirmed for March 20 at 10:00 AM at City Dental Clinic.",
            "ago_days": 8,
        },
        {
            "phone": "+37322654321",
            "status": TaskStatus.COMPLETED,
            "tpl": "Confirm reservation",
            "user": "ana@example.com",
            "slots": {
                "reservation_id": "RES-2026-0042",
                "reservation_date": "2026-03-18",
                "guest_name": "Ana Gojinevschi",
            },
            "summary": "Reservation confirmed for March 18, 2 guests, at La Placinte.",
            "ago_days": 6,
        },
        {
            "phone": "+37322111222",
            "status": TaskStatus.FAILED,
            "tpl": "Make appointment",
            "user": "ana@example.com",
            "slots": {
                "preferred_date": "2026-03-15",
                "preferred_time": "14:00",
                "service_type": "eye exam",
                "patient_name": "Ana G.",
            },
            "error": "No available slots. Interlocutor suggested next week.",
            "ago_days": 4,
        },
        {
            "phone": "+37322333444",
            "status": TaskStatus.PENDING,
            "tpl": "Request information",
            "user": "ana@example.com",
            "slots": {
                "question_topic": "pricing for annual membership",
                "business_name": "FitLife Gym",
            },
            "ago_hours": 6,
        },
        {
            "phone": "+37322334455",
            "status": TaskStatus.COMPLETED,
            "tpl": "Follow-up call",
            "user": "ana@example.com",
            "slots": {
                "reference_number": "ORD-88712",
                "contact_name": "DHL Support",
                "follow_up_topic": "parcel delivery status",
            },
            "summary": "Parcel out for delivery, expected by 5 PM today.",
            "ago_days": 2,
        },
        {
            "phone": "+37322335566",
            "status": TaskStatus.COMPLETED,
            "tpl": "Prescription refill request",
            "user": "ana@example.com",
            "slots": {
                "patient_name": "Ana Gojinevschi",
                "prescription_number": "RX-204815",
                "pharmacy_name": "Farmacia Familiei",
            },
            "summary": "Refill ready for pickup tomorrow after 2 PM. No doctor approval needed.",
            "ago_days": 1,
        },
        {
            "phone": "+37322336677",
            "status": TaskStatus.SCHEDULED,
            "tpl": "Reschedule appointment",
            "user": "ana@example.com",
            "slots": {
                "original_date": "2026-03-22",
                "original_time": "10:00",
                "new_preferred_date": "2026-03-29",
                "new_preferred_time": "10:00",
                "booked_name": "Ana G.",
                "service_type": "dental cleaning",
            },
            "scheduled_future_days": 1,
            "ago_hours": 4,
        },
        # --- John ---
        {
            "phone": "+37322555666",
            "status": TaskStatus.COMPLETED,
            "tpl": "Cancel appointment",
            "user": "john@example.com",
            "slots": {
                "appointment_date": "2026-03-12",
                "appointment_time": "09:00",
                "booked_name": "John Smith",
                "reason": "travel conflict",
            },
            "summary": "Appointment cancelled. No cancellation fee applied.",
            "ago_days": 7,
        },
        {
            "phone": "+37322777888",
            "status": TaskStatus.COMPLETED,
            "tpl": "Follow-up call",
            "user": "john@example.com",
            "slots": {
                "reference_number": "TKT-20260301",
                "contact_name": "Support Team",
                "follow_up_topic": "laptop repair",
            },
            "summary": "Repair completed. Pickup available Mon-Fri 9-17.",
            "ago_days": 3,
        },
        {
            "phone": "+37322999000",
            "status": TaskStatus.SCHEDULED,
            "tpl": "Make appointment",
            "user": "john@example.com",
            "slots": {
                "preferred_date": "2026-03-25",
                "preferred_time": "16:00",
                "service_type": "haircut",
                "patient_name": "John S.",
            },
            "scheduled_future_days": 2,
            "ago_hours": 3,
        },
        {
            "phone": "+37322999111",
            "status": TaskStatus.FAILED,
            "tpl": "Request information",
            "user": "john@example.com",
            "slots": {
                "question_topic": "car service pricing",
                "business_name": "AutoPro Garage",
            },
            "error": "Line busy after 3 retries.",
            "ago_days": 1,
        },
        {
            "phone": "+37322999222",
            "status": TaskStatus.COMPLETED,
            "tpl": "Order status check",
            "user": "john@example.com",
            "slots": {"order_number": "ORD-55231", "customer_name": "John Smith"},
            "summary": "Order shipped via FAN Courier, tracking MD20260315, expected delivery March 18.",
            "ago_days": 2,
        },
        # --- Maria ---
        {
            "phone": "+37322100200",
            "status": TaskStatus.COMPLETED,
            "tpl": "Confirm reservation",
            "user": "maria@example.com",
            "slots": {
                "reservation_id": "HTL-5567",
                "reservation_date": "2026-04-01",
                "guest_name": "Maria P.",
            },
            "summary": "Hotel reservation confirmed: April 1-3, double room, breakfast included.",
            "ago_days": 9,
        },
        {
            "phone": "+37322300400",
            "status": TaskStatus.FAILED,
            "tpl": "Request information",
            "user": "maria@example.com",
            "slots": {
                "question_topic": "opening hours",
                "business_name": "Central Post Office",
            },
            "error": "Cancelled by user",
            "ago_days": 2,
        },
        {
            "phone": "+37322500600",
            "status": TaskStatus.COMPLETED,
            "tpl": "Make appointment",
            "user": "maria@example.com",
            "slots": {
                "preferred_date": "2026-03-22",
                "preferred_time": "11:30",
                "service_type": "consultation",
                "patient_name": "Maria P.",
            },
            "summary": "Consultation on March 22 at 11:30. Bring ID and insurance.",
            "ago_hours": 12,
        },
        {
            "phone": "+37322500700",
            "status": TaskStatus.COMPLETED,
            "tpl": "File a complaint",
            "user": "maria@example.com",
            "slots": {
                "complaint_subject": "Defective product",
                "complaint_details": "Received a broken coffee maker, order #CM-9921",
                "customer_name": "Maria P.",
            },
            "summary": "Complaint registered, ticket #CMP-3302. Replacement will be shipped within 3 business days.",
            "ago_days": 5,
        },
        # --- Alex ---
        {
            "phone": "+37322600700",
            "status": TaskStatus.COMPLETED,
            "tpl": "Make appointment",
            "user": "alex@example.com",
            "slots": {
                "preferred_date": "2026-03-19",
                "preferred_time": "09:30",
                "service_type": "visa interview",
                "patient_name": "Alex T.",
            },
            "summary": "Interview confirmed at US Embassy, March 19, 09:30. Arrive 30 min early.",
            "ago_days": 5,
        },
        {
            "phone": "+37322600800",
            "status": TaskStatus.PENDING,
            "tpl": "Cancel appointment",
            "user": "alex@example.com",
            "slots": {
                "appointment_date": "2026-03-28",
                "appointment_time": "15:00",
                "booked_name": "Alex T.",
                "reason": "scheduling conflict",
            },
            "ago_hours": 2,
        },
        {
            "phone": "+37322600900",
            "status": TaskStatus.COMPLETED,
            "tpl": "Service outage report",
            "user": "alex@example.com",
            "slots": {
                "account_number": "ACC-778844",
                "service_type": "internet",
                "issue_description": "No connection since 8 AM",
                "customer_name": "Alex T.",
            },
            "summary": "Known outage in Botanica district. Estimated restoration by 6 PM today. Ticket #OUT-1129.",
            "ago_days": 3,
        },
        # --- Elena ---
        {
            "phone": "+37322700900",
            "status": TaskStatus.COMPLETED,
            "tpl": "Insurance claim inquiry",
            "user": "elena@example.com",
            "slots": {
                "claim_number": "CLM-4420",
                "policyholder_name": "Elena V.",
                "claim_type": "auto",
            },
            "summary": "Claim approved. Payout of 12,500 MDL within 5 business days.",
            "ago_days": 3,
        },
        {
            "phone": "+37322701000",
            "status": TaskStatus.IN_PROGRESS,
            "tpl": "Make appointment",
            "user": "elena@example.com",
            "slots": {
                "preferred_date": "2026-03-26",
                "preferred_time": "14:00",
                "service_type": "notary",
                "patient_name": "Elena V.",
            },
            "ago_hours": 0,
        },
        # --- Dmitri ---
        {
            "phone": "+37322800100",
            "status": TaskStatus.COMPLETED,
            "tpl": "Confirm reservation",
            "user": "dmitri@example.com",
            "slots": {
                "reservation_id": "FLT-MD-123",
                "reservation_date": "2026-04-05",
                "guest_name": "Dmitri K.",
            },
            "summary": "Flight confirmed: April 5, Chisinau-Bucharest, 07:15, seat 12A.",
            "ago_days": 4,
        },
        {
            "phone": "+37322800200",
            "status": TaskStatus.PENDING,
            "tpl": "Payment reminder",
            "user": "dmitri@example.com",
            "slots": {
                "invoice_number": "INV-2026-0088",
                "amount_due": "4,200 MDL",
                "due_date": "2026-03-20",
                "company_name": "CloudHost SRL",
            },
            "ago_hours": 5,
        },
        # --- Natalia ---
        {
            "phone": "+37322900100",
            "status": TaskStatus.COMPLETED,
            "tpl": "Prescription refill request",
            "user": "natalia@example.com",
            "slots": {
                "patient_name": "Natalia R.",
                "prescription_number": "RX-331002",
                "pharmacy_name": "Farmacia Verde",
            },
            "summary": "Prescription requires doctor renewal. Pharmacy will fax request to Dr. Popescu.",
            "ago_days": 2,
        },
        {
            "phone": "+37322900200",
            "status": TaskStatus.COMPLETED,
            "tpl": "Order status check",
            "user": "natalia@example.com",
            "slots": {"order_number": "PKG-MD-7721", "customer_name": "Natalia R."},
            "summary": "Package held at customs. Need to present ID at Chisinau sorting center for pickup.",
            "ago_days": 6,
        },
        # --- Victor ---
        {
            "phone": "+37322910100",
            "status": TaskStatus.COMPLETED,
            "tpl": "Payment reminder",
            "user": "victor@example.com",
            "slots": {
                "invoice_number": "INV-2026-0055",
                "amount_due": "1,800 MDL",
                "due_date": "2026-03-10",
                "company_name": "Victor's Consulting",
            },
            "summary": "Client confirmed payment sent via bank transfer on March 9. Reference: TRF-40091.",
            "ago_days": 7,
        },
        {
            "phone": "+37322910200",
            "status": TaskStatus.FAILED,
            "tpl": "File a complaint",
            "user": "victor@example.com",
            "slots": {
                "complaint_subject": "Billing error",
                "complaint_details": "Charged twice for March subscription, account #VS-2200",
                "customer_name": "Victor M.",
            },
            "error": "Call dropped after 2 minutes. No complaint registered.",
            "ago_days": 1,
        },
        # --- Admin ---
        {
            "phone": "+37322700800",
            "status": TaskStatus.COMPLETED,
            "tpl": "Follow-up call",
            "user": "ana.gojinevschi@isa.utm.md",
            "slots": {
                "reference_number": "INC-001",
                "contact_name": "Twilio Support",
                "follow_up_topic": "API rate limits",
            },
            "summary": "Twilio confirmed: 100 concurrent calls on current plan. Upgrade available.",
            "ago_days": 10,
        },
        {
            "phone": "+37322800900",
            "status": TaskStatus.PENDING,
            "tpl": "Request information",
            "user": "ana.gojinevschi@isa.utm.md",
            "slots": {
                "question_topic": "enterprise pricing",
                "business_name": "OpenAI",
            },
            "ago_hours": 1,
        },
        {
            "phone": "+37322801000",
            "status": TaskStatus.COMPLETED,
            "tpl": "Make appointment",
            "user": "ana.gojinevschi@isa.utm.md",
            "slots": {
                "preferred_date": "2026-03-14",
                "preferred_time": "10:00",
                "service_type": "demo meeting",
                "patient_name": "Admin",
            },
            "summary": "Demo meeting scheduled with client at HQ, March 14 at 10 AM.",
            "ago_days": 6,
        },
    ]

    created_task_ids: list[tuple[int, str]] = []
    for task_data in tasks_data:
        task = Task(
            target_phone=task_data["phone"],
            status=task_data["status"],
            template_id=template_name_to_id.get(task_data["tpl"], fallback_template_id),
            user_id=users[task_data["user"]],
            slot_data=task_data["slots"],
            scheduled_time=(
                now + timedelta(days=task_data["scheduled_future_days"])
                if "scheduled_future_days" in task_data
                else None
            ),
            summary=task_data.get("summary"),
            error_reason=task_data.get("error"),
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        created_task_ids.append((task.id, task_data["status"]))

    print(f"  CREATED {len(created_task_ids)} demo tasks")
    return created_task_ids


DEMO_TRANSCRIPTS: dict[str, list[dict]] = {
    "appointment_success": [
        {
            "speaker": Speaker.AGENT,
            "text": "Hello, I'm calling on behalf of a patient to schedule an appointment.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Sure, what date were you looking at?",
            "intent": "request_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "We'd prefer March 20 at 10:00 AM if possible.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Let me check... Yes, that slot is available.",
            "intent": "confirmation",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Perfect. Can you confirm the address and any preparation needed?",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "City Dental Clinic, 45 Stefan cel Mare. No special preparation needed.",
            "intent": "provide_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Thank you very much. The appointment is confirmed for March 20 at 10 AM. "
            "Have a great day! [OBJECTIVE_ACHIEVED]",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "You too, goodbye!",
            "intent": "farewell",
        },
    ],
    "reservation_confirmed": [
        {
            "speaker": Speaker.AGENT,
            "text": "Hello, I'm calling to confirm reservation RES-2026-0042 for March 18.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "One moment please... Yes, I see it. Table for 2 at 7 PM.",
            "intent": "confirmation",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "That's correct. Is everything still on track?",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Yes, all confirmed. See you then!",
            "intent": "confirmation",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Wonderful, thank you. Goodbye! [OBJECTIVE_ACHIEVED]",
            "intent": None,
        },
    ],
    "appointment_failed": [
        {
            "speaker": Speaker.AGENT,
            "text": "Hello, I'd like to book an eye exam for March 15 at 2 PM.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "I'm sorry, we're fully booked on the 15th.",
            "intent": "rejection",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Is there anything available that week?",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "The earliest opening is March 22 at 3 PM.",
            "intent": "provide_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "I'll need to check with the patient. Thank you for the information. [OBJECTIVE_FAILED]",
            "intent": None,
        },
    ],
    "follow_up_success": [
        {
            "speaker": Speaker.AGENT,
            "text": "Hi, I'm calling about reference number ORD-88712 regarding a parcel delivery.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Let me pull that up... Yes, the parcel is currently out for delivery.",
            "intent": "provide_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "When can we expect it to arrive?",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "It should be delivered by 5 PM today.",
            "intent": "provide_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Great, thank you for the update! [OBJECTIVE_ACHIEVED]",
            "intent": None,
        },
    ],
    "cancellation_success": [
        {
            "speaker": Speaker.AGENT,
            "text": "Hello, I need to cancel an appointment on March 12 at 9 AM for John Smith.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "I see the appointment. May I ask the reason for cancellation?",
            "intent": "request_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "There's a travel conflict. Is there a cancellation fee?",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "No fee for cancellations more than 24 hours in advance. It's cancelled.",
            "intent": "confirmation",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Thank you very much. Have a good day! [OBJECTIVE_ACHIEVED]",
            "intent": None,
        },
    ],
}


async def seed_call_sessions(
    session: AsyncSession, tasks: list[tuple[int, str]]
) -> None:
    result = await session.exec(select(func.count()).select_from(CallSession))
    count = result.one()
    if count > 0:
        print(f"  SKIP call sessions: {count} already exist")
        return

    transcript_keys = list(DEMO_TRANSCRIPTS.keys())
    total_sessions = 0
    total_log_lines = 0

    result = await session.exec(
        select(Task.id, Task.status).where(
            Task.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED])
        )
    )
    eligible_tasks = result.all()

    for task_index, (task_id, _task_status) in enumerate(eligible_tasks):
        now = datetime.now()
        duration = 45 + (task_id * 7) % 120

        call_session = CallSession(
            task_id=task_id,
            start_time=now - timedelta(days=task_id % 10, hours=task_id % 5),
            duration=duration,
            recording_uri=f"https://api.twilio.com/2010-04-01/Accounts/DEMO/Recordings/RE{task_id:06d}.wav",
        )
        session.add(call_session)
        await session.commit()
        await session.refresh(call_session)
        total_sessions += 1

        template_key = transcript_keys[task_index % len(transcript_keys)]
        transcript_lines = DEMO_TRANSCRIPTS[template_key]

        transcript_start_time = call_session.start_time
        for line_index, transcript_line in enumerate(transcript_lines):
            log = LogLine(
                session_id=call_session.id,
                timestamp=transcript_start_time + timedelta(seconds=line_index * SECONDS_BETWEEN_LINES),
                speaker=transcript_line["speaker"],
                text=transcript_line["text"],
                detected_intent=transcript_line["intent"],
            )
            session.add(log)
            total_log_lines += 1

        await session.commit()

    print(f"  CREATED {total_sessions} call sessions with {total_log_lines} log lines")


async def seed() -> None:
    async with AsyncSession(engine) as session:
        print("\n--- Seeding demo users ---")
        users = await seed_users(session)

        print("\n--- Seeding demo tasks ---")
        tasks = await seed_tasks(session, users)

        print("\n--- Seeding call sessions & transcripts ---")
        await seed_call_sessions(session, tasks)

    print("\nDemo seed completed.")
    print("\nDemo accounts:")
    print("  Admin:      ana.gojinevschi@isa.utm.md / admin1234")
    print("  Admin:      annagojinevschi@gmail.com / admin1234")
    print("  Users:      ana@example.com / password123")
    print("              john@example.com / password123")
    print("              maria@example.com / password123")
    print("              alex@example.com / password123")
    print("              elena@example.com / password123")
    print("              dmitri@example.com / password123")
    print("              natalia@example.com / password123")
    print("              victor@example.com / password123")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
