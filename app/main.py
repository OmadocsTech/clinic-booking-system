from datetime import date, datetime
from fastapi import Depends, FastAPI, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import crud, models, schemas
from .database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Clinic Booking System API",
    description="Appointment scheduling for a small clinic.",
    version="1.0.0",
)


@app.get("/health", tags=["Operations"])
def health_check():
  return {"status": "ok"}


@app.post("/appointments", response_model=schemas.AppointmentResponse, status_code=status.HTTP_201_CREATED, tags=["Appointments"])
def book_appointment(payload: schemas.AppointmentCreate, db: Session = Depends(get_db)):
  return crud.create_appointment(db, payload.doctor_id, payload.patient_id, payload.start_time)


@app.get("/doctors/{id}/availability")
def get_doctor_availability(id: int, date: date, db: Session = Depends(get_db)):
  return {"doctor_id": id, "date": date, "available_slots": crud.availability(db, id, date)}


@app.patch("/appointments/{id}/cancel", response_model=schemas.AppointmentResponse)
def cancel_appointment(
    id: int, payload: schemas.AppointmentCancel, db: Session = Depends(get_db)
):
  return crud.cancel_appointment(db, id, payload.reason)


@app.patch("/appointments/{id}/reschedule", response_model=schemas.AppointmentResponse)
def reschedule_appointment(id: int, payload: schemas.AppointmentReschedule, db: Session = Depends(get_db)):
  return crud.reschedule_appointment(db, id, payload.new_start_time)


@app.get("/patients/{id}/appointments", response_model=schemas.PatientAppointmentsResponse)
def upcoming_patient_appointments(id: int, db: Session = Depends(get_db)):
  crud.get_patient_or_404(db, id)
  appointments = db.scalars(select(models.Appointment).where(
    models.Appointment.patient_id == id,
    models.Appointment.status == models.AppointmentStatus.BOOKED,
    models.Appointment.start_time >= datetime.now(),
  ).order_by(models.Appointment.start_time)).all()
  return {"patient_id": id, "appointments": appointments}
