import { io } from "socket.io-client";

const API_BASE_URL = window.location.origin;

export const notificationService = {
  // Fetch notification history
  async getNotifications(unreadOnly = false) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/notifications?unread_only=${unreadOnly}`, {
        headers: { "Content-Type": "application/json" }
      });
      return await response.json();
    } catch (error) {
      console.error("Error fetching notifications:", error);
      return { success: false, notifications: [], unread_count: 0 };
    }
  },

  // Mark single notification as read
  async markAsRead(id) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/notifications/${id}/read`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" }
      });
      return await response.json();
    } catch (error) {
      console.error(`Error marking notification #${id} as read:`, error);
      return { success: false };
    }
  },

  // Mark all notifications as read
  async markAllAsRead() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/notifications/read-all`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" }
      });
      return await response.json();
    } catch (error) {
      console.error("Error marking all notifications as read:", error);
      return { success: false };
    }
  },

  // Connect Socket.IO client and join user & role rooms
  connectSocket(user, onNotificationReceived) {
    const socket = io(API_BASE_URL, {
      transports: ["websocket", "polling"],
      autoConnect: true
    });

    socket.on("connect", () => {
      console.log("[Socket.IO] Connected to Flask notification server:", socket.id);
      if (user) {
        if (user.id) {
          socket.emit("join_user", { user_id: user.id });
        }
        if (user.role) {
          socket.emit("join_role", { role: user.role });
        }
        if (user.district_id) {
          socket.emit("join_district", { district_id: user.district_id });
        }
      }
    });

    socket.on("notification", (data) => {
      console.log("[Socket.IO] Real-time notification received:", data);
      if (onNotificationReceived) {
        onNotificationReceived(data);
      }
    });

    socket.on("disconnect", () => {
      console.log("[Socket.IO] Disconnected from server");
    });

    return socket;
  }
};
