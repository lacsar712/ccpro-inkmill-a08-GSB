from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.mill import Mill
from app.models.process_card import PROCESS_CARD_STATUSES, ProcessCard
from app.serializers import process_card_json
from app.utils import error

bp = Blueprint("process_cards", __name__, url_prefix="/api/process-cards")


def _parse_version_no(body: dict) -> int | None:
    raw = body.get("versionNo")
    try:
        version_no = int(raw)
    except (TypeError, ValueError):
        return None
    if isinstance(raw, bool) or version_no < 1:
        return None
    return version_no


def _validate(body: dict) -> str | None:
    mill_id_raw = body.get("millId")
    try:
        mill_id = int(mill_id_raw)
    except (TypeError, ValueError):
        mill_id = 0
    if mill_id <= 0:
        return "请选择研磨机"

    db = SessionLocal()
    try:
        if not db.get(Mill, mill_id):
            return "研磨机不存在"
    finally:
        db.close()

    if _parse_version_no(body) is None:
        return "版本号必须为 ≥ 1 的整数"

    content = str(body.get("content", "")).strip()
    if not content:
        return "工艺卡内容不能为空"

    status = str(body.get("status") or "draft")
    if status not in PROCESS_CARD_STATUSES:
        return "状态无效，应为 draft / published / obsolete"

    return None


def _obsolete_other_published(db, mill_id: int, exclude_id: int | None = None) -> None:
    query = db.query(ProcessCard).filter(
        ProcessCard.mill_id == mill_id,
        ProcessCard.status == "published",
    )
    if exclude_id is not None:
        query = query.filter(ProcessCard.id != exclude_id)
    for row in query.all():
        row.status = "obsolete"


@bp.get("")
@jwt_required()
def list_cards():
    mill_id_raw = request.args.get("millId")
    db = SessionLocal()
    try:
        query = db.query(ProcessCard)
        if mill_id_raw not in (None, ""):
            try:
                mill_id = int(mill_id_raw)
            except ValueError:
                return error("millId 参数无效", 400)
            query = query.filter(ProcessCard.mill_id == mill_id)
        rows = query.order_by(
            ProcessCard.mill_id.asc(), ProcessCard.version_no.desc(), ProcessCard.id.desc()
        ).all()
        return jsonify([process_card_json(r) for r in rows])
    finally:
        db.close()


@bp.post("")
@jwt_required()
def create_card():
    body = request.get_json(silent=True) or {}
    err = _validate(body)
    if err:
        return error(err, 400)

    mill_id = int(body["millId"])
    status = str(body.get("status") or "draft")

    db = SessionLocal()
    try:
        if status == "published":
            _obsolete_other_published(db, mill_id)
        row = ProcessCard(
            mill_id=mill_id,
            version_no=_parse_version_no(body),
            content=str(body["content"]).strip(),
            status=status,
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return error("该研磨机下版本号已存在", 400)
        db.refresh(row)
        return jsonify(process_card_json(row)), 201
    finally:
        db.close()


@bp.put("/<int:item_id>")
@jwt_required()
def update_card(item_id: int):
    body = request.get_json(silent=True) or {}
    err = _validate(body)
    if err:
        return error(err, 400)

    mill_id = int(body["millId"])
    status = str(body.get("status") or "draft")

    db = SessionLocal()
    try:
        row = db.get(ProcessCard, item_id)
        if not row:
            return error("工艺卡不存在", 404)

        if status == "published":
            _obsolete_other_published(db, mill_id, exclude_id=row.id)
        row.mill_id = mill_id
        row.version_no = _parse_version_no(body)
        row.content = str(body["content"]).strip()
        row.status = status
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return error("该研磨机下版本号已存在", 400)
        db.refresh(row)
        return jsonify(process_card_json(row))
    finally:
        db.close()


@bp.post("/<int:item_id>/publish")
@jwt_required()
def publish_card(item_id: int):
    db = SessionLocal()
    try:
        row = db.get(ProcessCard, item_id)
        if not row:
            return error("工艺卡不存在", 404)

        if row.status != "published":
            _obsolete_other_published(db, row.mill_id, exclude_id=row.id)
            row.status = "published"
            db.commit()
        db.refresh(row)
        return jsonify(process_card_json(row))
    finally:
        db.close()


@bp.delete("/<int:item_id>")
@jwt_required()
def delete_card(item_id: int):
    db = SessionLocal()
    try:
        row = db.get(ProcessCard, item_id)
        if not row:
            return error("工艺卡不存在", 404)
        db.delete(row)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()
