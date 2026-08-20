"""Create five sample doctors, weekday hours, and one sample patient."""
from datetime import time
from .database import Base, SessionLocal, engine
from .models import Doctor, Patient, WorkingHours


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(Doctor).count():
            doctors = [Doctor(name=name, specialization=specialization) for name, specialization in [
                ("Dr. Wanjiku Kamau", "General Medicine"), ("Dr. David Otieno", "Paediatrics"),
                ("Dr. Aisha Noor", "Dermatology"), ("Dr. Peter Mwangi", "Cardiology"),
                ("Dr. Grace Njeri", "Family Medicine")]]
            db.add_all(doctors); db.flush()
            for doctor in doctors:
                for weekday in range(5):
                    db.add(WorkingHours(doctor_id=doctor.id, day_of_week=weekday, start_time=time(9), end_time=time(17)))
        if not db.query(Patient).filter_by(email="demo.patient@example.com").first():
            db.add(Patient(name="Demo Patient", email="demo.patient@example.com"))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
