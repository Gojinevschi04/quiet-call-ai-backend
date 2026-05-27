"""Seed demo data for testing/demo purposes.

Creates:
- 2 admin users + 8 regular users (10 total)
- 20+ tasks across all statuses
- Call sessions + transcript log lines for completed/failed tasks
"""

import asyncio
from datetime import datetime, timedelta

from sqlmodel import select
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
from app.scripts.constants import (
    ADMIN_EMAIL_PRIMARY,
    ADMIN_EMAIL_SECONDARY,
    ADMIN_PASSWORD,
    BASE_CALL_DURATION_SECONDS,
    CALL_DURATION_VARIATION_FACTOR,
    DEMO_RECORDING_URL_TEMPLATE,
    MAX_CALL_DURATION_VARIATION,
    SECONDS_BETWEEN_TRANSCRIPT_LINES,
    USER_PASSWORD,
)

DEMO_USERS = [
    {
        "email": ADMIN_EMAIL_PRIMARY,
        "role": UserRole.ADMIN,
        "password": ADMIN_PASSWORD,
        "phone_number": "+37360000001",
    },
    {
        "email": ADMIN_EMAIL_SECONDARY,
        "role": UserRole.ADMIN,
        "password": ADMIN_PASSWORD,
        "phone_number": "+37360000010",
    },
    {
        "email": "ana@example.com",
        "role": UserRole.USER,
        "password": USER_PASSWORD,
        "phone_number": "+37360000002",
    },
    {
        "email": "john@example.com",
        "role": UserRole.USER,
        "password": USER_PASSWORD,
        "phone_number": "+37360000003",
    },
    {
        "email": "maria@example.com",
        "role": UserRole.USER,
        "password": USER_PASSWORD,
        "phone_number": "+37360000004",
    },
    {
        "email": "alex@example.com",
        "role": UserRole.USER,
        "password": USER_PASSWORD,
        "phone_number": "+37360000005",
    },
    {
        "email": "elena@example.com",
        "role": UserRole.USER,
        "password": USER_PASSWORD,
        "phone_number": "+37360000006",
    },
    {
        "email": "dmitri@example.com",
        "role": UserRole.USER,
        "password": USER_PASSWORD,
        "phone_number": "+37360000007",
    },
    {
        "email": "natalia@example.com",
        "role": UserRole.USER,
        "password": USER_PASSWORD,
        "phone_number": "+37360000008",
    },
    {
        "email": "victor@example.com",
        "role": UserRole.USER,
        "password": USER_PASSWORD,
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


def _get_template_id(template_map: dict[str, DialogTemplate], name: str, fallback: DialogTemplate) -> int:
    return template_map.get(name, fallback).id


async def seed_tasks(session: AsyncSession, users: dict[str, int]) -> list[Task]:
    result = await session.exec(select(DialogTemplate))
    templates = list(result.all())
    if not templates:
        print("  SKIP tasks: no templates — run 'make db.seed' first")
        return []

    existing_phones_result = await session.exec(select(Task.target_phone))
    existing_phones = set(existing_phones_result.all())

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
            "status": TaskStatus.PENDING,
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
        # --- Extra Ana tasks (mostly RO, a few EN, 1 RU) — ready to simulate ---
        {
            "phone": "+37322801010",
            "status": TaskStatus.PENDING,
            "tpl": "Programare la medic",
            "user": "ana.gojinevschi@isa.utm.md",
            "slots": {
                "preferred_date": "2026-04-28",
                "preferred_time": "10:30",
                "service_type": "consultație stomatologică",
                "patient_name": "Ana Gojinevschi",
            },
            "ago_hours": 1,
        },
        {
            "phone": "+37322801011",
            "status": TaskStatus.PENDING,
            "tpl": "Confirmare rezervare",
            "user": "ana.gojinevschi@isa.utm.md",
            "slots": {
                "reservation_id": "REZ-2026-4410",
                "reservation_date": "2026-04-30",
                "guest_name": "Ana Gojinevschi",
            },
            "ago_hours": 2,
        },
        {
            "phone": "+37322801012",
            "status": TaskStatus.PENDING,
            "tpl": "Solicitare informații",
            "user": "ana.gojinevschi@isa.utm.md",
            "slots": {
                "question_topic": "prețul unui abonament lunar",
                "business_name": "FitLife Chișinău",
            },
            "ago_hours": 3,
        },
        {
            "phone": "+37322801013",
            "status": TaskStatus.PENDING,
            "tpl": "Anulare programare",
            "user": "ana.gojinevschi@isa.utm.md",
            "slots": {
                "appointment_date": "2026-04-25",
                "appointment_time": "15:00",
                "booked_name": "Ana Gojinevschi",
                "reason": "conflict de program",
            },
            "ago_hours": 4,
        },
        {
            "phone": "+37322801014",
            "status": TaskStatus.PENDING,
            "tpl": "Reprogramare programare",
            "user": "ana.gojinevschi@isa.utm.md",
            "slots": {
                "original_date": "2026-04-29",
                "original_time": "11:00",
                "new_preferred_date": "2026-05-03",
                "new_preferred_time": "14:00",
                "booked_name": "Ana Gojinevschi",
                "service_type": "control cardiologic",
            },
            "ago_hours": 5,
        },
        {
            "phone": "+37322801015",
            "status": TaskStatus.SCHEDULED,
            "tpl": "Reamintire plată",
            "user": "ana.gojinevschi@isa.utm.md",
            "slots": {
                "invoice_number": "FAC-2026-0310",
                "amount_due": "1800 MDL",
                "due_date": "2026-05-01",
                "company_name": "Atelier Design SRL",
            },
            "scheduled_future_days": 1,
        },
        {
            "phone": "+37322801016",
            "status": TaskStatus.SCHEDULED,
            "tpl": "Apel de revenire",
            "user": "ana.gojinevschi@isa.utm.md",
            "slots": {
                "reference_number": "TCK-99012",
                "contact_name": "Moldcell Support",
                "follow_up_topic": "migrare abonament business",
            },
            "scheduled_future_days": 2,
        },
        {
            "phone": "+37322801017",
            "status": TaskStatus.COMPLETED,
            "tpl": "Programare la medic",
            "user": "ana.gojinevschi@isa.utm.md",
            "slots": {
                "preferred_date": "2026-04-10",
                "preferred_time": "09:30",
                "service_type": "control oftalmologic",
                "patient_name": "Ana Gojinevschi",
            },
            "ago_days": 12,
        },
        {
            "phone": "+37322801018",
            "status": TaskStatus.COMPLETED,
            "tpl": "Confirmare rezervare",
            "user": "ana.gojinevschi@isa.utm.md",
            "slots": {
                "reservation_id": "REZ-2026-3390",
                "reservation_date": "2026-04-12",
                "guest_name": "Ana G.",
            },
            "ago_days": 10,
        },
        {
            "phone": "+37322801019",
            "status": TaskStatus.FAILED,
            "tpl": "Anulare programare",
            "user": "ana.gojinevschi@isa.utm.md",
            "slots": {
                "appointment_date": "2026-04-05",
                "appointment_time": "16:00",
                "booked_name": "Ana Gojinevschi",
                "reason": "indisponibilitate",
            },
            "error": "Wrong number — person on line not familiar with the booking.",
            "ago_days": 15,
        },
        {
            "phone": "+37322801020",
            "status": TaskStatus.PENDING,
            "tpl": "Make appointment",
            "user": "ana.gojinevschi@isa.utm.md",
            "slots": {
                "preferred_date": "2026-04-26",
                "preferred_time": "11:00",
                "service_type": "physiotherapy",
                "patient_name": "Ana G.",
            },
            "ago_hours": 6,
        },
        {
            "phone": "+37322801021",
            "status": TaskStatus.PENDING,
            "tpl": "Follow-up call",
            "user": "ana.gojinevschi@isa.utm.md",
            "slots": {
                "reference_number": "ORD-91240",
                "contact_name": "DHL Moldova",
                "follow_up_topic": "parcel delivery status",
            },
            "ago_hours": 7,
        },
        {
            "phone": "+37322801022",
            "status": TaskStatus.COMPLETED,
            "tpl": "Prescription refill request",
            "user": "ana.gojinevschi@isa.utm.md",
            "slots": {
                "patient_name": "Ana Gojinevschi",
                "prescription_number": "RX-771204",
                "pharmacy_name": "Farmacia Familiei",
            },
            "ago_days": 5,
        },
        {
            "phone": "+37322801023",
            "status": TaskStatus.PENDING,
            "tpl": "Запись на приём",
            "user": "ana.gojinevschi@isa.utm.md",
            "slots": {
                "preferred_date": "2026-04-27",
                "preferred_time": "14:00",
                "service_type": "консультация терапевта",
                "patient_name": "Анна Г.",
            },
            "ago_hours": 8,
        },
        # --- Days 25-29 ago (light activity, mostly completed) ---
        {
            "phone": "+37322400100",
            "status": TaskStatus.COMPLETED,
            "tpl": "Make appointment",
            "user": "maria@example.com",
            "slots": {
                "preferred_date": "2026-03-28",
                "preferred_time": "16:00",
                "service_type": "haircut",
                "patient_name": "Maria P.",
            },
            "summary": "Haircut booked at Salon Elite, March 28 at 4 PM.",
            "ago_days": 28,
        },
        {
            "phone": "+37322400200",
            "status": TaskStatus.COMPLETED,
            "tpl": "Payment reminder",
            "user": "victor@example.com",
            "slots": {
                "invoice_number": "INV-2026-0011",
                "amount_due": "950 MDL",
                "due_date": "2026-03-25",
                "company_name": "Victor's Consulting",
            },
            "summary": "Invoice paid. Transaction ID TRX-55021.",
            "ago_days": 27,
        },
        {
            "phone": "+37322400300",
            "status": TaskStatus.COMPLETED,
            "tpl": "Confirm reservation",
            "user": "john@example.com",
            "slots": {
                "reservation_id": "RST-9988",
                "reservation_date": "2026-03-26",
                "guest_name": "John Smith",
            },
            "summary": "Table for 4 confirmed at La Taifas for 7 PM.",
            "ago_days": 26,
        },
        {
            "phone": "+37322400400",
            "status": TaskStatus.FAILED,
            "tpl": "Request information",
            "user": "dmitri@example.com",
            "slots": {
                "question_topic": "international shipping fees",
                "business_name": "Moldova Post",
            },
            "error": "No answer after 3 attempts.",
            "ago_days": 25,
        },
        # --- Days 15-24 ago (mid activity, broad mix) ---
        {
            "phone": "+37322500100",
            "status": TaskStatus.COMPLETED,
            "tpl": "Insurance claim inquiry",
            "user": "elena@example.com",
            "slots": {
                "claim_number": "CLM-3311",
                "policyholder_name": "Elena V.",
                "claim_type": "home",
            },
            "summary": "Claim under review. Decision expected within 10 business days.",
            "ago_days": 23,
        },
        {
            "phone": "+37322500200",
            "status": TaskStatus.COMPLETED,
            "tpl": "Order status check",
            "user": "ana@example.com",
            "slots": {"order_number": "ORD-22114", "customer_name": "Ana G."},
            "summary": "Order delivered March 27. Signed by recipient.",
            "ago_days": 22,
        },
        {
            "phone": "+37322500300",
            "status": TaskStatus.COMPLETED,
            "tpl": "Make appointment",
            "user": "natalia@example.com",
            "slots": {
                "preferred_date": "2026-04-02",
                "preferred_time": "11:00",
                "service_type": "dental cleaning",
                "patient_name": "Natalia R.",
            },
            "summary": "Cleaning booked April 2 at 11 AM with Dr. Rusu.",
            "ago_days": 21,
        },
        {
            "phone": "+37322500400",
            "status": TaskStatus.FAILED,
            "tpl": "Cancel appointment",
            "user": "alex@example.com",
            "slots": {
                "appointment_date": "2026-04-01",
                "appointment_time": "10:00",
                "booked_name": "Alex T.",
                "reason": "personal",
            },
            "error": "Interlocutor hung up before confirming.",
            "ago_days": 20,
        },
        {
            "phone": "+37322500500",
            "status": TaskStatus.COMPLETED,
            "tpl": "Follow-up call",
            "user": "john@example.com",
            "slots": {
                "reference_number": "CASE-9011",
                "contact_name": "Legal Team",
                "follow_up_topic": "contract review status",
            },
            "summary": "Contract approved with minor amendments. Document sent via email.",
            "ago_days": 19,
        },
        {
            "phone": "+37322500800",
            "status": TaskStatus.COMPLETED,
            "tpl": "Prescription refill request",
            "user": "ana@example.com",
            "slots": {
                "patient_name": "Ana Gojinevschi",
                "prescription_number": "RX-115902",
                "pharmacy_name": "Farmacia Centrală",
            },
            "summary": "Refill approved. Ready for pickup next business day.",
            "ago_days": 18,
        },
        {
            "phone": "+37322500900",
            "status": TaskStatus.COMPLETED,
            "tpl": "Service outage report",
            "user": "victor@example.com",
            "slots": {
                "account_number": "ACC-556644",
                "service_type": "cable TV",
                "issue_description": "Signal lost since morning",
                "customer_name": "Victor M.",
            },
            "summary": "Regional outage reported. Technicians dispatched, ETA 4 hours.",
            "ago_days": 17,
        },
        {
            "phone": "+37322501000",
            "status": TaskStatus.COMPLETED,
            "tpl": "Make appointment",
            "user": "elena@example.com",
            "slots": {
                "preferred_date": "2026-04-06",
                "preferred_time": "09:00",
                "service_type": "check-up",
                "patient_name": "Elena V.",
            },
            "summary": "Check-up booked with Dr. Munteanu, April 6 at 9 AM.",
            "ago_days": 16,
        },
        {
            "phone": "+37322501100",
            "status": TaskStatus.FAILED,
            "tpl": "File a complaint",
            "user": "dmitri@example.com",
            "slots": {
                "complaint_subject": "Wrong item delivered",
                "complaint_details": "Received blue shirt instead of red, order #DM-4412",
                "customer_name": "Dmitri K.",
            },
            "error": "Call ended without resolution. Asked to resubmit in writing.",
            "ago_days": 15,
        },
        # --- Days 7-14 ago (growing volume, mix of outcomes) ---
        {
            "phone": "+37322600100",
            "status": TaskStatus.COMPLETED,
            "tpl": "Confirm reservation",
            "user": "ana@example.com",
            "slots": {
                "reservation_id": "HTL-7712",
                "reservation_date": "2026-04-15",
                "guest_name": "Ana G.",
            },
            "summary": "Hotel reservation confirmed for April 15, 2 nights.",
            "ago_days": 14,
        },
        {
            "phone": "+37322600200",
            "status": TaskStatus.COMPLETED,
            "tpl": "Reschedule appointment",
            "user": "john@example.com",
            "slots": {
                "original_date": "2026-04-10",
                "original_time": "14:00",
                "new_preferred_date": "2026-04-17",
                "new_preferred_time": "14:00",
                "booked_name": "John Smith",
                "service_type": "haircut",
            },
            "summary": "Rescheduled to April 17 at 2 PM. Same stylist.",
            "ago_days": 13,
        },
        {
            "phone": "+37322600300",
            "status": TaskStatus.COMPLETED,
            "tpl": "Order status check",
            "user": "maria@example.com",
            "slots": {"order_number": "PKG-22180", "customer_name": "Maria P."},
            "summary": "Package in transit. Expected delivery in 2 business days.",
            "ago_days": 12,
        },
        {
            "phone": "+37322600400",
            "status": TaskStatus.FAILED,
            "tpl": "Payment reminder",
            "user": "victor@example.com",
            "slots": {
                "invoice_number": "INV-2026-0077",
                "amount_due": "3,100 MDL",
                "due_date": "2026-04-15",
                "company_name": "Victor's Consulting",
            },
            "error": "Client disputed the invoice. Escalated to accounting.",
            "ago_days": 11,
        },
        {
            "phone": "+37322600500",
            "status": TaskStatus.COMPLETED,
            "tpl": "Make appointment",
            "user": "alex@example.com",
            "slots": {
                "preferred_date": "2026-04-20",
                "preferred_time": "15:00",
                "service_type": "eye exam",
                "patient_name": "Alex T.",
            },
            "summary": "Eye exam booked April 20 at 3 PM. Bring current glasses.",
            "ago_days": 11,
        },
        {
            "phone": "+37322600600",
            "status": TaskStatus.COMPLETED,
            "tpl": "Insurance claim inquiry",
            "user": "natalia@example.com",
            "slots": {
                "claim_number": "CLM-7890",
                "policyholder_name": "Natalia R.",
                "claim_type": "travel",
            },
            "summary": "Claim approved. Reimbursement of 450 EUR within 7 days.",
            "ago_days": 10,
        },
        {
            "phone": "+37322600710",
            "status": TaskStatus.COMPLETED,
            "tpl": "Request information",
            "user": "dmitri@example.com",
            "slots": {
                "question_topic": "apartment availability in May",
                "business_name": "Chisinau Rentals",
            },
            "summary": "Three 2-bedroom apartments available. Viewings can be scheduled Mon-Fri.",
            "ago_days": 9,
        },
        {
            "phone": "+37322600820",
            "status": TaskStatus.COMPLETED,
            "tpl": "Follow-up call",
            "user": "elena@example.com",
            "slots": {
                "reference_number": "TKT-41002",
                "contact_name": "IT Helpdesk",
                "follow_up_topic": "laptop setup",
            },
            "summary": "Laptop configured and delivered to the office.",
            "ago_days": 8,
        },
        {
            "phone": "+37322600930",
            "status": TaskStatus.COMPLETED,
            "tpl": "Service outage report",
            "user": "ana@example.com",
            "slots": {
                "account_number": "ACC-102938",
                "service_type": "mobile data",
                "issue_description": "No 4G signal in Ciocana district",
                "customer_name": "Ana G.",
            },
            "summary": "Known tower maintenance. Service to resume by evening. Ticket #OUT-2240.",
            "ago_days": 7,
        },
        # --- Future scheduled (days 1-7 ahead) ---
        {
            "phone": "+37322700110",
            "status": TaskStatus.SCHEDULED,
            "tpl": "Confirm reservation",
            "user": "ana@example.com",
            "slots": {
                "reservation_id": "HTL-9921",
                "reservation_date": "2026-04-30",
                "guest_name": "Ana G.",
            },
            "scheduled_future_days": 3,
            "ago_hours": 8,
        },
        {
            "phone": "+37322700220",
            "status": TaskStatus.SCHEDULED,
            "tpl": "Make appointment",
            "user": "maria@example.com",
            "slots": {
                "preferred_date": "2026-05-02",
                "preferred_time": "11:00",
                "service_type": "notary",
                "patient_name": "Maria P.",
            },
            "scheduled_future_days": 5,
            "ago_hours": 10,
        },
        {
            "phone": "+37322700330",
            "status": TaskStatus.SCHEDULED,
            "tpl": "Payment reminder",
            "user": "victor@example.com",
            "slots": {
                "invoice_number": "INV-2026-0102",
                "amount_due": "2,400 MDL",
                "due_date": "2026-05-10",
                "company_name": "Victor's Consulting",
            },
            "scheduled_future_days": 6,
            "ago_hours": 12,
        },
        # --- Recent today (<24h, pending/in-progress) ---
        {
            "phone": "+37322800110",
            "status": TaskStatus.PENDING,
            "tpl": "Request information",
            "user": "john@example.com",
            "slots": {
                "question_topic": "weekend delivery options",
                "business_name": "DHL Moldova",
            },
            "ago_hours": 2,
        },
        {
            "phone": "+37322800220",
            "status": TaskStatus.PENDING,
            "tpl": "Make appointment",
            "user": "natalia@example.com",
            "slots": {
                "preferred_date": "2026-04-25",
                "preferred_time": "13:00",
                "service_type": "consultation",
                "patient_name": "Natalia R.",
            },
            "ago_hours": 0,
        },
        # ===== Romanian-heavy demo data (for RO demo) =====
        {
            "phone": "+37322030101",
            "status": TaskStatus.COMPLETED,
            "tpl": "Programare la medic",
            "user": "ana@example.com",
            "slots": {
                "preferred_date": "2026-04-02",
                "preferred_time": "09:30",
                "service_type": "stomatolog",
                "patient_name": "Ana G.",
            },
            "summary": "Programare confirmată la Clinica Dentaria, 2 aprilie, ora 9:30.",
            "ago_days": 26,
        },
        {
            "phone": "+37322030102",
            "status": TaskStatus.COMPLETED,
            "tpl": "Confirmare rezervare",
            "user": "maria@example.com",
            "slots": {
                "reservation_id": "REZ-2026-0110",
                "reservation_date": "2026-04-05",
                "guest_name": "Maria P.",
            },
            "summary": "Rezervare confirmată la restaurant Andy's, masa pentru 4 persoane.",
            "ago_days": 24,
        },
        {
            "phone": "+37322030103",
            "status": TaskStatus.COMPLETED,
            "tpl": "Solicitare informații",
            "user": "john@example.com",
            "slots": {
                "question_topic": "program de lucru",
                "business_name": "Poșta Moldovei",
            },
            "summary": "Program: luni-vineri 08:00-17:00, sâmbătă 09:00-13:00.",
            "ago_days": 22,
        },
        {
            "phone": "+37322030104",
            "status": TaskStatus.COMPLETED,
            "tpl": "Programare la medic",
            "user": "elena@example.com",
            "slots": {
                "preferred_date": "2026-04-10",
                "preferred_time": "14:00",
                "service_type": "consultație cardiologie",
                "patient_name": "Elena V.",
            },
            "summary": "Programare confirmată cu Dr. Munteanu, 10 aprilie ora 14:00.",
            "ago_days": 20,
        },
        {
            "phone": "+37322030105",
            "status": TaskStatus.FAILED,
            "tpl": "Anulare programare",
            "user": "dmitri@example.com",
            "slots": {
                "appointment_date": "2026-04-12",
                "appointment_time": "10:00",
                "booked_name": "Dmitri K.",
                "reason": "urgență de serviciu",
            },
            "error": "Linia ocupată după 3 încercări.",
            "ago_days": 18,
        },
        {
            "phone": "+37322030106",
            "status": TaskStatus.COMPLETED,
            "tpl": "Reprogramare programare",
            "user": "natalia@example.com",
            "slots": {
                "original_date": "2026-04-15",
                "original_time": "11:00",
                "new_preferred_date": "2026-04-22",
                "new_preferred_time": "11:00",
                "booked_name": "Natalia R.",
                "service_type": "masaj terapeutic",
            },
            "summary": "Reprogramare confirmată pentru 22 aprilie, ora 11:00.",
            "ago_days": 16,
        },
        {
            "phone": "+37322030107",
            "status": TaskStatus.COMPLETED,
            "tpl": "Solicitare informații",
            "user": "alex@example.com",
            "slots": {
                "question_topic": "preț abonament anual",
                "business_name": "FitLife Chișinău",
            },
            "summary": "Abonament anual: 3.200 MDL, include sală și bazin.",
            "ago_days": 14,
        },
        {
            "phone": "+37322030108",
            "status": TaskStatus.COMPLETED,
            "tpl": "Programare la medic",
            "user": "victor@example.com",
            "slots": {
                "preferred_date": "2026-04-18",
                "preferred_time": "16:00",
                "service_type": "analize sânge",
                "patient_name": "Victor M.",
            },
            "summary": "Programare confirmată la laborator Synevo, 18 aprilie ora 16:00. Vine nemâncat.",
            "ago_days": 13,
        },
        {
            "phone": "+37322030109",
            "status": TaskStatus.COMPLETED,
            "tpl": "Confirmare rezervare",
            "user": "ana@example.com",
            "slots": {
                "reservation_id": "HTL-CHI-4412",
                "reservation_date": "2026-04-28",
                "guest_name": "Ana Gojinevschi",
            },
            "summary": "Rezervare hotel confirmată: Berd's Design Hotel, 28-30 aprilie, cameră dublă.",
            "ago_days": 12,
        },
        {
            "phone": "+37322030110",
            "status": TaskStatus.COMPLETED,
            "tpl": "Anulare programare",
            "user": "john@example.com",
            "slots": {
                "appointment_date": "2026-04-20",
                "appointment_time": "09:00",
                "booked_name": "John Smith",
                "reason": "conflict de călătorie",
            },
            "summary": "Programare anulată. Fără taxă de anulare.",
            "ago_days": 11,
        },
        {
            "phone": "+37322030111",
            "status": TaskStatus.COMPLETED,
            "tpl": "Solicitare informații",
            "user": "maria@example.com",
            "slots": {
                "question_topic": "disponibilitate apartament 2 camere",
                "business_name": "Chișinău Imobil",
            },
            "summary": "Trei apartamente disponibile, vizionări programate marți după-amiază.",
            "ago_days": 10,
        },
        {
            "phone": "+37322030112",
            "status": TaskStatus.COMPLETED,
            "tpl": "Programare la medic",
            "user": "elena@example.com",
            "slots": {
                "preferred_date": "2026-04-24",
                "preferred_time": "10:30",
                "service_type": "control stomatologic",
                "patient_name": "Elena V.",
            },
            "summary": "Programare confirmată la Dr. Rusu, 24 aprilie ora 10:30.",
            "ago_days": 9,
        },
        {
            "phone": "+37322030113",
            "status": TaskStatus.COMPLETED,
            "tpl": "Reprogramare programare",
            "user": "dmitri@example.com",
            "slots": {
                "original_date": "2026-04-25",
                "original_time": "15:00",
                "new_preferred_date": "2026-05-02",
                "new_preferred_time": "15:00",
                "booked_name": "Dmitri K.",
                "service_type": "tuns și barbă",
            },
            "summary": "Reprogramat pentru 2 mai ora 15:00, același maestru.",
            "ago_days": 8,
        },
        {
            "phone": "+37322030114",
            "status": TaskStatus.COMPLETED,
            "tpl": "Confirmare rezervare",
            "user": "alex@example.com",
            "slots": {
                "reservation_id": "AVIA-MD-2040",
                "reservation_date": "2026-05-05",
                "guest_name": "Alex T.",
            },
            "summary": "Zbor confirmat: Chișinău-București, 5 mai 07:15, locul 14A.",
            "ago_days": 7,
        },
        {
            "phone": "+37322030115",
            "status": TaskStatus.FAILED,
            "tpl": "Programare la medic",
            "user": "natalia@example.com",
            "slots": {
                "preferred_date": "2026-04-28",
                "preferred_time": "11:00",
                "service_type": "dermatolog",
                "patient_name": "Natalia R.",
            },
            "error": "Nicio slot liber până pe 10 mai. A sugerat să sunăm ulterior.",
            "ago_days": 6,
        },
        {
            "phone": "+37322030116",
            "status": TaskStatus.COMPLETED,
            "tpl": "Solicitare informații",
            "user": "victor@example.com",
            "slots": {
                "question_topic": "prețuri servicii contabilitate",
                "business_name": "ContExpert SRL",
            },
            "summary": "Pachet lunar de la 1.800 MDL pentru SRL. Ofertă personalizată prin email.",
            "ago_days": 5,
        },
        {
            "phone": "+37322030117",
            "status": TaskStatus.COMPLETED,
            "tpl": "Programare la medic",
            "user": "ana@example.com",
            "slots": {
                "preferred_date": "2026-05-03",
                "preferred_time": "13:00",
                "service_type": "oftalmolog",
                "patient_name": "Ana G.",
            },
            "summary": "Programare confirmată la Optimed, 3 mai ora 13:00.",
            "ago_days": 4,
        },
        {
            "phone": "+37322030118",
            "status": TaskStatus.COMPLETED,
            "tpl": "Anulare programare",
            "user": "maria@example.com",
            "slots": {
                "appointment_date": "2026-04-30",
                "appointment_time": "16:00",
                "booked_name": "Maria P.",
                "reason": "motive personale",
            },
            "summary": "Programare anulată cu succes. Fără taxă.",
            "ago_days": 3,
        },
        {
            "phone": "+37322030119",
            "status": TaskStatus.SCHEDULED,
            "tpl": "Confirmare rezervare",
            "user": "elena@example.com",
            "slots": {
                "reservation_id": "REZ-EV-2210",
                "reservation_date": "2026-05-12",
                "guest_name": "Elena V.",
            },
            "scheduled_future_days": 4,
            "ago_hours": 6,
        },
        {
            "phone": "+37322030120",
            "status": TaskStatus.PENDING,
            "tpl": "Solicitare informații",
            "user": "dmitri@example.com",
            "slots": {
                "question_topic": "livrare internațională",
                "business_name": "Moldova Post",
            },
            "ago_hours": 3,
        },
    ]

    created_task_ids: list[tuple[int, str]] = []
    skipped_count = 0
    for task_data in tasks_data:
        if task_data["phone"] in existing_phones:
            skipped_count += 1
            continue

        task_created_at = now - timedelta(
            days=task_data.get("ago_days", 0),
            hours=task_data.get("ago_hours", 0),
        )
        generated_summary = _generate_summary(task_data["tpl"], task_data["status"], task_data["slots"])
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
            summary=generated_summary or task_data.get("summary"),
            error_reason=task_data.get("error"),
            created_at=task_created_at,
            updated_at=task_created_at,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        created_task_ids.append((task.id, task_data["status"]))

    print(f"  CREATED {len(created_task_ids)} demo tasks (skipped {skipped_count} already existing by phone)")
    return created_task_ids


class _SlotDict(dict):
    """dict that renders missing keys as an empty string — safe for text.format_map."""

    def __missing__(self, key: str) -> str:
        return ""


def _render_transcript(lines: list[dict], slot_data: dict) -> list[dict]:
    """Fill {placeholder} fields in each line's text from slot_data, safely."""
    rendered: list[dict] = []
    for line in lines:
        rendered_text = line["text"].format_map(_SlotDict(slot_data))
        rendered.append({**line, "text": rendered_text})
    return rendered


SUMMARY_TEMPLATES: dict[tuple[str, bool], str] = {
    ("Make appointment", True): (
        "Appointment confirmed for {patient_name} — {service_type} on {preferred_date} at {preferred_time}."
    ),
    ("Make appointment", False): "Could not schedule {service_type} for {patient_name} on {preferred_date}.",
    ("Confirm reservation", True): "Reservation {reservation_id} confirmed for {guest_name} on {reservation_date}.",
    ("Confirm reservation", False): "Reservation {reservation_id} for {guest_name} could not be confirmed.",
    ("Cancel appointment", True): (
        "Appointment on {appointment_date} at {appointment_time} for {booked_name} cancelled. Reason: {reason}."
    ),
    ("Cancel appointment", False): "Could not cancel appointment for {booked_name} on {appointment_date}.",
    ("Reschedule appointment", True): (
        "Appointment for {booked_name} ({service_type}) moved from {original_date} {original_time} "
        "to {new_preferred_date} {new_preferred_time}."
    ),
    ("Reschedule appointment", False): "Could not reschedule appointment for {booked_name}.",
    ("Follow-up call", True): "Follow-up on {follow_up_topic} (ref {reference_number}) completed with {contact_name}.",
    ("Follow-up call", False): "Follow-up on {follow_up_topic} — no response from {contact_name}.",
    ("Request information", True): "Information about {question_topic} obtained from {business_name}.",
    ("Request information", False): "Could not obtain information about {question_topic} from {business_name}.",
    ("Order status check", True): "Status for order {order_number} ({customer_name}) checked.",
    ("Order status check", False): "Could not check status for order {order_number}.",
    ("File a complaint", True): "Complaint registered: {complaint_subject} for {customer_name}.",
    ("File a complaint", False): "Complaint {complaint_subject} could not be filed.",
    ("Prescription refill request", True): (
        "Prescription {prescription_number} refill requested for {patient_name} at {pharmacy_name}."
    ),
    ("Prescription refill request", False): (
        "Prescription {prescription_number} refill could not be processed at {pharmacy_name}."
    ),
    ("Service outage report", True): "Outage reported for account {account_number} ({service_type}). Ticket opened.",
    ("Service outage report", False): "Outage for account {account_number} could not be reported.",
    ("Insurance claim inquiry", True): (
        "Claim {claim_number} ({claim_type}) for {policyholder_name} — status checked."
    ),
    ("Insurance claim inquiry", False): "Could not check status for claim {claim_number}.",
    ("Payment reminder", True): (
        "Payment reminder delivered: invoice {invoice_number} ({amount_due}) due {due_date} from {company_name}."
    ),
    ("Payment reminder", False): "Payment reminder for invoice {invoice_number} could not be delivered.",
    # RO
    ("Programare la medic", True): (
        "Programare confirmată pentru {patient_name} — {service_type} pe {preferred_date} la {preferred_time}."
    ),
    (
        "Programare la medic",
        False,
    ): "Programarea {service_type} pentru {patient_name} nu a putut fi făcută pe {preferred_date}.",
    ("Confirmare rezervare", True): "Rezervarea {reservation_id} confirmată pentru {guest_name} pe {reservation_date}.",
    ("Confirmare rezervare", False): "Rezervarea {reservation_id} pentru {guest_name} nu a putut fi confirmată.",
    ("Anulare programare", True): (
        "Programarea din {appointment_date} la ora {appointment_time} pentru {booked_name} a fost anulată. "
        "Motiv: {reason}."
    ),
    ("Anulare programare", False): "Programarea pentru {booked_name} din {appointment_date} nu a putut fi anulată.",
    ("Reprogramare programare", True): (
        "Programarea lui {booked_name} ({service_type}) mutată din {original_date} {original_time} "
        "în {new_preferred_date} {new_preferred_time}."
    ),
    ("Reprogramare programare", False): "Programarea lui {booked_name} nu a putut fi reprogramată.",
    ("Solicitare informații", True): "Informații despre {question_topic} obținute de la {business_name}.",
    (
        "Solicitare informații",
        False,
    ): "Informațiile despre {question_topic} nu au putut fi obținute de la {business_name}.",
    ("Apel de revenire", True): (
        "Revenire pe {follow_up_topic} (ref {reference_number}) — finalizată cu {contact_name}."
    ),
    ("Apel de revenire", False): "Revenirea pentru {follow_up_topic} — fără răspuns de la {contact_name}.",
    ("Verificare status comandă", True): "Statusul comenzii {order_number} pentru {customer_name} verificat.",
    ("Verificare status comandă", False): "Statusul comenzii {order_number} nu a putut fi verificat.",
    ("Reamintire plată", True): (
        "Reamintire de plată trimisă: factura {invoice_number} ({amount_due}) "
        "scadentă pe {due_date} de la {company_name}."
    ),
    ("Reamintire plată", False): "Reamintirea pentru factura {invoice_number} nu a putut fi livrată.",
    # RU
    ("Запись на приём", True): (
        "Приём подтверждён для {patient_name} — {service_type} на {preferred_date} в {preferred_time}."
    ),
    ("Запись на приём", False): "Не удалось записать {patient_name} на {preferred_date}.",
}


def _generate_summary(template_name: str, status: str, slots: dict) -> str | None:
    """Derive a summary string from a per-template pattern + slot_data.

    Returns None for tasks whose status is not terminal, or for templates without
    a mapped pattern (callers may fall back to the task_data's hardcoded summary).
    """
    is_completed = status == TaskStatus.COMPLETED
    if not is_completed and status != TaskStatus.FAILED:
        return None
    pattern = SUMMARY_TEMPLATES.get((template_name, is_completed))
    if not pattern:
        return None
    return pattern.format_map(_SlotDict(slots))


DEMO_TRANSCRIPTS: dict[str, list[dict]] = {
    "appointment_success": [
        {
            "speaker": Speaker.AGENT,
            "text": "Hello, this is an automated assistant. I'm calling for {patient_name} to schedule a {service_type} appointment.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Sure, what date were you looking at?",
            "intent": "request_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "We'd prefer {preferred_date} at {preferred_time} if possible.",
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
            "text": "We're at the main clinic. No special preparation needed.",
            "intent": "provide_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Thank you very much. The appointment is confirmed for {preferred_date} at {preferred_time}. "
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
            "text": "Hello, this is an automated assistant calling for {guest_name} "
            "to confirm reservation {reservation_id} for {reservation_date}.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "One moment please... Yes, I see it. The reservation is active.",
            "intent": "confirmation",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Great. Is everything still on track for {reservation_date}?",
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
            "text": "Hello, I'd like to book a {service_type} appointment for {preferred_date} at {preferred_time}.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "I'm sorry, we're fully booked that day.",
            "intent": "rejection",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Is there anything available that week?",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "The earliest opening is next week at 3 PM.",
            "intent": "provide_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "I'll need to check with {patient_name}. Thank you for the information. [OBJECTIVE_FAILED]",
            "intent": None,
        },
    ],
    "follow_up_success": [
        {
            "speaker": Speaker.AGENT,
            "text": "Hi, I'm calling about {reference_number} regarding {follow_up_topic}.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Let me pull that up... Yes, I can see the details here.",
            "intent": "provide_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "When can we expect the next update?",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Everything's on schedule — you should hear back by end of day.",
            "intent": "provide_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Great, thank you for the update! [OBJECTIVE_ACHIEVED]",
            "intent": None,
        },
    ],
    "reschedule_success": [
        {
            "speaker": Speaker.AGENT,
            "text": "Hello, this is an automated assistant calling for {booked_name}. "
            "I need to reschedule an appointment from {original_date} at {original_time}.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "I see the appointment. What date would work better?",
            "intent": "request_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "We'd like to move it to {new_preferred_date} at {new_preferred_time} if possible.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "That slot is available. I'll update it now.",
            "intent": "confirmation",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Perfect. So confirmed for {new_preferred_date} at {new_preferred_time} for {service_type}. "
            "Thank you! [OBJECTIVE_ACHIEVED]",
            "intent": None,
        },
    ],
    "cancellation_success": [
        {
            "speaker": Speaker.AGENT,
            "text": "Hello, I need to cancel an appointment on {appointment_date} at {appointment_time} for {booked_name}.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "I see the appointment. May I ask the reason for cancellation?",
            "intent": "request_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "{reason}. Is there a cancellation fee?",
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
    "ro_programare_success": [
        {
            "speaker": Speaker.AGENT,
            "text": "Bună ziua, sunt un asistent automat. Sun din partea lui {patient_name} "
            "pentru a face o programare de {service_type}.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Desigur, pentru ce dată ați dori?",
            "intent": "request_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Preferabil pe {preferred_date}, la ora {preferred_time} dacă se poate.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Verific... Da, avem liber.",
            "intent": "confirmation",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Perfect, confirm pentru {preferred_date} la {preferred_time}. Mulțumesc frumos! [OBJECTIVE_ACHIEVED]",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Cu plăcere. O zi bună!",
            "intent": "farewell",
        },
    ],
    "ro_rezervare_success": [
        {
            "speaker": Speaker.AGENT,
            "text": "Bună ziua, sun din partea lui {guest_name} pentru a confirma "
            "rezervarea {reservation_id} pentru {reservation_date}.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Un moment, vă rog... Da, o văd. Totul este în regulă.",
            "intent": "confirmation",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Perfect. Deci rezervarea rămâne activă pentru {reservation_date}?",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Da, totul confirmat. Vă așteptăm!",
            "intent": "confirmation",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Minunat, mulțumesc. La revedere! [OBJECTIVE_ACHIEVED]",
            "intent": None,
        },
    ],
    "ro_reschedule_success": [
        {
            "speaker": Speaker.AGENT,
            "text": "Bună ziua, sun din partea lui {booked_name} pentru a reprograma "
            "programarea din {original_date} de la ora {original_time}.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Am găsit programarea. Ce dată ați prefera?",
            "intent": "request_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Am dori s-o mutăm pe {new_preferred_date} la ora {new_preferred_time}, dacă se poate.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Ora e liberă, am actualizat programarea.",
            "intent": "confirmation",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Perfect. Confirmat pentru {new_preferred_date} la {new_preferred_time}. "
            "Mulțumesc! [OBJECTIVE_ACHIEVED]",
            "intent": None,
        },
    ],
    "ro_anulare_success": [
        {
            "speaker": Speaker.AGENT,
            "text": "Bună ziua, sun din partea lui {booked_name} pentru a anula "
            "programarea din {appointment_date} de la ora {appointment_time}.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Am găsit-o. Pot întreba care este motivul anulării?",
            "intent": "request_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "{reason}. Există vreo taxă de anulare?",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Fără taxă, s-a anulat cu succes.",
            "intent": "confirmation",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Vă mulțumesc. O zi bună! [OBJECTIVE_ACHIEVED]",
            "intent": None,
        },
    ],
    "ro_informatii_success": [
        {
            "speaker": Speaker.AGENT,
            "text": "Bună ziua, sunt un asistent automat. Aș dori să aflu despre {question_topic} de la {business_name}.",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Sigur, vă ofer informațiile pe loc.",
            "intent": "provide_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Mulțumesc pentru informație. Există vreo ofertă activă în perioada aceasta?",
            "intent": None,
        },
        {
            "speaker": Speaker.INTERLOCUTOR,
            "text": "Da, avem promoții valabile până la sfârșitul lunii.",
            "intent": "provide_info",
        },
        {
            "speaker": Speaker.AGENT,
            "text": "Foarte bine, mulțumesc mult. O zi bună! [OBJECTIVE_ACHIEVED]",
            "intent": None,
        },
    ],
}


TRANSCRIPT_KEY_BY_TEMPLATE_NAME: dict[str, str] = {
    "Make appointment": "appointment_success",
    "Confirm reservation": "reservation_confirmed",
    "Cancel appointment": "cancellation_success",
    "Reschedule appointment": "reschedule_success",
    "Follow-up call": "follow_up_success",
    "Request information": "follow_up_success",
    "Order status check": "follow_up_success",
    "File a complaint": "appointment_failed",
    "Prescription refill request": "appointment_success",
    "Service outage report": "follow_up_success",
    "Insurance claim inquiry": "follow_up_success",
    "Payment reminder": "follow_up_success",
    "Programare la medic": "ro_programare_success",
    "Confirmare rezervare": "ro_rezervare_success",
    "Solicitare informații": "ro_informatii_success",
    "Anulare programare": "ro_anulare_success",
    "Reprogramare programare": "ro_reschedule_success",
    "Apel de revenire": "ro_informatii_success",
    "Verificare status comandă": "ro_informatii_success",
    "Depunere plângere": "ro_informatii_success",
    "Cerere rețetă": "ro_programare_success",
    "Raportare întrerupere serviciu": "ro_informatii_success",
    "Întrebare dosar asigurare": "ro_informatii_success",
    "Reamintire plată": "ro_informatii_success",
}


async def seed_call_sessions(session: AsyncSession, tasks: list[tuple[int, str]]) -> None:
    from app.modules.templates.models import DialogTemplate

    transcript_keys = list(DEMO_TRANSCRIPTS.keys())
    total_sessions = 0
    total_log_lines = 0

    existing_task_ids_result = await session.exec(select(CallSession.task_id))
    existing_session_task_ids = set(existing_task_ids_result.all())

    result = await session.exec(
        select(Task.id, Task.status, Task.created_at, Task.template_id, Task.slot_data).where(
            Task.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED])
        )
    )
    eligible_tasks = [
        (task_id, status, created_at, template_id, slot_data or {})
        for (task_id, status, created_at, template_id, slot_data) in result.all()
        if task_id not in existing_session_task_ids
    ]

    template_rows = await session.exec(select(DialogTemplate.id, DialogTemplate.name))
    template_name_by_id: dict[int, str] = dict(template_rows.all())

    for task_index, (task_id, _task_status, task_created_at, template_id, slot_data) in enumerate(eligible_tasks):
        duration = BASE_CALL_DURATION_SECONDS + (task_id * CALL_DURATION_VARIATION_FACTOR) % MAX_CALL_DURATION_VARIATION

        call_session = CallSession(
            task_id=task_id,
            start_time=task_created_at,
            duration=duration,
            recording_uri=DEMO_RECORDING_URL_TEMPLATE.format(task_id=task_id),
            created_at=task_created_at,
            updated_at=task_created_at,
        )
        session.add(call_session)
        await session.commit()
        await session.refresh(call_session)
        total_sessions += 1

        template_name = template_name_by_id.get(template_id, "")
        template_key = TRANSCRIPT_KEY_BY_TEMPLATE_NAME.get(
            template_name,
            transcript_keys[task_index % len(transcript_keys)],
        )
        transcript_lines = _render_transcript(DEMO_TRANSCRIPTS[template_key], slot_data)

        transcript_start_time = call_session.start_time
        for line_index, transcript_line in enumerate(transcript_lines):
            log = LogLine(
                session_id=call_session.id,
                timestamp=transcript_start_time + timedelta(seconds=line_index * SECONDS_BETWEEN_TRANSCRIPT_LINES),
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
    print(f"  Admin:      {ADMIN_EMAIL_PRIMARY} / {ADMIN_PASSWORD}")
    print(f"  Admin:      {ADMIN_EMAIL_SECONDARY} / {ADMIN_PASSWORD}")
    print(f"  Users:      ana@example.com / {USER_PASSWORD}")
    print(f"              john@example.com / {USER_PASSWORD}")
    print(f"              maria@example.com / {USER_PASSWORD}")
    print(f"              alex@example.com / {USER_PASSWORD}")
    print(f"              elena@example.com / {USER_PASSWORD}")
    print(f"              dmitri@example.com / {USER_PASSWORD}")
    print(f"              natalia@example.com / {USER_PASSWORD}")
    print(f"              victor@example.com / {USER_PASSWORD}")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
