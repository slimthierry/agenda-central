from typing import Generic, TypeVar
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


def paginate(session: Session, model, conditions, order_by, page: int = 1, page_size: int = 20):
    offset = (page - 1) * page_size

    # Count total
    count_query = select(func.count()).select_from(model).where(*conditions)
    total = session.scalar(count_query)

    # Get items
    query = select(model).where(*conditions).order_by(*order_by).offset(offset).limit(page_size)
    items = session.scalars(query).all()

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
