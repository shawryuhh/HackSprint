"""Seeds demo data for the canonical Krishna Apartments scenario.

Run with:  python -m scripts.seed_demo_data [--reset] [--fleet-only]

Goes through the real service layer (incident_service, resource_service,
assignment_service, replanning_service) rather than raw INSERTs, so the
seeded data is guaranteed to satisfy exactly the same rules the live API
enforces — this script is effectively the AI/n8n side of the demo, feeding
already-decided payloads into the same contracts a real integration would
use. It also serves as an end-to-end smoke test of the full incident ->
assign -> replan flow against whatever DATABASE_URL points at.

By default this ADDS to whatever's already in the target database. Pass
--reset to truncate incidents/resources/assignments/action_logs first (and
reset the ambulance/rescue-unit ID sequences) — only do this against a
database you're fine losing all rows in, e.g. your local dev DB before a
demo. Never point this at anything shared without --reset being a deliberate
choice.
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.enums import Severity
from app.schemas.assignment import AssignmentCreate, ReplanningRequest
from app.schemas.incident import IncidentCreate
from app.schemas.resource import ResourceCreate
from app.services import assignment_service, incident_service, replanning_service, resource_service
from app.services.id_generator import resource_prefix_for_type

APP_TABLES = ["incidents", "resources", "assignments", "action_logs"]

# Order matters: ambulances are created in this order so the canonical
# narrative's AMB-02 and AMB-05 land on the resources actually used in it.
FLEET = [
    ("ambulance", "Sector 12 Depot", ["medical"], 2),
    ("ambulance", "Sector 12 Depot", ["medical"], 2),  # -> AMB-02
    ("ambulance", "Sector 9 Depot", ["medical"], 2),
    ("ambulance", "Sector 9 Depot", ["medical"], 2),
    ("ambulance", "Sector 4 Depot", ["medical"], 2),  # -> AMB-05
    ("rescue_unit", "Central Depot", ["water_rescue", "medical"], 4),  # -> RESCUE-01
    ("rescue_unit", "North Depot", ["water_rescue"], 4),
    ("volunteer", "Community Hall", ["evacuation_support"], None),
    ("shelter", "Government School, Sector 8", [], 200),
    ("hospital", "City General Hospital", ["trauma", "medical"], 50),
]


def reset_tables(db: Session) -> None:
    db.execute(text(f"TRUNCATE TABLE {', '.join(APP_TABLES)} RESTART IDENTITY CASCADE"))
    # Resource ID sequences are created on demand per type prefix (see
    # app.services.id_generator) and aren't reset by RESTART IDENTITY above,
    # since they aren't owned by a table's identity column. Reset every
    # sequence this seed run uses, so a repeated --reset always reproduces
    # the exact same resource IDs, not just the narrative-critical ones.
    prefixes = {resource_prefix_for_type(resource_type) for resource_type, *_ in FLEET}
    for prefix in prefixes:
        seq_name = f"resource_seq_{prefix.lower()}"
        exists = db.execute(
            text("SELECT 1 FROM pg_sequences WHERE sequencename = :name"), {"name": seq_name}
        ).scalar()
        if exists:
            db.execute(text(f'SELECT setval(\'"{seq_name}"\', 1, false)'))
    db.commit()


def seed_fleet(db: Session) -> None:
    print("Seeded fleet:")
    for resource_type, location, capabilities, capacity in FLEET:
        resource = resource_service.create_resource(
            db,
            ResourceCreate(
                type=resource_type,
                location=location,
                capabilities=capabilities,
                capacity=capacity,
            ),
        )
        print(f"  {resource.id:<10} {resource.type:<12} {resource.location}")


def seed_narrative_scenario(db: Session) -> None:
    # Advances the sequences so this run's incident/assignment IDs match the
    # canonical demo narrative (INC-1042, ASG-887) regardless of what ran
    # before. Both sequences always exist (created in the initial migration),
    # so this is safe with or without --reset.
    db.execute(text("SELECT setval('incident_seq', 1041)"))
    db.execute(text("SELECT setval('assignment_seq', 886)"))
    db.commit()

    incident = incident_service.create_incident(
        db,
        IncidentCreate(
            location="Krishna Apartments, Block C",
            latitude=12.9352,
            longitude=77.6146,
            type="flood",
            severity=Severity.CRITICAL,
            people_affected=4,
            needs=["medical", "evacuation"],
            confidence=0.88,
            priority_score=94,
            report_metadata={
                "channel": "whatsapp",
                "raw_text": (
                    "Water entering Krishna Apartments Block C. "
                    "My grandmother cannot walk."
                ),
            },
        ),
    )

    amb_02 = resource_service.get_resource(db, "AMB-02")
    rescue_01 = resource_service.get_resource(db, "RESCUE-01")
    amb_05 = resource_service.get_resource(db, "AMB-05")

    assignment_service.create_assignment(
        db,
        AssignmentCreate(
            incident_id=incident.id,
            resource_ids=[amb_02.id, rescue_01.id],
            decision_source="ai",
            approved_by="dispatcher_1",
            reason="Medical emergency involving a vulnerable person",
            ai_recommendation={
                "incident_id": incident.id,
                "priority_score": 94,
                "recommended_resources": [amb_02.id, rescue_01.id],
                "reason": "Medical emergency involving a vulnerable person",
                "confidence": 0.91,
            },
        ),
    )

    replanning_service.replan(
        db,
        ReplanningRequest(
            incident_id=incident.id,
            old_resource_id=amb_02.id,
            new_resource_ids=[amb_05.id],
            reason="road_blocked",
            decision_source="ai",
            approved_by="dispatcher_1",
        ),
    )

    print(f"\nSeeded canonical scenario on incident {incident.id}:")
    print(f"  {amb_02.id} assigned, then replanned to {amb_05.id} (road block)")
    print(f"  {rescue_01.id} still dispatched to {incident.id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Truncate incidents/resources/assignments/action_logs first.",
    )
    parser.add_argument(
        "--fleet-only",
        action="store_true",
        help="Seed the resource fleet only; skip the incident/assignment/replan narrative.",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.reset:
            reset_tables(db)

        seed_fleet(db)

        if not args.fleet_only:
            seed_narrative_scenario(db)


if __name__ == "__main__":
    main()
