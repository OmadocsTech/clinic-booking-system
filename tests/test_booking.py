from datetime import datetime, time, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import crud, models
from app.database import Base


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([models.Doctor(name="Dr. Wanjiku", specialization="General Medicine"), models.Patient(name="Amina", email="amina@example.com")])
    session.commit()
    yield session
    session.close()


def future_slot(hour=10):
    return (datetime.now() + timedelta(days=2)).replace(hour=hour, minute=0, second=0, microsecond=0)


def add_hours(db, slot):
    db.add(models.WorkingHours(doctor_id=1, day_of_week=slot.weekday(), start_time=time(9), end_time=time(17)))
    db.commit()


def test_booking_requires_working_hours_and_rejects_duplicates(db):
    slot = future_slot()
    add_hours(db, slot)
    appointment = crud.create_appointment(db, 1, 1, slot)
    assert appointment.end_time == slot + timedelta(minutes=30)
    with pytest.raises(HTTPException) as error:
        crud.create_appointment(db, 1, 1, slot)
    assert error.value.status_code == 409


def test_booking_rejects_outside_working_hours(db):
    slot = future_slot(hour=18)
    add_hours(db, slot)
    with pytest.raises(HTTPException) as error:
        crud.create_appointment(db, 1, 1, slot)
    assert error.value.status_code == 422


def test_cancel_and_reschedule_release_original_slots(db):
    original = future_slot()
    destination = original + timedelta(minutes=30)
    add_hours(db, original)
    appointment = crud.create_appointment(db, 1, 1, original)
    moved = crud.reschedule_appointment(db, appointment.id, destination)
    assert moved.start_time == destination
    assert crud.create_appointment(db, 1, 1, original).start_time == original
    crud.cancel_appointment(db, moved.id, "No longer needed")
    assert crud.create_appointment(db, 1, 1, destination).id != moved.id
