from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum

from app.database import Base

class NodeType(enum.Enum):
    PAGE = "page"
    ACTION = "action"

class NavNode(Base):
    __tablename__ = "nav_nodes"

    id = Column(Integer, primary_key=True, index=True)
    node_type = Column(String, default=NodeType.PAGE.value) # "page" или "action"
    identifier = Column(String, unique=True, index=True) # путь (e.g. /profile) или ACTION тег
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    depth = Column(Integer, default=0)
    
    # Связи (edges, где текущий узел — источник)
    outgoing_edges = relationship("NavEdge", foreign_keys="[NavEdge.source_node_id]", back_populates="source_node")
    # Связи (edges, где текущий узел — цель)
    incoming_edges = relationship("NavEdge", foreign_keys="[NavEdge.target_node_id]", back_populates="target_node")
    
    # Роли, которым доступен узел
    access_rules = relationship("NodeAccessRule", back_populates="node", cascade="all, delete-orphan")


class NavEdge(Base):
    __tablename__ = "nav_edges"

    id = Column(Integer, primary_key=True, index=True)
    source_node_id = Column(Integer, ForeignKey("nav_nodes.id", ondelete="CASCADE"), nullable=False)
    target_node_id = Column(Integer, ForeignKey("nav_nodes.id", ondelete="CASCADE"), nullable=False)
    relationship_type = Column(String, default="navigates_to") # navigates_to, triggers_action
    weight = Column(Integer, default=1)

    source_node = relationship("NavNode", foreign_keys=[source_node_id], back_populates="outgoing_edges")
    target_node = relationship("NavNode", foreign_keys=[target_node_id], back_populates="incoming_edges")


class NodeAccessRule(Base):
    __tablename__ = "node_access_rules"

    id = Column(Integer, primary_key=True, index=True)
    nav_node_id = Column(Integer, ForeignKey("nav_nodes.id", ondelete="CASCADE"), nullable=False)
    allowed_role = Column(String, nullable=False) # "student", "teacher", "guest", "all"

    node = relationship("NavNode", back_populates="access_rules")
