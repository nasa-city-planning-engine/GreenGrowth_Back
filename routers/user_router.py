from flask import Blueprint, jsonify, request
from models import Message, User, Tag, db

user_bp = Blueprint("users", __name__, url_prefix="/users")


@user_bp.post("/register")
def register_user():
    data = request.get_json()

    if not data:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "The body of the request is empty",
                    "payload": None,
                }
            ),
            400,
        )

    try:
        if User.query.filter(
            (User.username == data["username"]) | (User.email == data["email"])
        ).first():
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Username or email already exists",
                        "payload": None,
                    }
                ),
                409,
            )

        new_user = User(
            username=data["username"], email=data["email"], password=data["password"]
        )

        db.session.add(new_user)
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"User {new_user.username} registered successfully",
                    "payload": {
                        "id": new_user.id,
                        "username": new_user.username,
                        "email": new_user.email,
                    },
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e), "payload": None}), 500


@user_bp.get("/")
def get_users():
    try:
        users = User.query.all()
        users_list = [
            {"id": user.id, "username": user.username, "email": user.email}
            for user in users
        ]

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Users retrieved successfully",
                    "payload": users_list,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "payload": None}), 500


@user_bp.delete("/<int:user_id>")
def delete_user(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return (
                jsonify(
                    {"status": "error", "message": "User not found", "payload": None}
                ),
                404,
            )

        db.session.delete(user)
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"User with id {user_id} deleted successfully",
                    "payload": None,
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e), "payload": None}), 500


@user_bp.put("/<int:user_id>")
def update_user(user_id):
    data = request.get_json()

    try:
        user = User.query.get_or_404(user_id)
        user.email = data.get("email", user.email)
        user.username = data.get("username", user.username)
        user.password = data.get("password", user.password)

        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"User with id {user_id} updated successfully",
                    "payload": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                    },
                }
            ),
            200,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e), "payload": None}), 500


@user_bp.get("/messages/<int:user_id>/")
def get_user_messages(user_id):
    try:
        user = User.query.get_or_404(user_id)
        messages = Message.query.filter_by(user_id=user.id).all()
        messages_list = [
            {
                "id": message.id,
                "content": message.content,
                "tags": [tag.name for tag in message.tags],
            }
            for message in messages
        ]

        if not messages_list:
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "No messages found for this user",
                        "payload": [],
                    }
                ),
                200,
            )
        # return messages when found
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
