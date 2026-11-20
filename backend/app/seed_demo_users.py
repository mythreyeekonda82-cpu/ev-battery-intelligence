from .database import SessionLocal, init_db
from .models import User, Vehicle, Battery
from .security import hash_password, verify_password


# ============================================================
# CREATE OR UPDATE DEMO USERS
# ============================================================

def create_demo_users(db):

    accounts = [
        {
            "email": "user@evbattery.demo",
            "name": "EV Battery User",
            "password": "user1234",
            "role": "user"
        },
        {
            "email": "admin@evbattery.demo",
            "name": "EV Battery Admin",
            "password": "admin1234",
            "role": "admin"
        }
    ]

    result = {}

    for account in accounts:

        user = (
            db.query(User)
            .filter(
                User.email == account["email"]
            )
            .first()
        )

        if user is None:

            user = User(
                email=account["email"],
                name=account["name"],
                hashed_password=hash_password(
                    account["password"]
                ),
                role=account["role"],
                is_active=True
            )

            db.add(user)
            db.commit()
            db.refresh(user)

        else:

            if not verify_password(
                account["password"],
                user.hashed_password
            ):

                user.hashed_password = hash_password(
                    account["password"]
                )

            user.name = account["name"]
            user.role = account["role"]
            user.is_active = True

            db.commit()
            db.refresh(user)

        result[account["role"]] = user

    return result["user"], result["admin"]


# ============================================================
# CREATE 56 VEHICLES AND 56 BATTERIES
# ============================================================

def create_fleet(db):

    user = (
        db.query(User)
        .filter(
            User.email == "user@evbattery.demo"
        )
        .first()
    )

    created_count = 0

    for number in range(1, 57):

        vehicle_id = f"EV-{number:03d}"
        battery_id = f"BAT-{number:03d}"

        vehicle = (
            db.query(Vehicle)
            .filter(
                Vehicle.vehicle_id == vehicle_id
            )
            .first()
        )

        if vehicle is None:

            vehicle = Vehicle(
                vehicle_id=vehicle_id,
                name=f"Vehicle {number:02d}",
                model=f"EV Model {((number-1) % 5)+1}",
                owner_id=user.id if number == 1 else None,
                battery_count=1,
                status="ACTIVE"
            )

            db.add(vehicle)
            db.flush()

            created_count += 1

        elif number == 1:

            vehicle.owner_id = user.id

        battery = (
            db.query(Battery)
            .filter(
                Battery.battery_id == battery_id
            )
            .first()
        )

        if battery is None:

            battery = Battery(
                battery_id=battery_id,
                vehicle_id=vehicle.id,
                name=f"Battery Pack {number:02d}",
                soc=80.0,
                soh=95.0,
                voltage=400.0,
                current=0.0,
                temperature=30.0,
                cycles=0,
                health="HEALTHY",
                status="ACTIVE"
            )

            db.add(battery)

        else:

            battery.vehicle_id = vehicle.id

    db.commit()

    return created_count


# ============================================================
# MAIN
# ============================================================

def main():

    print("===================================")
    print(" VOLTIQ DATABASE INITIALIZATION")
    print("===================================")

    init_db()

    db = SessionLocal()

    try:

        user, admin = create_demo_users(db)

        print("\nUSER ACCOUNT:")
        print(user.email)

        print("\nADMIN ACCOUNT:")
        print(admin.email)

        created = create_fleet(db)

        vehicle_count = db.query(Vehicle).count()
        battery_count = db.query(Battery).count()

        print("\nFLEET INFORMATION")

        print("Vehicles:", vehicle_count)
        print("Batteries:", battery_count)
        print("New vehicles:", created)

        if vehicle_count >= 56 and battery_count >= 56:
            print("\nSUCCESS: VOLTIQ DATABASE READY")

        else:
            print("\nWARNING: CHECK DATABASE")

    finally:

        db.close()


if __name__ == "__main__":
    main()