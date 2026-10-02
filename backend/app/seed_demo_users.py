from backend.app.database import SessionLocal, init_db
from backend.app.models import User, Vehicle, Battery
from backend.app.security import hash_password


# ============================================================
# CREATE DEMO USERS
# ============================================================

def create_demo_users(db):
    """
    Create the demo user and admin accounts if they don't exist.
    """

    user = (
        db.query(User)
        .filter(
            User.email == "user@evbattery.demo"
        )
        .first()
    )

    if user is None:
        user = User(
            email="user@evbattery.demo",
            name="EV Battery User",
            hashed_password=hash_password(
                "user1234"
            ),
            role="user",
            is_active=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

    admin = (
        db.query(User)
        .filter(
            User.email == "admin@evbattery.demo"
        )
        .first()
    )

    if admin is None:
        admin = User(
            email="admin@evbattery.demo",
            name="EV Battery Admin",
            hashed_password=hash_password(
                "admin1234"
            ),
            role="admin",
            is_active=True,
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

    return user, admin


# ============================================================
# CREATE 56 VEHICLES
# ============================================================

def create_fleet(db):
    """
    Create Vehicle 01 through Vehicle 56.

    Each vehicle receives exactly one battery.
    """

    user = (
        db.query(User)
        .filter(
            User.email == "user@evbattery.demo"
        )
        .first()
    )

    created_count = 0

    for number in range(1, 57):

        vehicle_id = (
            f"EV-{number:03d}"
        )

        battery_id = (
            f"BAT-{number:03d}"
        )

        # ----------------------------------------------------
        # Find existing vehicle
        # ----------------------------------------------------

        vehicle = (
            db.query(Vehicle)
            .filter(
                Vehicle.vehicle_id
                == vehicle_id
            )
            .first()
        )

        if vehicle is None:

            # Assign the demo user to Vehicle 01.
            #
            # The admin can access every vehicle.
            # A normal user will only see their assigned vehicle.

            owner_id = None

            if number == 1:
                owner_id = user.id

            vehicle = Vehicle(
                vehicle_id=vehicle_id,

                name=(
                    f"Vehicle "
                    f"{number:02d}"
                ),

                model=(
                    f"EV Model "
                    f"{((number - 1) % 5) + 1}"
                ),

                owner_id=owner_id,

                battery_count=1,

                status="ACTIVE",
            )

            db.add(vehicle)
            db.commit()
            db.refresh(vehicle)

            created_count += 1

        else:

            # Vehicle already exists.
            # Make sure Vehicle 01 remains assigned
            # to the demo user.

            if number == 1:
                vehicle.owner_id = user.id
                db.commit()


        # ----------------------------------------------------
        # Find existing battery
        # ----------------------------------------------------

        battery = (
            db.query(Battery)
            .filter(
                Battery.battery_id
                == battery_id
            )
            .first()
        )

        if battery is None:

            battery = Battery(
                battery_id=battery_id,

                vehicle_id=vehicle.id,

                name=(
                    f"Battery Pack "
                    f"{number:02d}"
                ),

                soc=80.0,

                soh=95.0,

                voltage=400.0,

                current=0.0,

                temperature=30.0,

                cycles=0,

                health="HEALTHY",

                status="ACTIVE",
            )

            db.add(battery)

        else:

            # Ensure the battery is linked
            # to the correct vehicle.

            battery.vehicle_id = vehicle.id

    db.commit()

    return created_count


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "=============================================="
    )
    print(
        " EV BATTERY INTELLIGENCE - DATABASE SEED"
    )
    print(
        "=============================================="
    )

    # Create database tables.
    init_db()

    db = SessionLocal()

    try:

        # ----------------------------------------------------
        # USERS
        # ----------------------------------------------------

        user, admin = create_demo_users(
            db
        )

        print()
        print(
            "Demo users ready."
        )

        print(
            f"USER  : {user.email}"
        )

        print(
            f"ADMIN : {admin.email}"
        )


        # ----------------------------------------------------
        # FLEET
        # ----------------------------------------------------

        created_count = create_fleet(
            db
        )

        print()
        print(
            f"Fleet ready: 56 vehicles"
        )

        print(
            f"New vehicles created: "
            f"{created_count}"
        )


        # ----------------------------------------------------
        # VERIFY
        # ----------------------------------------------------

        vehicle_count = (
            db.query(Vehicle)
            .count()
        )

        battery_count = (
            db.query(Battery)
            .count()
        )

        print()
        print(
            "Database verification:"
        )

        print(
            f"Vehicles : {vehicle_count}"
        )

        print(
            f"Batteries: {battery_count}"
        )

        print()

        if vehicle_count >= 56:
            print(
                "SUCCESS: 56 vehicles are ready."
            )
        else:
            print(
                "WARNING: Fleet is incomplete."
            )

        if battery_count >= 56:
            print(
                "SUCCESS: 56 batteries are ready."
            )
        else:
            print(
                "WARNING: Battery fleet is incomplete."
            )

        print()

    finally:

        db.close()


if __name__ == "__main__":
    main()