"""
Generic base repository — provides typed CRUD operations.
All concrete repositories extend this class.
"""
from typing import Generic, TypeVar, Type
from sqlalchemy.orm import Session
from app.models import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository with standard CRUD.

    Usage:
        class UserRepository(BaseRepository[User]):
            model = User
    """

    model: Type[ModelType]

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, record_id: int) -> ModelType | None:
        return self.db.query(self.model).filter(self.model.id == record_id).first()

    def get_all(self) -> list[ModelType]:
        return self.db.query(self.model).all()

    def save(self, instance: ModelType) -> ModelType:
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def delete(self, instance: ModelType) -> None:
        self.db.delete(instance)
        self.db.commit()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
