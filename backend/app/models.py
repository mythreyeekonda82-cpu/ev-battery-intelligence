from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)

from .database import Base


# ============================================================
# USER
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    name = Column(
        String,
        nullable=False,
    )

    hashed_password = Column(
        String,
        nullable=False,
    )

    role = Column(
        String,
        default="user",
        nullable=False,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


# ============================================================
# VEHICLE
# ============================================================

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    vehicle_id = Column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )

    name = Column(
        String(150),
        nullable=False,
        default="EV Vehicle",
    )

    model = Column(
        String(150),
        nullable=True,
    )

    # User who owns/is assigned this vehicle.
    # Admin vehicles can have no assigned user.
    owner_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    battery_count = Column(
        Integer,
        default=1,
        nullable=False,
    )

    status = Column(
        String(50),
        default="ACTIVE",
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


# ============================================================
# BATTERY
# ============================================================

class Battery(Base):
    __tablename__ = "batteries"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    battery_id = Column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )

    vehicle_id = Column(
        Integer,
        ForeignKey("vehicles.id"),
        nullable=True,
        index=True,
    )

    name = Column(
        String(150),
        nullable=False,
    )

    soc = Column(
        Float,
        default=80.0,
    )

    soh = Column(
        Float,
        default=95.0,
    )

    voltage = Column(
        Float,
        default=400.0,
    )

    current = Column(
        Float,
        default=0.0,
    )

    temperature = Column(
        Float,
        default=30.0,
    )

    cycles = Column(
        Integer,
        default=0,
    )

    health = Column(
        String(50),
        default="HEALTHY",
    )

    status = Column(
        String(50),
        default="ACTIVE",
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


# ============================================================
# TELEMETRY
# ============================================================

class Telemetry(Base):
    __tablename__ = "telemetry"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    battery_id = Column(
        String(50),
        index=True,
        nullable=False,
    )

    voltage = Column(
        Float,
        nullable=False,
    )

    current = Column(
        Float,
        nullable=False,
    )

    temperature = Column(
        Float,
        nullable=False,
    )

    soc = Column(
        Float,
        nullable=False,
    )

    soh = Column(
        Float,
        nullable=False,
    )

    cycles = Column(
        Integer,
        default=0,
    )

    power_kw = Column(
        Float,
        default=0.0,
    )

    timestamp = Column(
        DateTime,
        default=datetime.utcnow,
        index=True,
        nullable=False,
    )


# ============================================================
# ALERT
# ============================================================

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    battery_id = Column(
        String(50),
        nullable=True,
        index=True,
    )

    alert_type = Column(
        String(100),
        nullable=False,
    )

    severity = Column(
        String(50),
        default="INFO",
    )

    message = Column(
        Text,
        nullable=False,
    )

    is_read = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        index=True,
        nullable=False,
    )


# ============================================================
# USER SETTINGS
# ============================================================

class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
    )

    temperature_warning = Column(
        Float,
        default=40.0,
    )

    temperature_critical = Column(
        Float,
        default=45.0,
    )

    soc_warning = Column(
        Float,
        default=20.0,
    )

    soh_warning = Column(
        Float,
        default=85.0,
    )

    email_enabled = Column(
        Boolean,
        default=True,
    )

    whatsapp_enabled = Column(
        Boolean,
        default=False,
    )

    weekly_reports = Column(
        Boolean,
        default=True,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


# ============================================================
# NOTIFICATION LOG
# ============================================================

class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    channel = Column(
        String(50),
        nullable=False,
    )

    recipient = Column(
        String(255),
        nullable=False,
    )

    message = Column(
        Text,
        nullable=False,
    )

    status = Column(
        String(50),
        default="QUEUED",
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )