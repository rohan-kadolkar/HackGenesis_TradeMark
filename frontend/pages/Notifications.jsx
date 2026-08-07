import React, { useState, useEffect } from "react";
import { notificationService } from "../services/notificationService";

export const NotificationsPage = ({ user }) => {
  const [notifications, setNotifications] = useState([]);
  const [filter, setFilter] = useState("all"); // 'all' or 'unread'
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchNotifications();

    if (user) {
      const socket = notificationService.connectSocket(user, (newNotif) => {
        setNotifications((prev) => [newNotif, ...prev]);
      });
      return () => socket.disconnect();
    }
  }, [user]);

  const fetchNotifications = async () => {
    setLoading(true);
    const res = await notificationService.getNotifications(filter === "unread");
    if (res.success) {
      setNotifications(res.notifications);
    }
    setLoading(false);
  };

  const handleMarkRead = async (id) => {
    const res = await notificationService.markAsRead(id);
    if (res.success) {
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
    }
  };

  const handleMarkAllRead = async () => {
    const res = await notificationService.markAllAsRead();
    if (res.success) {
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    }
  };

  const filteredNotifications = notifications.filter((n) =>
    filter === "unread" ? !n.is_read : true
  );

  return (
    <div className="container py-4">
      <div className="d-flex justify-content-between align-items-center mb-4 pb-2 border-bottom">
        <div>
          <h3 className="fw-bold mb-0">
            <i className="fas fa-bell me-2 text-primary"></i>Notification Center
          </h3>
          <p className="text-muted small mb-0">
            Real-time alerts, verification updates, and district biosecurity notices
          </p>
        </div>
        <div>
          <button className="btn btn-outline-primary btn-sm me-2" onClick={handleMarkAllRead}>
            <i className="fas fa-check-double me-1"></i>Mark All Read
          </button>
        </div>
      </div>

      <div className="btn-group mb-4" role="group">
        <button
          className={`btn ${filter === "all" ? "btn-primary" : "btn-outline-primary"}`}
          onClick={() => setFilter("all")}
        >
          All Notifications ({notifications.length})
        </button>
        <button
          className={`btn ${filter === "unread" ? "btn-primary" : "btn-outline-primary"}`}
          onClick={() => setFilter("unread")}
        >
          Unread Only ({notifications.filter((n) => !n.is_read).length})
        </button>
      </div>

      {loading ? (
        <div className="text-center py-5">
          <div className="spinner-border text-primary" role="status"></div>
          <p className="text-muted mt-2">Loading notifications...</p>
        </div>
      ) : filteredNotifications.length === 0 ? (
        <div className="card text-center p-5 border-0 shadow-sm bg-light">
          <i className="fas fa-inbox fa-3x text-muted mb-3"></i>
          <h5>No Notifications Found</h5>
          <p className="text-muted">You are all caught up!</p>
        </div>
      ) : (
        <div className="row g-3">
          {filteredNotifications.map((n) => (
            <div className="col-12" key={n.id}>
              <div
                className={`card border-0 shadow-sm p-3 ${
                  !n.is_read ? "border-start border-primary border-4 bg-white" : "bg-light"
                }`}
              >
                <div className="d-flex justify-content-between align-items-start">
                  <div>
                    <h6 className="fw-bold mb-1">{n.title}</h6>
                    <p className="mb-2 text-dark" style={{ whiteSpace: "pre-line" }}>
                      {n.message}
                    </p>
                    <div className="d-flex align-items-center gap-3">
                      <span className="badge bg-secondary">{n.recipient_role || "general"}</span>
                      <small className="text-muted">{n.created_at}</small>
                      {n.report_id && (
                        <a href={`/incident/${n.report_id}`} className="small text-primary fw-bold">
                          View Report #{n.report_id} &rarr;
                        </a>
                      )}
                    </div>
                  </div>
                  {!n.is_read && (
                    <button
                      className="btn btn-sm btn-outline-success"
                      onClick={() => handleMarkRead(n.id)}
                    >
                      <i className="fas fa-check me-1"></i>Mark Read
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default NotificationsPage;
