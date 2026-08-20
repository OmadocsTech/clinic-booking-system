from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from .models import AppointmentStatus


class AppointmentCreate(BaseModel):
  doctor_id: int = Field(gt=0)
  patient_id: int = Field(gt=0)
  start_time: datetime  # Expected format: ISO 8601


class AppointmentCancel(BaseModel):
  reason: str = Field(..., min_length=3, description="Reason for cancellation")


class AppointmentReschedule(BaseModel):
  new_start_time: datetime


class AppointmentResponse(BaseModel):
  model_config = ConfigDict(from_attributes=True)
  id: int
  doctor_id: int
  patient_id: int
  start_time: datetime
  end_time: datetime
  status: AppointmentStatus
  cancellation_reason: Optional[str] = None



class Slot(BaseModel):
  start: datetime
  end: datetime


class AvailabilityResponse(BaseModel):
  doctor_id: int
  date: date
  available_slots: list[Slot]


class PatientAppointmentsResponse(BaseModel):
  patient_id: int
  appointments: list[AppointmentResponse]
