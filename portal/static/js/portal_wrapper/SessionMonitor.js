var SessionMonitorObj = function() { /* global $ */
    var LOGOUT_URL = "/logout";
    var TIMEOUT_URL = "/logout?timeout=1";
    var LOGOUT_STORAGE_KEY = "truenthLoggedOut";
    var TIMEOUT_STORAGE_KEY="truenthTimedOut";
    this.init = function() {
        this.clearLogoutStorage();
        this.initStorageEvent();
        var expiresIn = $("#sessionMonitorProps").attr("data-expires-in"); //session expires in time period from backend
        var __CRSF_TOKEN = $("#sessionMonitorProps").attr("data-crsftoken") || "";
        var __BASE_URL = $("#sessionMonitorProps").attr("data-baseurl") || "";
        var SESSION_LIFETIME = this.calculatedLifeTime(expiresIn);
        var sessMon = (function(n, o) {
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
                    logoutUrl: n + LOGOUT_URL,
                    timeoutUrl: n + TIMEOUT_URL,
                    ping: function() {
                        console.log("wtf ? ", CsrfTokenChecker);
                        var options = {
                            type: "POST",
                            contentType: "text/plain",
                            headers: {
                                "X-CSRFToken": o
                            },
                            cache: !1,
                            url: l.pingUrl,
                            crossDomain: !0
                        };
                        if ((typeof CsrfTokenChecker !== "undefined") &&
                            CsrfTokenChecker.checkTokenValidity()) {
                            //CSRF token is valid
                            console.log("CSRF token valid");
                            options["headers"] = {
                                "X-CSRFToken": o
                            };
                        }
                        $.ajax(options);
                    },
                    setLogoutStorage: function() {
                        if (typeof localStorage !== "undefined") {
                            window.localStorage.setItem(LOGOUT_STORAGE_KEY, true);
                        }
                    },
                    setTimeoutStorage: function() {
                        if (typeof localStorage !== "undefined") {
                            window.localStorage.setItem(TIMEOUT_STORAGE_KEY, true);
                        }
                    },
                    logout: function() {
                        if (typeof(sessionStorage) !== "undefined") {
                            sessionStorage.clear();
                        }
                        l.setLogoutStorage();
                        window.location.href = l.logoutUrl;
                    },
                    onwarning: function() {
                        var n = Math.round(l.timeBeforeWarning / 60 / 1e3),
                            o = $("#jqsm-warning"); //default place holder element, content of which should be provided by consumer
                        $("div#jqsm-warning").show();
                        $("button#stay-logged-in").on("click", function(n) {
                            if (n) {
                                n.stopPropagation();
                            }
                            l.extendsess(n);
                        }).on("click", function() {
                            o.hide();
                        });
                        $("button#jqsm-log-out").on("click", l.logout);
                    },
                    onbeforetimeout: function() {},
                    ontimeout: function() {
                        if (typeof(sessionStorage) !== "undefined") {
                            sessionStorage.clear();
                        }
                        l.setTimeoutStorage();
                        window.location.href = l.timeoutUrl;
                    }
                };

                function s() {
                    $.when(l.onbeforetimeout()).always(l.ontimeout);
                }

                function e() {
                    var n = l.sessionLifetime - l.timeBeforeWarning;
                    window.clearTimeout(r);
                    window.clearTimeout(u);
                    r = window.setTimeout(l.onwarning, n);
                    u = window.setTimeout(s, l.sessionLifetime);
                }

                function i(n) {
                    if (n) {
                        n.stopPropagation();
                    }
                    var o = new Date,
                        t = o - g;
                    if (n && n.target && "stay-logged-in" === String(n.target.id)) {
                        g = o;
                        e();
                        n = null;
                        l.ping();
                        return;
                    }
                    if (t > l.minPingInterval) {
                        g = o;
                        e();
                        l.ping();
                    }
                }
                return $.extend(l, a, t, {
                    extendsess: i
                }), $(document).on(l.activityEvents, i), e(), l.ping(), l;
            };
        })(__BASE_URL, __CRSF_TOKEN)({
            sessionLifetime: SESSION_LIFETIME,
            timeBeforeWarning: 6e4,
            minPingInterval: 6e4,
            activityEvents: "mouseup",
            pingUrl: __BASE_URL + "/api/ping",
            logoutUrl: __BASE_URL + LOGOUT_URL,
            timeoutUrl: __BASE_URL + TIMEOUT_URL,
            modalShown: !1,
            intervalMonitor: !1,
            onwarning: function() {
                $("#session-warning-modal").modal("show");
                if (sessMon.modalShown) {
                    sessMon.intervalMonitor = setInterval(function() {
                        sessMon.ontimeout();
                    }, 12e4);
                }
            }
        });
        $("#session-warning-modal").modal({"backdrop": false,"keyboard": false,"show": false}).on("show.bs.modal", function () {sessMon.modalShown = true;}).on("hide.bs.modal", function () { sessMon.modalShown = false; if (sessMon.intervalMonitor) { clearInterval(sessMon.intervalMonitor); }}).on("click", "#stay-logged-in", sessMon.extendsess).on("click", "#log-out", sessMon.logout);
        var warningText = ($("#session-warning-modal").find("#remaining-time").text()).replace("{time}", (sessMon.timeBeforeWarning / 1000));
        $("#session-warning-modal").find("#remaining-time").text(warningText);
    };
    this.clearLogoutStorage = function() {
        window.localStorage.removeItem(LOGOUT_STORAGE_KEY);
        window.localStorage.removeItem(TIMEOUT_STORAGE_KEY);
    };
    this.initStorageEvent = function() {
        //listen for timeout or logout event in other tabs
        var cleanUp = function(e) {
            var key = e.key? e.key : e.originalEvent.key;
            var newVal = e.newVal ? e.newValue: e.originalEvent.newValue;
            console.log("SESSION MONITOR GET HERE? key ",key, " val ", newVal)
            if(key === LOGOUT_STORAGE_KEY && newVal === "true") {
                window.location = LOGOUT_URL;
            }
            if(key === TIMEOUT_STORAGE_KEY && newVal === "true") {
                window.location = TIMEOUT_URL;
            }
        }
        $(window).on("storage", cleanUp);
    },
    this.calculatedLifeTime = function(configuredLifeTime) {
        var calculated = 15 * 60;
        configuredLifeTime = parseInt(configuredLifeTime);
        if (!isNaN(configuredLifeTime) && configuredLifeTime > 0) {
            calculated = configuredLifeTime;
        }
        return (calculated * 1000) - (calculated > 10 ? (10 * 1000) : 0);
    };
};
// setTimeout(function() {
//     $(window).on("load", function() {
//         SessionMonitorObj.clearLogoutStorage();
//         SessionMonitorObj.initStorageEvent();
//     });
// }, 300);
