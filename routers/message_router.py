
# routers/message_router.py
#
# This module defines the API endpoints for managing messages.

from flask import Blueprint, jsonify, request
from sqlalchemy import func
from models import Message, User, Tag, db, message_tags

# Define the Blueprint for message-related routes
message_bp = Blueprint("messages", __name__, url_prefix="/messages")


# Endpoint: POST /messages/
# Create a new message
@message_bp.post("/")
def create_message():
    data = request.get_json()

    if not data:
        return jsonify({
            "status": "error",
            "message": "The body of the request is empty",
            "payload": None,
        })

    try:
        # Create a new Message instance from request data
        new_message = Message(
            content=data["content"],
            latitude=data["latitude"],
            longitude=data["longitude"],
            location=data["location"],
            user_id=data["user_id"],
            tags=[Tag.query.filter_by(name=tag).first() for tag in data.get("tags", [])],
        )

        db.session.add(new_message)
        db.session.commit()

        return (
            jsonify({
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
            }),
            201,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e), "payload": None}), 500


# Endpoint: GET /messages/
# Retrieve all messages
@message_bp.get("/")
def get_messages():
    try:
        messages = Message.query.all()
        messages_list = []
        for message in messages:
            messages_list.append({
                "id": message.id,
                "content": message.content,
                "latitude": message.latitude,
                "longitude": message.longitude,
                "location": message.location,
                "tags": [tag.name for tag in message.tags],
            })

        return (
            jsonify({
                "status": "success",
                "message": "Messages retrieved successfully",
                "payload": messages_list,
            }),
            200,
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "payload": None}), 500


# Endpoint: GET /messages/<message_id>
# Retrieve a single message by its ID
@message_bp.get("/<int:message_id>")
def get_message(message_id):
    try:
        message = Message.query.get_or_404(message_id)
        return (
            jsonify({
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
            }),
            200,
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "payload": None}), 500


# Endpoint: GET /messages/get-messages-by-location
# Retrieve messages filtered by location
@message_bp.get("/get-messages-by-location")
def get_messages_by_location():
    location = request.args.get("location")

    if not location:
        return (
            jsonify({
                "status": "error",
                "message": "Location is required",
                "payload": None,
            }),
            400,
        )

    try:
        messages = Message.query.filter_by(location=location).all()
        messages_list = []
        for message in messages:
            messages_list.append({
                "id": message.id,
                "content": message.content,
                "latitude": message.latitude,
                "longitude": message.longitude,
                "location": message.location,
                "tags": [tag.name for tag in message.tags],
            })

        return (
            jsonify({
                "status": "success",
                "message": "Messages retrieved successfully",
                "payload": messages_list,
            }),
            200,
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "payload": None}), 500


# Endpoint: DELETE /messages/<message_id>
# Delete a message by its ID
@message_bp.delete("/<int:message_id>")
def delete_message(message_id):
    try:
        message = Message.query.get_or_404(message_id)
        db.session.delete(message)
        db.session.commit()
        return (
            jsonify({
                "status": "success",
                "message": f"Message with id {message_id} deleted successfully",
                "payload": None,
            }),
            200,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e), "payload": None}), 500


# Endpoint: PUT /messages/<message_id>
# Update a message by its ID
@message_bp.put("/<int:message_id>")
def update_message(message_id):
    data = request.get_json()

    if not data:
        return jsonify({
            "status": "error",
            "message": "The body of the request is empty",
            "payload": None,
        })

    try:
        message = Message.query.get_or_404(message_id)

        # Update fields if present in request
        message.content = data.get("content", message.content)
        message.latitude = data.get("latitude", message.latitude)
        message.longitude = data.get("longitude", message.longitude)
        message.location = data.get("location", message.location)
        if "tags" in data:
            message.tags = [Tag.query.filter_by(name=tag).first() for tag in data["tags"]]

        db.session.commit()

        return (
            jsonify({
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
            }),
            200,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e), "payload": None}), 500


# Endpoint: GET /messages/get-messages-by-tag
# Retrieve messages filtered by tags (supports 'any' or 'all' match modes)
@message_bp.get("/get-messages-by-tag")
def get_messages_by_tags():
    tags_param = request.args.get("tags", "")
    match_mode = request.args.get("match", "any").lower()  # 'any' or 'all'

    if not tags_param:
        return (
            jsonify({
                "status": "error",
                "message": "Missing 'tags' query parameter",
                "payload": None,
            }),
            400,
        )

    tag_names = [t.strip() for t in tags_param.split(",") if t.strip()]
    if not tag_names:
        return (
            jsonify({
                "status": "error",
                "message": "No valid tags provided",
                "payload": None,
            }),
            400,
        )

    try:
        if match_mode == "all":
            # Messages that have ALL provided tags
            messages = (
                Message.query.join(message_tags)
                .join(Tag)
                .filter(Tag.name.in_(tag_names))
                .group_by(Message.id)
                .having(func.count(Tag.id) == len(tag_names))
                .all()
            )
        else:
            # Messages that have ANY of the provided tags
            messages = Message.query.filter(
                Message.tags.any(Tag.name.in_(tag_names))
            ).all()

        payload = [
            {
                "id": m.id,
                "content": m.content,
                "latitude": getattr(m, "latitude", None),
                "longitude": getattr(m, "longitude", None),
                "location": getattr(m, "location", None),
                "tags": [t.name for t in m.tags],
            }
            for m in messages
        ]

        return (
            jsonify({
                "status": "success",
                "message": "Messages retrieved",
                "payload": payload,
            }),
            200,
        )
    except Exception as e:
        db.session.rollback()
        return (
            jsonify({
                "status": "error",
                "message": str(e),
                "payload": None,
            }),
            500,
        )
