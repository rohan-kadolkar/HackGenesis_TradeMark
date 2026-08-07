import React, { useState, useEffect } from "react";
import { notificationService } from "../services/notificationService";

export const NotificationBell = ({ user }) => {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    // 1. Initial REST API load of history
    loadNotifications();

    // 2. Real-time Socket.IO Connection
    if (user) {
      const socket = notificationService.connectSocket(user, (newNotif) => {
        setNotifications((prev) => [newNotif, ...prev]);
        setUnreadCount((prev) => prev + 1);

        // Play audio alert / Toast alert if supported
        if (typeof Notification !== "undefined" && Notification.permission === "granted") {
          new Notification(newNotif.title, { body: newNotif.message });
        }
      });

      return () => {
        socket.disconnect();
      };
    }
  }, [user]);

  const loadNotifications = async () => {
    const res = await notificationService.getNotifications();
    if (res.success) {
      setNotifications(res.notifications);
      setUnreadCount(res.unread_count);
    }
  };

  const handleMarkAsRead = async (id, e) => {
    e.stopPropagation();
    const res = await notificationService.markAsRead(id);
    if (res.success) {
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    }
  };

  const handleMarkAllRead = async () => {
    const res = await notificationService.markAllAsRead();
    if (res.success) {
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    }
  };

  return (
    <div className="notification-bell-dropdown position-relative d-inline-block">
      <button
        className="btn btn-link text-dark position-relative p-2 text-decoration-none"
        onClick={() => setIsOpen(!isOpen)}
        title="Notifications"
      >
        <i className="fas fa-bell fa-lg"></i>
        {unreadCount > 0 && (
          <span className="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          className="dropdown-menu dropdown-menu-end show shadow-lg border-0 mt-2 p-0"
          style={{ width: "350px", maxHeight: "450px", overflowY: "auto", zIndex: 1050 }}
        >
          <div className="p-3 bg-primary text-white d-flex justify-content-between align-items-center rounded-top">
            <h6 className="mb-0 fw-bold">
              <i className="fas fa-bell me-2"></i>Notifications
            </h6>
            {unreadCount > 0 && (
              <button
                className="btn btn-sm btn-outline-light py-0 px-2 small"
                onClick={handleMarkAllRead}
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="list-group list-group-flush">
            {notifications.length === 0 ? (
              <div className="p-4 text-center text-muted">
                <i className="fas fa-check-circle fa-2x text-success mb-2"></i>
                <p className="mb-0 small">No notifications found.</p>
              </div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  className={`list-group-item list-group-item-action p-3 ${
                    !n.is_read ? "bg-light border-start border-primary border-3" : ""
                  }`}
                >
                  <div className="d-flex justify-content-between align-items-start mb-1">
                    <strong className="small text-dark">{n.title}</strong>
                    {!n.is_read && (
                      <button
                        className="btn btn-sm btn-link text-muted p-0 ms-2"
                        title="Mark as read"
                        onClick={(e) => handleMarkAsRead(n.id, e)}
                      >
                        <i className="fas fa-check text-primary"></i>
                      </button>
                    )}
                  </div>
                  <p className="mb-1 small text-secondary" style={{ whiteSpace: "pre-line" }}>
                    {n.message}
                  </p>
                  <small className="text-muted" style={{ fontSize: "11px" }}>
                    {n.created_at}
                  </small>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationBell;
