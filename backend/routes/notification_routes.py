from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from backend.services.notification_service import NotificationService

notification_bp = Blueprint('notification_bp', __name__)

@notification_bp.route('/notifications', methods=['GET'])
@notification_bp.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    """
    GET /notifications or GET /api/notifications
    Returns notification history and unread count for logged in user.
    """
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    notifications = NotificationService.get_notifications(
        user_id=current_user.id,
        user_role=current_user.role,
        unread_only=unread_only
    )
    unread_count = sum(1 for n in notifications if not n.is_read)

    return jsonify({
        'success': True,
        'notifications': [n.to_dict() for n in notifications],
        'unread_count': unread_count
    })

@notification_bp.route('/notifications/<int:notification_id>/read', methods=['PATCH'])
@notification_bp.route('/api/notifications/<int:notification_id>/read', methods=['PATCH'])
@login_required
def mark_notification_read(notification_id):
    """
    PATCH /notifications/<id>/read or PATCH /api/notifications/<id>/read
    Marks specific notification as read.
    """
    notif = NotificationService.mark_read(notification_id, user_id=current_user.id)
    if not notif:
        return jsonify({'success': False, 'error': 'Notification not found'}), 404

    return jsonify({
        'success': True,
        'message': f'Notification #{notification_id} marked as read',
        'notification': notif.to_dict()
    })

@notification_bp.route('/notifications/read-all', methods=['PATCH'])
@notification_bp.route('/api/notifications/read-all', methods=['PATCH'])
@login_required
def mark_all_notifications_read():
    """
    PATCH /notifications/read-all or PATCH /api/notifications/read-all
    Marks all notifications for current user as read.
    """
    count = NotificationService.mark_all_read(user_id=current_user.id, user_role=current_user.role)
    return jsonify({
        'success': True,
        'message': f'Marked {count} notifications as read',
        'count': count
    })
