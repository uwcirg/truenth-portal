var SessionMonitorObj = function(crsf_token, session_lifetime) {
  this.crsfToken = crsf_token;
  this.sessionLifetime = session_lifetime;
  this.init = function() {
    // Set default sessionLifetime from Flask config
    // Subtract 10 seconds to ensure the backend doesn't expire the session first
    var CONFIG_SESSION_LIFETIME = this.sessionLifetime, DEFAULT_SESSION_LIFETIME;
    var cookieTimeout = this.readCookie("SS_TIMEOUT");
    cookieTimeout = cookieTimeout ? parseInt(cookieTimeout) : null;
    var __CRSF_TOKEN = this.crsfToken;

    if (cookieTimeout && cookieTimeout > 0) {
      DEFAULT_SESSION_LIFETIME = (cookieTimeout * 1000) - (cookieTimeout > 10 ? (10 * 1000) : 0);
    } else {
        try {
          if (!CONFIG_SESSION_LIFETIME || CONFIG_SESSION_LIFETIME === "") {
            CONFIG_SESSION_LIFETIME = 15 * 60;
          }
          DEFAULT_SESSION_LIFETIME = (CONFIG_SESSION_LIFETIME * 1000) - (CONFIG_SESSION_LIFETIME > 10 ? (10 * 1000) : 0);
        } catch(e) {
          DEFAULT_SESSION_LIFETIME = (15 * 60 * 1000) - (10 * 1000);
        }
    }

    var sessMon = (function(__CRSF_TOKEN) {
                      return function(a){"use strict";function b(a){a&&a.stopPropagation();var b=new Date,c=b-j;a&&a.target&&"stay-logged-in"==a.target.id?(j=b,d(),a=null,i.ping()):c>i.minPingInterval&&(j=b,d(),i.ping())}function c(){d(),i.ping()}function d(){var a=i.sessionLifetime-i.timeBeforeWarning;window.clearTimeout(f),window.clearTimeout(g),f=window.setTimeout(i.onwarning,a),g=window.setTimeout(e,i.sessionLifetime)}function e(){$.when(i.onbeforetimeout()).always(i.ontimeout)}var f,g,h={sessionLifetime:36e5,timeBeforeWarning:6e5,minPingInterval:6e4,activityEvents:"mouseup",pingUrl:window.location.protocol+"//"+window.location.host+"/api/ping",logoutUrl:"/logout",timeoutUrl:"/logout?timeout=1",ping:function(){$.ajax({type:"POST",contentType:"text/plain",headers: {"X-CSRFToken": __CRSF_TOKEN}, cache:false,url:i.pingUrl,crossDomain:!0})},logout:function(){window.location.href=i.logoutUrl},onwarning:function(){var a=Math.round(i.timeBeforeWarning/60/1e3),b=$('<div id="jqsm-warning">Your session will expire in '+a+' minutes. <button id="jqsm-stay-logged-in">Stay Logged In</button><button id="jqsm-log-out">Log Out</button></div>');$("body").children("div#jqsm-warning").length||$("body").prepend(b),$("div#jqsm-warning").show(),$("button#stay-logged-in").on("click",function(a){a&&a.stopPropagation(),i.extendsess(a)}).on("click",function(){b.hide()}),$("button#jqsm-log-out").on("click",i.logout)},onbeforetimeout:function(){},ontimeout:function(){window.location.href=i.timeoutUrl}},i={},j=new Date;return $.extend(i,h,a,{extendsess:b}),$(document).on(i.activityEvents,b),c(),i};
                    })(__CRSF_TOKEN)({
                      sessionLifetime: DEFAULT_SESSION_LIFETIME,
                      timeBeforeWarning: 1 * 60 * 1000,
                      minPingInterval: 1 * 60 * 1000,  // 1 minute
                      activityEvents: "mouseup",
                      pingUrl: "/api/ping",
                      logoutUrl: "/logout",
                      timeoutUrl: "/logout?timed_out=1",
                      modalShown: false,
                      intervalMonitor: false,
                      onwarning: function() {$("#session-warning-modal").modal("show"); if (sessMon.modalShown) sessMon.intervalMonitor = setInterval(function(){ sessMon.ontimeout() }, 2 * 60 * 1000);}
                    });
    window.sessMon = sessMon;
    var warningText = (i18next.t("Your session will expire in approximately {time} seconds due to inactivity.")).replace("{time}",(sessMon.timeBeforeWarning / 1000));
    $("#session-warning-modal").modal({"backdrop": false,"keyboard": false,"show": false})
            .on("show.bs.modal", function() { sessMon.modalShown = true})
            .on("hide.bs.modal", function() { sessMon.modalShown = false; if (sessMon.intervalMonitor) clearInterval(sessMon.intervalMonitor); })
            .on("click", "#stay-logged-in", sessMon.extendsess)
            .on("click", "#log-out", sessMon.logout)
            .find("#remaining-time").text(warningText);
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