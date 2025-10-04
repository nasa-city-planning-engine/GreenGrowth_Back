from flask import Blueprint, jsonify, request
from models import Message, User, Tag, db

message_bp = Blueprint("messages", __name__, url_prefix="/messages")


@message_bp.post("/")
def create_message():

    data = request.get_json()

    if not data:
        return jsonify(
            {
                "status": "error",
                "message": "The body of the request is empty",
                "payload": None,
            }
        )

    try:

        new_message = Message(
            content=data["content"],
            latitude=data["latitude"],
            longitude=data["longitude"],
            location=data["location"],
            user_id=data["user_id"],
            tags=[
                Tag.query.filter_by(name=tag).first() for tag in data.get("tags", [])
            ],
        )

        db.session.add(new_message)
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"Message with id {new_message.id} created successfully",
                    "payload": {
                        "id": new_message.id,
                        "content": new_message.content,
                        "latitude": new_message.latitude,
                        "longitude": new_message.longitude,
                        "location": new_message.location,
                        "tags": [tag.name for tag in new_message.tags],
                    },
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e), "payload": None}), 500

    return new_message


@message_bp.get("/")
def get_messages():
    try:
        messages = Message.query.all()
        messages_list = []
        for message in messages:
            messages_list.append(
                {
                    "id": message.id,
                    "content": message.content,
                    "latitude": message.latitude,
                    "longitude": message.longitude,
                    "location": message.location,
                    "tags": [tag.name for tag in message.tags],
                }
            )

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Messages retrieved successfully",
                    "payload": messages_list,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "payload": None}), 500


@message_bp.get("/<int:message_id>")
def get_message(message_id):
    try:
        message = Message.query.get_or_404(message_id)

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Message retrieved successfully",
                    "payload": {
                        "id": message.id,
                        "content": message.content,
                        "latitude": message.latitude,
                        "longitude": message.longitude,
                        "location": message.location,
                        "tags": [tag.name for tag in message.tags],
                    },
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "payload": None}), 500


@message_bp.get("/get-messages-by-location")
def get_messages_by_location():
    location = request.args.get("location")

    if not location:
        return jsonify(
            {
                "status": "error",
                "message": "Location is required",
                "payload": None,
            }
        ), 400

    try:
        messages = Message.query.filter_by(location=location).all()
        messages_list = []
        for message in messages:
            messages_list.append(
                {
                    "id": message.id,
                    "content": message.content,
                    "latitude": message.latitude,
                    "longitude": message.longitude,
                    "location": message.location,
                    "tags": [tag.name for tag in message.tags],
                }
            )

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Messages retrieved successfully",
                    "payload": messages_list,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "payload": None}), 500


message_bp.delete("/<int:message_id>")


def delete_message(message_id):
    try:
        message = Message.query.get_or_404(message_id)
        db.session.delete(message)
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"Message with id {message_id} deleted successfully",
                    "payload": None,
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e), "payload": None}), 500


message_bp.put("/<int:message_id>")


def update_message(message_id):
    data = request.get_json()

    if not data:
        return jsonify(
            {
                "status": "error",
                "message": "The body of the request is empty",
                "payload": None,
            }
        )

    try:
        message = Message.query.get_or_404(message_id)

        message.content = data.get("content", message.content)
        message.latitude = data.get("latitude", message.latitude)
        message.longitude = data.get("longitude", message.longitude)
        message.location = data.get("location", message.location)
        if "tags" in data:
            message.tags = [
                Tag.query.filter_by(name=tag).first() for tag in data["tags"]
            ]

        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"Message with id {message_id} updated successfully",
                    "payload": {
                        "id": message.id,
                        "content": message.content,
                        "latitude": message.latitude,
                        "longitude": message.longitude,
                        "location": message.location,
                        "tags": [tag.name for tag in message.tags],
                    },
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e), "payload": None}), 500
