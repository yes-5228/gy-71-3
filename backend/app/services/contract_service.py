from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.contract import Contract
from app.models.payment import Payment
from app.models.workstation import Workstation
from app.schemas.contract import ContractCreate, ContractUpdate


def _get_unpaid_payment_count(db: Session, contract_id: int) -> int:
    stmt = select(Payment).where(
        Payment.contract_id == contract_id,
        Payment.status.in_(["unpaid", "overdue"]),
    )
    return len(list(db.scalars(stmt).all()))


def _get_deposit_unhandled(contract: Contract) -> bool:
    return contract.deposit > 0 and contract.deposit_status != "refunded"


def validate_contract_end(db: Session, contract: Contract, target_status: str) -> tuple[bool, str]:
    if contract.status != "active":
        return False, "只有履行中的合同可以变更为结束状态"
    action_label = "终止合同" if target_status == "terminated" else "设置合同到期"
    unpaid_count = _get_unpaid_payment_count(db, contract.id)
    if unpaid_count > 0:
        return False, f"存在 {unpaid_count} 笔未结清账单，请先处理完毕后再{action_label}"
    if _get_deposit_unhandled(contract):
        return False, f"存在未处理押金，请先退还押金后再{action_label}"
    return True, ""


def enrich_contract_termination_flag(db: Session, contracts: list[Contract]) -> list[Contract]:
    for contract in contracts:
        if contract.status == "active":
            can_terminate, reason = validate_contract_end(db, contract, "terminated")
            contract.can_terminate = can_terminate
            contract.terminate_reason = reason
        else:
            contract.can_terminate = False
            contract.terminate_reason = ""
    return contracts


def list_contracts(db: Session, status: str | None = None) -> list[Contract]:
    stmt = (
        select(Contract)
        .options(joinedload(Contract.workstation))
        .order_by(Contract.end_date.asc())
    )
    if status:
        stmt = stmt.where(Contract.status == status)
    contracts = list(db.scalars(stmt).all())
    return enrich_contract_termination_flag(db, contracts)


def get_contract(db: Session, contract_id: int) -> Contract | None:
    stmt = (
        select(Contract)
        .options(joinedload(Contract.workstation))
        .where(Contract.id == contract_id)
    )
    contract = db.scalars(stmt).first()
    if contract:
        enrich_contract_termination_flag(db, [contract])
    return contract


def create_contract(db: Session, payload: ContractCreate) -> Contract:
    workstation = db.get(Workstation, payload.workstation_id)
    if not workstation:
        raise ValueError("workstation_not_found")
    if workstation.status not in {"available", "reserved"}:
        raise ValueError("workstation_not_available")
    if payload.end_date <= payload.start_date:
        raise ValueError("invalid_contract_dates")

    contract = Contract(
        **payload.model_dump(),
        contract_no=f"CT-{date.today().strftime('%Y%m%d')}-{payload.workstation_id:03d}",
        status="active",
        deposit_status="unhandled" if payload.deposit > 0 else "refunded",
    )
    workstation.status = "leased"
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


def update_contract(db: Session, contract_id: int, payload: ContractUpdate) -> Contract | None:
    contract = db.get(Contract, contract_id)
    if not contract:
        return None

    update_data = payload.model_dump(exclude_unset=True)

    if "deposit_status" in update_data:
        raise ValueError("deposit_status_modify_forbidden:押金状态不能通过编辑接口修改，请走专门的押金退还操作")

    new_status = update_data.get("status")
    current_status = contract.status
    will_terminate = new_status == "terminated" and current_status != "terminated"
    will_expire = new_status == "expired" and current_status != "expired"

    if will_terminate or will_expire:
        target_status = "terminated" if will_terminate else "expired"
        can_end, reason = validate_contract_end(db, contract, target_status)
        if not can_end:
            prefix = "termination_blocked:" if will_terminate else "expire_blocked:"
            raise ValueError(f"{prefix}{reason}")

    try:
        for key, value in update_data.items():
            setattr(contract, key, value)
        if contract.status in {"terminated", "expired"} and contract.workstation:
            contract.workstation.status = "available"
        db.commit()
        db.refresh(contract)
        return contract
    except ValueError:
        raise
    except Exception:
        db.rollback()
        raise


def refund_deposit(db: Session, contract_id: int) -> Contract | None:
    contract = db.get(Contract, contract_id)
    if not contract:
        return None
    if contract.deposit_status == "refunded":
        raise ValueError("deposit_already_refunded")
    contract.deposit_status = "refunded"
    db.commit()
    db.refresh(contract)
    return contract


def terminate_contract(db: Session, contract_id: int) -> Contract:
    contract = db.get(Contract, contract_id)
    if not contract:
        raise ValueError("contract_not_found")

    can_terminate, reason = validate_contract_end(db, contract, "terminated")
    if not can_terminate:
        raise ValueError(f"termination_blocked:{reason}")

    try:
        contract.status = "terminated"
        if contract.workstation:
            contract.workstation.status = "available"
        db.commit()
        db.refresh(contract)
        return contract
    except Exception:
        db.rollback()
        raise


def expiring_contracts(db: Session, days: int) -> list[Contract]:
    today = date.today()
    until = date.fromordinal(today.toordinal() + days)
    stmt = (
        select(Contract)
        .options(joinedload(Contract.workstation))
        .where(Contract.status == "active", Contract.end_date >= today, Contract.end_date <= until)
        .order_by(Contract.end_date.asc())
    )
    contracts = list(db.scalars(stmt).all())
    return enrich_contract_termination_flag(db, contracts)
