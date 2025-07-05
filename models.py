import enum
from sqlalchemy import Column, Integer, Float, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class RequestStatus(enum.Enum):
    pending = "pending"
    accepted = "accepted"
    completed = "completed"

class StopType(enum.Enum):
    depot = "depot"
    store = "store"

class Depot(Base):
    __tablename__ = 'depots'

    id = Column(Integer, primary_key=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)

class Truck(Base):
    __tablename__ = 'trucks'

    id = Column(Integer, primary_key=True)
    capacity = Column(Integer, nullable=False)
    current_lat = Column(Float, nullable=False)
    current_lon = Column(Float, nullable=False)
    available_capacity = Column(Integer, nullable=False)

class StoreRequest(Base):
    __tablename__ = 'store_requests'

    id = Column(Integer, primary_key=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    demand = Column(Integer, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(Enum(RequestStatus), default=RequestStatus.pending, nullable=False)

class Route(Base):
    __tablename__ = 'routes'

    id = Column(Integer, primary_key=True)
    truck_id = Column(Integer, ForeignKey('trucks.id'))
    truck = relationship('Truck')
    stops = relationship('RouteStop', back_populates='route', cascade='all, delete-orphan')

class RouteStop(Base):
    __tablename__ = 'route_stops'

    id = Column(Integer, primary_key=True)
    route_id = Column(Integer, ForeignKey('routes.id'))
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    eta = Column(DateTime, nullable=True)
    stop_type = Column(Enum(StopType), nullable=False)
    completed = Column(Boolean, default=False, nullable=False)

    route = relationship('Route', back_populates='stops')
