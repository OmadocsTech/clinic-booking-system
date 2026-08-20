"""Appointment business rules, isolated from the HTTP layer."""

from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models

SLOT_LENGTH = timedelta(minutes=30)
MINIMUM_NOTICE = timedelta(hours=1)


def _not_found(entity: str) -> HTTPException:
  return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{entity} not found.")


def get_doctor_or_404(db: Session, doctor_id: int) -> models.Doctor:
  doctor = db.get(models.Doctor, doctor_id)
  if doctor is None:
    raise _not_found("Doctor")
  return doctor


def get_patient_or_404(db: Session, patient_id: int) -> models.Patient:
  patient = db.get(models.Patient, patient_id)
  if patient is None:
    raise _not_found("Patient")
  return patient


def validate_slot(db: Session, doctor_id: int, start_time: datetime, *, exclude_appointment_id: int | None = None) -> datetime:
  """Validate a slot as if it were a new booking and return its end time."""
  if start_time.tzinfo is not None:
    raise HTTPException(status_code=422, detail="start_time must not include a timezone offset.")
  if start_time.second or start_time.microsecond or start_time.minute % 30:
    raise HTTPException(status_code=422, detail="Appointments must start on a 30-minute boundary.")
  if start_time < datetime.now() + MINIMUM_NOTICE:
    raise HTTPException(status_code=400, detail="Bookings must be made at least 1 hour in advance.")

  get_doctor_or_404(db, doctor_id)
  hours = db.scalar(select(models.WorkingHours).where(
    models.WorkingHours.doctor_id == doctor_id,
    models.WorkingHours.day_of_week == start_time.weekday(),
  ))
  end_time = start_time + SLOT_LENGTH
  if hours is None or start_time.time() < hours.start_time or end_time.time() > hours.end_time:
    raise HTTPException(status_code=422, detail="The requested slot is outside the doctor's working hours.")

  booked_query = select(models.Appointment.id).where(
    models.Appointment.doctor_id == doctor_id,
    models.Appointment.start_time == start_time,
    models.Appointment.status == models.AppointmentStatus.BOOKED,
  )
  if exclude_appointment_id is not None:
    booked_query = booked_query.where(models.Appointment.id != exclude_appointment_id)
  booked = db.scalar(booked_query)
  if booked is not None:
    raise HTTPException(status_code=409, detail="This appointment slot is already booked.")
  return end_time


def create_appointment(db: Session, doctor_id: int, patient_id: int, start_time: datetime) -> models.Appointment:
  get_patient_or_404(db, patient_id)
  appointment = models.Appointment(
    doctor_id=doctor_id, patient_id=patient_id, start_time=start_time,
    end_time=validate_slot(db, doctor_id, start_time), status=models.AppointmentStatus.BOOKED,
  )
  db.add(appointment)
  try:
    db.commit()
  except IntegrityError:
    db.rollback()
    raise HTTPException(status_code=409, detail="This appointment slot is already booked.") from None
  db.refresh(appointment)
  return appointment


def availability(db: Session, doctor_id: int, target_date: date) -> list[dict[str, datetime]]:
  get_doctor_or_404(db, doctor_id)
  hours = db.scalar(select(models.WorkingHours).where(
    models.WorkingHours.doctor_id == doctor_id,
    models.WorkingHours.day_of_week == target_date.weekday(),
  ))
  if hours is None:
    return []
  cursor = datetime.combine(target_date, hours.start_time)
  limit = datetime.combine(target_date, hours.end_time)
  booked = set(db.scalars(select(models.Appointment.start_time).where(
    models.Appointment.doctor_id == doctor_id,
    models.Appointment.status == models.AppointmentStatus.BOOKED,
    models.Appointment.start_time >= datetime.combine(target_date, time.min),
    models.Appointment.start_time < datetime.combine(target_date + timedelta(days=1), time.min),
  )).all())
  slots = []
  while cursor + SLOT_LENGTH <= limit:
    if cursor not in booked:
      slots.append({"start": cursor, "end": cursor + SLOT_LENGTH})
    cursor += SLOT_LENGTH
  return slots


def cancel_appointment(db: Session, appointment_id: int, reason: str) -> models.Appointment:
  appointment = db.get(models.Appointment, appointment_id)
  if appointment is None:
    raise _not_found("Appointment")
  if appointment.status == models.AppointmentStatus.CANCELLED:
    raise HTTPException(status_code=409, detail="Appointment is already cancelled.")
  appointment.status = models.AppointmentStatus.CANCELLED
  appointment.cancellation_reason = reason
  db.commit()
  db.refresh(appointment)
  return appointment


def reschedule_appointment(db: Session, appointment_id: int, new_start_time: datetime) -> models.Appointment:
  appointment = db.get(models.Appointment, appointment_id)
  if appointment is None:
    raise _not_found("Appointment")
  if appointment.status == models.AppointmentStatus.CANCELLED:
    raise HTTPException(status_code=409, detail="A cancelled appointment cannot be rescheduled.")
  new_end_time = validate_slot(db, appointment.doctor_id, new_start_time, exclude_appointment_id=appointment.id)
  appointment.start_time = new_start_time
  appointment.end_time = new_end_time
  appointment.cancellation_reason = None
  try:
    db.commit()
  except IntegrityError:
    db.rollback()
    raise HTTPException(status_code=409, detail="This appointment slot is already booked.") from None
  db.refresh(appointment)
  return appointment
