from math import ceil
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import (
    QuotationTemplate, QuotationTemplateLine, Product, ProductVariant, Plan, User
)
from backend.app.schemas import (
    QuotationTemplateCreate, QuotationTemplateUpdate, QuotationTemplateResponse, PaginatedResponse
)
from backend.app.deps import get_current_user, require_roles

router = APIRouter(prefix="/quotation-templates", tags=["Quotation Templates"])


@router.get("", response_model=PaginatedResponse[QuotationTemplateResponse])
def list_quotation_templates(
    search: Optional[str] = Query(None, description="Search template name"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists reusable quotation templates with nested line items."""
    query = db.query(QuotationTemplate)
    if search:
        query = query.filter(QuotationTemplate.name.ilike(f"%{search.strip()}%"))

    total = query.count()
    items = query.order_by(QuotationTemplate.name.asc()).offset((page - 1) * size).limit(size).all()
    pages = ceil(total / size) if total > 0 else 1

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages
    }


@router.post("", response_model=QuotationTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_quotation_template(
    req: QuotationTemplateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "staff"))
):
    """
    Staff/Admin: Creates a reusable quotation template and its item lines in a single transaction.
    Validates that:
    1. The specified plan exists.
    2. Every line product exists.
    3. If a variant is specified, it strictly belongs to that product.
    """
    if req.plan_id:
        plan = db.query(Plan).filter(Plan.id == req.plan_id).first()
        if not plan:
            raise HTTPException(status_code=400, detail="Specified plan_id does not exist")

    # Validate all lines before creating
    for idx, line in enumerate(req.lines):
        product = db.query(Product).filter(Product.id == line.product_id).first()
        if not product:
            raise HTTPException(status_code=400, detail=f"Line {idx + 1}: Product {line.product_id} does not exist")

        if line.variant_id:
            variant = db.query(ProductVariant).filter(
                ProductVariant.id == line.variant_id,
                ProductVariant.product_id == line.product_id
            ).first()
            if not variant:
                raise HTTPException(
                    status_code=400,
                    detail=f"Line {idx + 1}: Variant {line.variant_id} does not belong to product {line.product_id}"
                )

        if line.quantity <= 0:
            raise HTTPException(status_code=400, detail=f"Line {idx + 1}: Quantity must be greater than 0")

    template = QuotationTemplate(
        name=req.name.strip(),
        validity_days=req.validity_days,
        plan_id=req.plan_id
    )
    db.add(template)
    db.flush()

    for line in req.lines:
        t_line = QuotationTemplateLine(
            template_id=template.id,
            product_id=line.product_id,
            variant_id=line.variant_id,
            quantity=line.quantity
        )
        db.add(t_line)

    db.commit()
    db.refresh(template)
    return template


@router.get("/{id}", response_model=QuotationTemplateResponse)
def get_quotation_template(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetches full quotation template details with lines and plan."""
    template = db.query(QuotationTemplate).filter(QuotationTemplate.id == id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Quotation template not found")
    return template


@router.patch("/{id}", response_model=QuotationTemplateResponse)
def update_quotation_template(
    id: int,
    req: QuotationTemplateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "staff"))
):
    """Admin/Staff: Updates quotation template and its nested line items."""
    template = db.query(QuotationTemplate).filter(QuotationTemplate.id == id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Quotation template not found")

    if req.name is not None:
        template.name = req.name.strip()
    if req.validity_days is not None:
        template.validity_days = req.validity_days
    if req.plan_id is not None:
        template.plan_id = req.plan_id

    if req.lines is not None:
        # Validate lines
        for idx, line in enumerate(req.lines):
            prod = db.query(Product).filter(Product.id == line.product_id).first()
            if not prod:
                raise HTTPException(status_code=400, detail=f"Line {idx + 1}: Product not found")
            if line.quantity <= 0:
                raise HTTPException(status_code=400, detail=f"Line {idx + 1}: Quantity must be greater than 0")

        # Replace lines
        db.query(QuotationTemplateLine).filter(QuotationTemplateLine.template_id == template.id).delete()
        for line in req.lines:
            t_line = QuotationTemplateLine(
                template_id=template.id,
                product_id=line.product_id,
                variant_id=line.variant_id,
                quantity=line.quantity
            )
            db.add(t_line)

    db.commit()
    db.refresh(template)
    return template


@router.delete("/{id}")
def delete_quotation_template(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "staff"))
):
    """Admin/Staff: Deletes quotation template."""
    template = db.query(QuotationTemplate).filter(QuotationTemplate.id == id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Quotation template not found")

    db.delete(template)
    db.commit()
    return {"message": f"Quotation template '{template.name}' deleted successfully"}
