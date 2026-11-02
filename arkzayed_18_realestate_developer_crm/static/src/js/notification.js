 /** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";
import { session } from "@web/session";

publicWidget.registry.Notification = publicWidget.Widget.extend({
        selector: "#o_main_nav > ul:nth-child(3)",

        start: async function () {
            var def = this._super.apply(this, arguments);
            await this._getUserMessages()
            return def;
        },

        _getNotificationLength: function(result) {
            var unreadNotifications = result.filter(function(notification) {
                return !notification.read_flag;
            });
            return unreadNotifications.length;
        },

        _getUserMessages: async function () {
            var self = this;
            // Public/unauthenticated visitors cannot call backend methods. Letting
            // the rejected RPC (403 Forbidden) bubble up to the global error handler
            // triggers Odoo's session-expired notification, which itself crashes with
            // an OwlError on its legacy button shape. Catch it and fail silently.
            var result;
            try {
                result = await rpc('/web/dataset/call_kw/user.notification/get_user_messages', {
                    model: 'user.notification',
                    method: 'get_user_messages',
                    args: [[]],
                    kwargs: {},
                })
            } catch (error) {
                // Fail silently instead of cascading into the global error handler.
                return;
            }
            var notificationList = document.getElementById("notification_list");
            var notificationDiv = document.getElementById("notification_div");
            if (!result || !notificationList || !notificationDiv) {
                return;
            }
            // Handle the result of method call
            result.forEach(function (notification) {
                var id = notification.id;
                var title = notification.title;
                var lead_id = notification.res_id;
                var read_flag = notification.read_flag;
                var aTag = document.createElement("a");
                aTag.href = `/my/lead/${lead_id}`;
                aTag.name = 'lead_link';
                aTag.id = id;
                if (read_flag) {
                    aTag.className = "lead_link visited";
                    aTag.style.color = "#35979c";
                } else {
                    aTag.className = "lead_link active";
                    aTag.style.color = "#1a75ff";
                }
                aTag.innerHTML = `${title}`;
                // Add click event to the dynamically created <a> tag
                aTag.addEventListener("click", function(event) {
                    event.preventDefault();
                    self._set_flag(event);
                });

                // Append the dynamically created <a> tag to the 'notification_list' element
                notificationList.appendChild(aTag);

                // Add a separator
                var separator = document.createElement("div");
                separator.className = "o_NotificationList_separator flex-shrink-0 w-100 border-bottom";
                notificationList.appendChild(separator);
            });

            var spanTag = document.createElement("span");
            spanTag.className = "badge";
            spanTag.style.color = "#1a75ff";
            spanTag.textContent = self._getNotificationLength(result);
            notificationDiv.appendChild(spanTag);
        },

        _set_flag: async function (event) {
            var notificationId = event.target.id;
            await rpc('/web/dataset/call_kw/user.notification/set_read_flag', {
                model: 'user.notification',
                method: 'set_read_flag',
                args: [[]],
                kwargs: {notification_id: notificationId},
            });
            window.location.href = event.target.href;
        },
});
