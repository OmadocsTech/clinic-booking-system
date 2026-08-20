import enum
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, String, Time
from sqlalchemy.orm import relationship
from .database import Base


class AppointmentStatus(str, enum.Enum):
  BOOKED = "BOOKED"
  CANCELLED = "CANCELLED"


class Doctor(Base):
  __tablename__ = "doctors"

  id = Column(Integer, primary_key=True, index=True)
  name = Column(String, nullable=False)
  specialization = Column(String, nullable=False)

  working_hours = relationship("WorkingHours", back_populates="doctor")
  appointments = relationship("Appointment", back_populates="doctor")


class WorkingHours(Base):
  __tablename__ = "working_hours"
  __table_args__ = (Index("uq_doctor_weekday", "doctor_id", "day_of_week", unique=True),)

  id = Column(Integer, primary_key=True, index=True)
  doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
  day_of_week = Column(
      Integer, nullable=False
  )  # 0 = Monday, 6 = Sunday
  start_time = Column(Time, nullable=False)
  end_time = Column(Time, nullable=False)

  doctor = relationship("Doctor", back_populates="working_hours")


class Patient(Base):
  __tablename__ = "patients"

  id = Column(Integer, primary_key=True, index=True)
  name = Column(String, nullable=False)
  email = Column(String, unique=True, index=True, nullable=False)

  appointments = relationship("Appointment", back_populates="patient")


class Appointment(Base):
  __tablename__ = "appointments"
  __table_args__ = (
      Index("ix_appointments_doctor_start", "doctor_id", "start_time"),
  )

  id = Column(Integer, primary_key=True, index=True)
  doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
  patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
  start_time = Column(DateTime, nullable=False, index=True)
  end_time = Column(DateTime, nullable=False)
  status = Column(
      Enum(AppointmentStatus),
      default=AppointmentStatus.BOOKED,
      nullable=False,
  )
  cancellation_reason = Column(String, nullable=True)

  doctor = relationship("Doctor", back_populates="appointments")
  patient = relationship("Patient", back_populates="appointments")


# Database-level guard against concurrent active bookings. A cancelled booking
# does not participate in this partial unique index, so its slot is reusable.
Index(
    "uq_active_appointment_slot",
    Appointment.doctor_id,
    Appointment.start_time,
    unique=True,
    sqlite_where=(Appointment.status == AppointmentStatus.BOOKED),
    postgresql_where=(Appointment.status == AppointmentStatus.BOOKED),
)
