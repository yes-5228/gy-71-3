from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.contract import ContractCreate, ContractRead, ContractUpdate
from app.services.contract_service import create_contract, get_contract, list_contracts, refund_deposit, terminate_contract, update_contract

router = APIRouter()


def serialize_contract(contract) -> dict:
    data = ContractRead.model_validate(contract).model_dump()
    data["can_terminate"] = getattr(contract, "can_terminate", True)
    data["terminate_reason"] = getattr(contract, "terminate_reason", "")
    return data


@router.get("", response_model=list[ContractRead])
def read_contracts(status: str | None = None, db: Session = Depends(get_db)):
    return [serialize_contract(c) for c in list_contracts(db, status=status)]


@router.get("/{contract_id}", response_model=ContractRead)
def read_contract(contract_id: int, db: Session = Depends(get_db)):
    contract = get_contract(db, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    return serialize_contract(contract)


@router.post("", response_model=ContractRead, status_code=status.HTTP_201_CREATED)
def sign_contract(payload: ContractCreate, db: Session = Depends(get_db)):
    try:
        contract = create_contract(db, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="合同编号冲突，请稍后重试") from exc
    except ValueError as exc:
        messages = {
            "workstation_not_found": "工位不存在",
            "workstation_not_available": "工位当前不可租赁",
            "invalid_contract_dates": "合同结束日期必须晚于开始日期",
        }
        raise HTTPException(status_code=400, detail=messages.get(str(exc), "合同数据无效")) from exc
    return serialize_contract(contract)


@router.patch("/{contract_id}", response_model=ContractRead)
def edit_contract(contract_id: int, payload: ContractUpdate, db: Session = Depends(get_db)):
    try:
        contract = update_contract(db, contract_id, payload)
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith("termination_blocked:"):
            raise HTTPException(status_code=400, detail=msg.split(":", 1)[1])
        raise HTTPException(status_code=400, detail="合同更新失败")
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    return serialize_contract(contract)


@router.post("/{contract_id}/refund-deposit", response_model=ContractRead)
def refund_deposit_endpoint(contract_id: int, db: Session = Depends(get_db)):
    try:
        contract = refund_deposit(db, contract_id)
    except ValueError as exc:
        if str(exc) == "deposit_already_refunded":
            raise HTTPException(status_code=400, detail="押金已退还，无需重复操作")
        raise HTTPException(status_code=400, detail="押金退还失败")
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    return serialize_contract(contract)


@router.post("/{contract_id}/terminate", response_model=ContractRead)
def terminate_contract_endpoint(contract_id: int, db: Session = Depends(get_db)):
    try:
        contract = terminate_contract(db, contract_id)
    except ValueError as exc:
        msg = str(exc)
        if msg == "contract_not_found":
            raise HTTPException(status_code=404, detail="合同不存在")
        if msg.startswith("termination_blocked:"):
            raise HTTPException(status_code=400, detail=msg.split(":", 1)[1])
        raise HTTPException(status_code=400, detail="合同终止失败")
    return serialize_contract(contract)
