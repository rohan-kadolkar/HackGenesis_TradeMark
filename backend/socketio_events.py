from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import request

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")

def init_socketio(app):
    socketio.init_app(app)
    return socketio

@socketio.on('connect')
def handle_connect():
    print(f"[SocketIO] Client connected: {request.sid}")
    emit('connected', {'status': 'connected', 'sid': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"[SocketIO] Client disconnected: {request.sid}")

@socketio.on('join_user')
def handle_join_user(data):
    user_id = data.get('user_id')
    if user_id:
        room_name = f"user_{user_id}"
        join_room(room_name)
        print(f"[SocketIO] Client {request.sid} joined room: {room_name}")
        emit('joined_room', {'room': room_name})

@socketio.on('join_role')
def handle_join_role(data):
    role = data.get('role')
    if role:
        room_name = f"role_{role}"
        join_room(room_name)
        print(f"[SocketIO] Client {request.sid} joined room: {room_name}")
        emit('joined_room', {'room': room_name})

@socketio.on('join_district')
def handle_join_district(data):
    district_id = data.get('district_id')
    if district_id:
        room_name = f"district_{district_id}"
        join_room(room_name)
        print(f"[SocketIO] Client {request.sid} joined room: {room_name}")
        emit('joined_room', {'room': room_name})
