"""
Track C owns this file.

Schema matches the synopsis's "Database Design" section exactly. Extend as
needed but keep these tables — your guide will likely check the report
against the actual schema.
"""

from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    budget_preferences = Column(Float, nullable=True)


class RoomPhoto(Base):
    __tablename__ = "room_photos"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    storage_path = Column(String, nullable=False)
    upload_date = Column(DateTime, default=datetime.datetime.utcnow)


class Detection(Base):
    __tablename__ = "detections"
    id = Column(Integer, primary_key=True)
    photo_id = Column(Integer, ForeignKey("room_photos.id"), nullable=False)
    furniture_type = Column(String, nullable=False)
    bounding_box = Column(String, nullable=False)  # store as "x1,y1,x2,y2"
    confidence = Column(Float, nullable=False)


class StylePalette(Base):
    __tablename__ = "style_palette"
    id = Column(Integer, primary_key=True)
    photo_id = Column(Integer, ForeignKey("room_photos.id"), nullable=False)
    style_label = Column(String, nullable=False)
    style_confidence = Column(Float, nullable=False)
    dominant_colors = Column(String, nullable=False)  # comma-separated hex codes


class CatalogItem(Base):
    __tablename__ = "catalog_items"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    style_tags = Column(String, nullable=True)   # comma-separated
    color_tags = Column(String, nullable=True)    # comma-separated
    retailer_id = Column(Integer, ForeignKey("store_locations.id"), nullable=True)


class Recommendation(Base):
    __tablename__ = "recommendations"
    id = Column(Integer, primary_key=True)
    photo_id = Column(Integer, ForeignKey("room_photos.id"), nullable=False)
    catalog_item_id = Column(Integer, ForeignKey("catalog_items.id"), nullable=False)
    score = Column(Float, nullable=False)
    explanation_text = Column(String, nullable=True)


class StoreLocation(Base):
    __tablename__ = "store_locations"
    id = Column(Integer, primary_key=True)
    retailer_id = Column(String, nullable=False)
    category = Column(String, nullable=False)
    retailer_name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    distance_cache = Column(Float, nullable=True)
    cached_at = Column(DateTime, nullable=True)
