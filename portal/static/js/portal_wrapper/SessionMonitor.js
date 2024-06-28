var SessionMonitorObj = function() { /* global $ */

    var LOGOUT_URL = "/logout";
    var TIMEOUT_URL = "/logout?timed_out=1";
    var LOGOUT_STORAGE_KEY = "truenthLoggedOut";
    var TIMEOUT_STORAGE_KEY="truenthTimedOut";

    this.init = function() {
        this.clearStorage();
        this.initStorageEvent();
        this.initElementEvents();
        this.initUnloadEvent();
        var expiresIn = $("#sessionMonitorProps").attr("data-expires-in"); //session expires in time period from backend
        var __CRSF_TOKEN = $("#sessionMonitorProps").attr("data-crsftoken") || "";
        var __BASE_URL = $("#sessionMonitorProps").attr("data-baseurl") || "";
        // expiresIn from backend is in seconds
        var SESSION_LIFETIME = this.calculatedLifeTime(expiresIn ? expiresIn : 1800); // default to 30 minutes
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
                    lastActivityStorageKey: "TRUENTH_SESSION_LAST_ACTIVITY",
                    ping: function() {
                        var options = {
                            type: "POST",
                            contentType: "text/plain",
                            cache: !1,
                            url: l.pingUrl,
                            crossDomain: !0
                        };
                        if ((typeof CsrfTokenChecker !== "undefined") &&
                            CsrfTokenChecker.checkTokenValidity()) {
                            //CSRF token is valid
                            options["headers"] = {
                                "X-CSRFToken": o
                            };
                        }
                        // extra check to ensure that the user's session hasn't gone staled
                        if (typeof CsrfTokenChecker !== "undefined") {
                            // extra check to ensure that the user's session hasn't gone staled
                            $.ajax(__BASE_URL+"/api/me")
                            .done(function() {
                                console.log("user authorized");
                            })
                            .fail(function(xhr) {
                                // user not authorized
                                if (parseInt(xhr.status) === 401) {
                                    window.location = l.logoutUrl;
                                }
                            });
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
                        l.removeTimeOnLoad();
                        window.location.href = l.logoutUrl;
                    },
                    initTimeOnLoad: function() {
                        window.localStorage.setItem(l.lastActivityStorageKey, Date.now());
                    },
                    //get last active time
                    getLastActiveTime: function(){
                        var storedDateTime = window.localStorage.getItem(l.lastActivityStorageKey);
                        return storedDateTime ? storedDateTime : Date.now();
                    },
                    removeTimeOnLoad: function() {
                        window.localStorage.removeItem(l.lastActivityStorageKey);
                    },
                    //determine if some given period of time has elapsed since last stored active time
                    isTimeExceeded: function() {
                        var activeDuration = (Date.now() - parseFloat(l.getLastActiveTime()));
                        if (!isNaN(activeDuration) && activeDuration >= 0) {
                            console.log("session lifetime is ", l.sessionLifetime/1000/60, " minutes");
                            console.log("time in session ", (activeDuration)/1000/60, " minutes ");
                            // compare in milliseconds
                            return activeDuration > l.sessionLifetime;
                        }
                        return false;
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
                        //check if session time is up before actually logging out user
                        if (!l.isTimeExceeded()) {
                            return;
                        }
                        if (typeof(sessionStorage) !== "undefined") {
                            sessionStorage.clear();
                        }
                        console.log("Time exceeded, logging out...");
                        l.timeout();
                    },
                    timeout: function() {
                        // this should communicate to any open browser tab 
                        l.setTimeoutStorage();
                        // remove session start timestamp from localStorage
                        l.removeTimeOnLoad();
                        window.location.href = l.timeoutUrl;
                    }
                };

                function s() {
                    $.when(l.onbeforetimeout()).always(l.ontimeout);
                }
                // this function is called each time on page load and on user activity
                function e() {
                    var lifeTime = l.sessionLifetime && l.sessionLifetime > 0 ? l.sessionLifetime : 30*60*1000; // default to 30 minutes in miliseconds;
                    var timeBeforeWarning = l.timeBeforeWarning && l.timeBeforeWarning > 0 ? l.timeBeforeWarning : 60000; // default to one minute in miliseconds
                    var n = lifeTime - timeBeforeWarning;
                    window.clearTimeout(r);
                    window.clearTimeout(u);
                    console.log("Initiating time on load...");
                    // initialize the session start timestamp here, saved in localStorage
                    l.initTimeOnLoad();
                    // set timer for showing timeout warning modal, prior to when timeout happens
                    r = window.setTimeout(l.onwarning, n);
                    // set timer for timing out session
                    u = window.setTimeout(s, lifeTime);
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
            onwarning: function() {
                // showing the session about to timeout modal
                $("#session-warning-modal").modal("show");
                if (sessMon.modalShown) {
                    console.log("session timing out, start count down...");
                }
            }
        });
        $("#session-warning-modal").modal({"backdrop": false,"keyboard": false,"show": false}).on("show.bs.modal", function () {sessMon.modalShown = true;}).on("hide.bs.modal", function () { sessMon.modalShown = false;}).on("click", "#stay-logged-in", sessMon.extendsess).on("click", "#log-out", sessMon.logout);
        var warningText = ($("#session-warning-modal").find("#remaining-time").text()).replace("{time}", (sessMon.timeBeforeWarning / 1000));
        $("#session-warning-modal").find("#remaining-time").text(warningText);
    };
    this.getUrlParameter = function(name) {
        name = name.replace(/[\[]/, "\\[").replace(/[\]]/, "\\]");
        var regex = new RegExp("[\\?&]" + name + "=([^&#]*)");
        var results = regex.exec(location.search);
        return results === null ? "" : decodeURIComponent(results[1]);
    };
    this.setLogoutSessionStorage = function() {
        sessionStorage.clear();
        sessionStorage.setItem("logout", "true"); //set session storage logout indicator
    };
    this.handleLogoutEvent = function() {
        this.setLogoutSessionStorage();
        localStorage.setItem(LOGOUT_STORAGE_KEY, true);
    },
    this.handleTimeOutEvent = function() {
        this.setLogoutSessionStorage();
        localStorage.setItem(TIMEOUT_STORAGE_KEY, true);
    };
    this.clearStorage = function() {
        localStorage.removeItem(LOGOUT_STORAGE_KEY);
        localStorage.removeItem(TIMEOUT_STORAGE_KEY);
    };
    this.initUnloadEvent = function() {
        $(window).on("beforeunload", function() {
            //taking into consideration that user may type in logout in url
            if (this.getUrlParameter("timed_out")) {
                this.handleTimeOutEvent();
            } else if (this.getUrlParameter("logout")) {
                this.handleLogoutEvent();
            }
        }.bind(this));
    },
    this.initElementEvents = function() {
        $("#tnthNavWrapper .logout").on("click", function(event) {
            event.stopImmediatePropagation();
            this.handleLogoutEvent();
        }.bind(this));
    };
    this.initStorageEvent = function() {
        //listen for timeout or logout event in other tabs
        var cleanUp = function(e) {
            if (!e) {
                return false;
            }
            var originalEvent = e.originalEvent;
            var key = e.key? e.key : (originalEvent ? originalEvent.key : null);
            var newVal = e.newVal ? e.newValue: (originalEvent ? originalEvent.newValue : null);
            if(key === TIMEOUT_STORAGE_KEY && newVal === "true") {
                window.location = TIMEOUT_URL;
            } else if(key === LOGOUT_STORAGE_KEY && newVal === "true") {
                window.location = LOGOUT_URL;
            }
        }
        $(window).on("storage", cleanUp);
    },
    //configured session lifetime from backend is in seconds
    this.calculatedLifeTime = function(configuredLifeTime) {
        var calculated = 30 * 60;
        configuredLifeTime = parseInt(configuredLifeTime);
        if (!isNaN(configuredLifeTime) && configuredLifeTime > 0) {
            calculated = configuredLifeTime;
        }
        return (calculated * 1000) - (calculated > 10 ? (10 * 1000) : 0);
    };
};
