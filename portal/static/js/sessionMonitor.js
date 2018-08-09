var SessionMonitorObj = function() {
  //this.crsfToken = crsf_token;
  //this.baseUrl = base_url;
  //this.sessionLifetime = session_lifetime;
  this.init = function() {
    // Set default sessionLifetime from Flask config
    // Subtract 10 seconds to ensure the backend doesn't expire the session first
    var DEFAULT_SESSION_LIFETIME;
    var cookieTimeout = this.readCookie("SS_INACTIVITY_TIMEOUT") || $("#sessionMonitorProps").attr("data-cookie-timeout"); //for debugging and also a workaround when cookie is not accessible via call to document.cookie
    cookieTimeout = cookieTimeout ? parseInt(cookieTimeout) : null;
    var __CRSF_TOKEN = $("#sessionMonitorProps").attr("data-crsftoken") || "";
    var __BASE_URL = $("#sessionMonitorProps").attr("data-baseurl") || "";
    var CONFIG_SESSION_LIFETIME = $("#sessionMonitorProps").attr("data-sessionlifetime") || 15 * 60;

    if (cookieTimeout && !isNaN(cookieTimeout) && cookieTimeout > 0) {
      DEFAULT_SESSION_LIFETIME = (cookieTimeout * 1000) - (cookieTimeout > 10 ? (10 * 1000) : 0);
    } else {
        try {
          DEFAULT_SESSION_LIFETIME = (CONFIG_SESSION_LIFETIME * 1000) - (CONFIG_SESSION_LIFETIME > 10 ? (10 * 1000) : 0);
        } catch(e) {
          DEFAULT_SESSION_LIFETIME = (15 * 60 * 1000) - (10 * 1000);
        }
    }
    var sessMon=(function(n, o) {
      return function(t) {
          "use strict";
          var l = {};
          var g = new Date;
          var r;
          var u;
          var a = {
                    sessionLifetime: 36e5,
                    timeBeforeWarning: 6e5,
                    minPingInterval: 6e4,
                    activityEvents: "mouseup",
                    pingUrl: n + "/api/ping",
                    logoutUrl: n + "/logout",
                    timeoutUrl: n + "/logout?timeout=1",
                    ping: function() {
                      $.ajax({
                          type: "POST",
                          contentType: "text/plain",
                          headers: {
                              "X-CSRFToken": o
                          },
                          cache: !1,
                          url: l.pingUrl,
                          crossDomain: !0
                      });
                    },
                    logout: function() {
                      if (typeof(sessionStorage) !== "undefined") {
                        sessionStorage.clear();
                      }
                      window.location.href = l.logoutUrl;
                    },
                    onwarning: function() {
                      var n = Math.round(l.timeBeforeWarning / 60 / 1e3),
                          o = $('<div id="jqsm-warning">Your session will expire in ' + n + ' minutes. <button id="jqsm-stay-logged-in">Stay Logged In</button><button id="jqsm-log-out">Log Out</button></div>');
                      $("body").children("div#jqsm-warning").length || $("body").prepend(o), $("div#jqsm-warning").show(), $("button#stay-logged-in").on("click", function(n) {
                          n && n.stopPropagation(), l.extendsess(n);
                      }).on("click", function() {
                          o.hide();
                      }), $("button#jqsm-log-out").on("click", l.logout);
                    },
                    onbeforetimeout: function() {},
                    ontimeout: function() {
                      window.location.href = l.timeoutUrl;
                      if (typeof(sessionStorage) !== "undefined") {
                        sessionStorage.clear();
                      }
                    }
                  };

          function i(n) {
              n && n.stopPropagation();
              var o = new Date,
                  t = o - g;
              n && n.target && "stay-logged-in" === String(n.target.id) ? (g = o, e(), n = null, l.ping()) : t > l.minPingInterval && (g = o, e(), l.ping());
          }

          function e() {
              var n = l.sessionLifetime - l.timeBeforeWarning;
              window.clearTimeout(r), window.clearTimeout(u), r = window.setTimeout(l.onwarning, n), u = window.setTimeout(s, l.sessionLifetime);
          }

          function s() {
              $.when(l.onbeforetimeout()).always(l.ontimeout);
          }
          return $.extend(l, a, t, {
              extendsess: i
          }), $(document).on(l.activityEvents, i), e(), l.ping(), l;
      };
  })(__BASE_URL, __CRSF_TOKEN)({
      sessionLifetime: DEFAULT_SESSION_LIFETIME,
      timeBeforeWarning: 6e4,
      minPingInterval: 6e4,
      activityEvents: "mouseup",
      pingUrl: __BASE_URL + "/api/ping",
      logoutUrl: __BASE_URL + "/logout",
      timeoutUrl: __BASE_URL + "/logout?timed_out=1",
      modalShown: !1,
      intervalMonitor: !1,
      onwarning: function() {
          $("#session-warning-modal").modal("show"), sessMon.modalShown && (sessMon.intervalMonitor = setInterval(function() {
              sessMon.ontimeout();
          }, 12e4));
      }
  });
  $("#session-warning-modal").modal({
          "backdrop": false,
          "keyboard": false,
          "show": false
      })
      .on("show.bs.modal", function() {
          sessMon.modalShown = true;
      })
      .on("hide.bs.modal", function() {
          sessMon.modalShown = false;
          if (sessMon.intervalMonitor) {
              clearInterval(sessMon.intervalMonitor);
          }
      })
      .on("click", "#stay-logged-in", sessMon.extendsess)
      .on("click", "#log-out", sessMon.logout);
      var warningText = ($("#session-warning-modal").find("#remaining-time").text()).replace("{time}",(sessMon.timeBeforeWarning / 1000));
      $("#session-warning-modal").find("#remaining-time").text(warningText);
    };
    this.readCookie = function(name) {
      var nameEQ = name + "=";
      var ca = document.cookie.split(";");
      for (var i = 0; i < ca.length; i++) {
          var c = ca[i];
          while (c.charAt(0) === " ") {
            c = c.substring(1, c.length);
          }
          if (c.indexOf(nameEQ) === 0) {
            return c.substring(nameEQ.length, c.length);
          }
      }
      return null;
    };
  };
