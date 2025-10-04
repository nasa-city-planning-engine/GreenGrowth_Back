from flask import request, Blueprint, jsonify, flash
from models.UserModel import User
from models import db

user_bp = Blueprint("user_bp", __name__)

# User Registration Route
@user_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    
    try:
        if not username or not email or not password:
            return jsonify({"error": "Missing required fields"}), 400

        new_user = User.user_register(username, email, password)

        if new_user is None:
            return jsonify({"error": "Username or email already exists"}), 409

        return jsonify({"message": "User registered successfully", "user": {"id": new_user.id, "username": new_user.username, "email": new_user.email}}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"status":"error",
                        "message": str(e),
                        "payload":None}), 500
    
# User Sign-In Route
@user_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    
    try:
        if not username or not password:
            return jsonify({"error": "Missing required fields"}), 400

        user = User.sign_in(username, password)

        if user is None:
            return jsonify({"error": "Invalid username or password"}), 401

        return jsonify({"message": "Login successful", "user": {"id": user.id, "username": user.username, "email": user.email}}), 200

    except Exception as e:
        return jsonify({"status":"error",
                        "message": str(e),
                        "payload":None}), 500
    
# User Update Route
@user_bp.route("/update/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    data = request.get_json()
    new_username = data.get("username")
    new_email = data.get("email")
    
    try:
        user = User.query.get(user_id)
        if user is None:
            return jsonify({"error": "User not found"}), 404

        user.user_update(new_username=new_username, new_email=new_email)
        
        return jsonify({"message": "User updated successfully", "user": {"id": user.id, "username": user.username, "email": user.email}}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status":"error",
                        "message": str(e),
                        "payload":None}), 500
    

# User Deletion Route
@user_bp.route("/delete/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    try:
        user = User.query.get(user_id)
        if user is None:
            return jsonify({"error": "User not found"}), 404

        user.user_delete()
        return jsonify({"message": "User deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status":"error",
                        "message": str(e),
                        "payload":None}), 500




