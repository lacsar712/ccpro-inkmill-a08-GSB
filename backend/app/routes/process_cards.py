from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.mill import Mill
from app.models.process_card import ProcessCard
from app.serializers import process_card_json
from app.utils import error

bp = Blueprint("process_cards", __name__, url_prefix="/api/process-cards")


def _validate(body: dict) -> str | None:
    mill_id = int(body.get("millId") or 0)
    if mill_id <= 0:
        return "请选择研磨机"

    try:
        version_no = int(body.get("versionNo"))
    except (TypeError, ValueError):
        return "版本号必须为正整数"
    if version_no <= 0:
        return "版本号必须为正整数"

    content = str(body.get("content") or "").strip()
    if not content:
        return "工艺卡内容不能为空"

    db = SessionLocal()
    try:
        if not db.get(Mill, mill_id):
            return "研磨机不存在"
    finally:
        db.close()

    return None


@bp.get("")
@jwt_required()
def list_cards():
    mill_id = request.args.get("millId", type=int)
    db = SessionLocal()
    try:
        query = db.query(ProcessCard)
        if mill_id:
            query = query.filter(ProcessCard.mill_id == mill_id)
        rows = query.order_by(
            ProcessCard.mill_id.asc(),
            ProcessCard.version_no.desc(),
            ProcessCard.id.desc(),
        ).all()
        return jsonify([process_card_json(r) for r in rows])
    finally:
        db.close()


@bp.get("/<int:item_id>")
@jwt_required()
def get_card(item_id: int):
    db = SessionLocal()
    try:
        row = db.get(ProcessCard, item_id)
        if not row:
            return error("工艺卡不存在", 404)
        return jsonify(process_card_json(row))
    finally:
        db.close()


@bp.post("")
@jwt_required()
def create_card():
    body = request.get_json(silent=True) or {}
    err = _validate(body)
    if err:
        return error(err, 400)

    db = SessionLocal()
    try:
        row = ProcessCard(
            mill_id=int(body["millId"]),
            version_no=int(body["versionNo"]),
            content=str(body["content"]).strip(),
            status="draft",
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return error("该机台已存在相同版本号", 400)
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

    db = SessionLocal()
    try:
        row = db.get(ProcessCard, item_id)
        if not row:
            return error("工艺卡不存在", 404)
        if row.status != "draft":
            return error("仅草稿状态可编辑，请新建版本", 400)

        row.mill_id = int(body["millId"])
        row.version_no = int(body["versionNo"])
        row.content = str(body["content"]).strip()
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return error("该机台已存在相同版本号", 400)
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
        if row.status != "draft":
            return error("仅草稿状态可删除", 400)
        db.delete(row)
        db.commit()
        return jsonify({"ok": True})
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
        if row.status == "published":
            return error("该工艺卡已发布", 400)
        if row.status == "obsolete":
            return error("已作废工艺卡不能重新发布，请新建版本", 400)

        # 锁住机台行，串行化该机台的发布动作，保证同时最多一个 published
        db.query(Mill).filter(Mill.id == row.mill_id).with_for_update().one()

        (
            db.query(ProcessCard)
            .filter(
                ProcessCard.mill_id == row.mill_id,
                ProcessCard.status == "published",
                ProcessCard.id != row.id,
            )
            .update({"status": "obsolete"}, synchronize_session=False)
        )
        row.status = "published"
        db.commit()
        db.refresh(row)
        return jsonify(process_card_json(row))
    finally:
        db.close()
