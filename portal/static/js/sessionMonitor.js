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

    var sessMon=function(n){return function(o){"use strict";function t(n){n&&n.stopPropagation();var o=new Date,t=o-l;n&&n.target&&"stay-logged-in"==n.target.id?(l=o,i(),n=null,a.ping()):t>a.minPingInterval&&(l=o,i(),a.ping())}function i(){var n=a.sessionLifetime-a.timeBeforeWarning;window.clearTimeout(s),window.clearTimeout(r),s=window.setTimeout(a.onwarning,n),r=window.setTimeout(e,a.sessionLifetime)}function e(){$.when(a.onbeforetimeout()).always(a.ontimeout)}var s,r,u={sessionLifetime:36e5,timeBeforeWarning:6e5,minPingInterval:6e4,activityEvents:"mouseup",pingUrl:window.location.protocol+"//"+window.location.host+"/api/ping",logoutUrl:"/logout",timeoutUrl:"/logout?timeout=1",ping:function(){$.ajax({type:"POST",contentType:"text/plain",headers:{"X-CSRFToken":n},cache:!1,url:a.pingUrl,crossDomain:!0})},logout:function(){window.location.href=a.logoutUrl},onwarning:function(){var n=Math.round(a.timeBeforeWarning/60/1e3),o=$('<div id="jqsm-warning">Your session will expire in '+n+' minutes. <button id="jqsm-stay-logged-in">Stay Logged In</button><button id="jqsm-log-out">Log Out</button></div>');$("body").children("div#jqsm-warning").length||$("body").prepend(o),$("div#jqsm-warning").show(),$("button#stay-logged-in").on("click",function(n){n&&n.stopPropagation(),a.extendsess(n)}).on("click",function(){o.hide()}),$("button#jqsm-log-out").on("click",a.logout)},onbeforetimeout:function(){},ontimeout:function(){window.location.href=a.timeoutUrl}},a={},l=new Date;return $.extend(a,u,o,{extendsess:t}),$(document).on(a.activityEvents,t),i(),a.ping(),a}}(__CRSF_TOKEN)({sessionLifetime:DEFAULT_SESSION_LIFETIME,timeBeforeWarning:6e4,minPingInterval:6e4,activityEvents:"mouseup",pingUrl:"/api/ping",logoutUrl:"/logout",timeoutUrl:"/logout?timed_out=1",modalShown:!1,intervalMonitor:!1,onwarning:function(){$("#session-warning-modal").modal("show"),sessMon.modalShown&&(sessMon.intervalMonitor=setInterval(function(){sessMon.ontimeout()},12e4))}});
    
    window.sessMon = sessMon;
    var warningText = (i18next.t("Your session will expire in approximately {time} seconds due to inactivity.")).replace("{time}",(sessMon.timeBeforeWarning / 1000));
    $("#session-warning-modal").modal({"backdrop": false,"keyboard": false,"show": false})
            .on("show.bs.modal", function() { sessMon.modalShown = true; })
            .on("hide.bs.modal", function() { sessMon.modalShown = false; if (sessMon.intervalMonitor)  { clearInterval(sessMon.intervalMonitor); } })
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
