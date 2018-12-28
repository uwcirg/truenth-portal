var UtilityObj = function() { /*global $ */
    this.requestAttempts = 0;
};
UtilityObj.prototype.init = function() {
    this.setCustomJQueryEvents(this.checkJQuery()?jQuery: null); /*global jQuery*/
    this.consolePolyFill();
};
UtilityObj.prototype.hasValue = function(val) {
    return String(val) !== "null" && String(val) !== "" && String(val) !== "undefined";
};
UtilityObj.prototype.showMain = function() {
    $("#mainHolder").css({
        "visibility": "visible",
        "-ms-filter": "progid:DXImageTransform.Microsoft.Alpha(Opacity=100)",
        "filter": "alpha(opacity=100)",
        "-moz-opacity": 1,
        "-khtml-opacity": 1,
        "opacity": 1
    });
};
UtilityObj.prototype.hideLoader = function(delay, time) {
    if (delay) {
        $("#loadingIndicator").hide();
        return;
    }
    setTimeout(function() {
        $("#loadingIndicator").fadeOut();
    }, time || 200);
};
UtilityObj.prototype.loader = function(show) {
    //landing page
    if (document.getElementById("fullSizeContainer")) {
        this.hideLoader();
        this.showMain();
        return false;
    }
    if (show) {
        $("#loadingIndicator").show();
        return;
    }
    if (!this.isDelayLoading()) {
        var self = this;
        setTimeout(function() {
            self.showMain();
        }, 100);
        this.hideLoader(true, 350);
    }
};
UtilityObj.prototype.isDelayLoading = function() { /*global DELAY_LOADING*/
    return (typeof DELAY_LOADING !== "undefined") && DELAY_LOADING;
};
UtilityObj.prototype.isTouchDevice = function() {
    return true === ("ontouchstart" in window || window.DocumentTouch && document instanceof window.DocumentTouch);
};
UtilityObj.prototype.embedPortalWrapperContent = function(data) {
    if (data && !data.error) {
        $("#mainNav").html(data);
    }
    var self = this;
    setTimeout(function() {
        self.loader();
    }, 0);
};
UtilityObj.prototype.getIEVersion = function() {
    var match = navigator.userAgent.match(/(?:MSIE |Trident\/.*; rv:)(\d+)/);
    return match ? parseInt(match[1]) : false;
};
UtilityObj.prototype.newHttpRequest = function(url, params, callBack) { /* note: this function supports older version of IE (version <= 9) - jquery ajax calls errored in older IE version*/
    this.requestAttempts++;
    var xmlhttp, self = this;
    callBack = callBack || function() {};
    if (window.XDomainRequest) {
        xmlhttp = new XDomainRequest();
        xmlhttp.onload = function() {
            callBack(xmlhttp.responseText);
        };
    } else if (window.XMLHttpRequest) {
        xmlhttp = new XMLHttpRequest();
    } else {
        xmlhttp = new ActiveXObject("Microsoft.XMLHTTP"); /*global ActiveXObject */
    }
    xmlhttp.onreadystatechange = function() {
        if (xmlhttp.readyState === 4) {
            if (xmlhttp.status === 200) {
                callBack(xmlhttp.responseText);
                self.requestAttempts = 0;
                return;
            } 
            if (self.requestAttempts < 3) {
                setTimeout(function() {
                    self.newHttpRequest(url, params, callBack);
                }, 3000);
            } else {
                callBack({error: xmlhttp.responseText});
                self.loader();
                self.requestAttempts = 0;
            }
        }
    };
    params = params || {};
    xmlhttp.open("GET", url, true);
    for (var param in params) {
        if (params.hasOwnProperty(param)) {
            xmlhttp.setRequestHeader(param, params[param]);
        }
    }
    if (!params.cache) {
        xmlhttp.setRequestHeader("cache-control", "no-cache");
        xmlhttp.setRequestHeader("expires", "-1");
        xmlhttp.setRequestHeader("pragma", "no-cache"); //legacy HTTP 1.0 servers and IE support
    }
    xmlhttp.send();
};
UtilityObj.prototype.ajaxRequest = function(url, params, callback) {
    callback = callback || function() {};
    if (!url) {
        callback({error: i18next.t("Url is required.")});
        return false;
    }
    var defaults = {
        url: url,
        type: "GET",
        contentType: "text/plain",
        timeout: 5000,
        cache: false
    };
    params = params || defaults;
    params = $.extend({}, defaults, params);
    this.requestAttempts++;
    var uself = this;
    $.ajax(params).done(function(data) {
        callback(data);
        uself.requestAttempts = 0;
    }).fail(function() {
        if (uself.requestAttempts <= 3) {
            setTimeout(function() { uself.ajaxRequest(url, params, callback);}, 3000);
        } else {
            callback({error: i18next.t("Error occurred processing request")}); /*global i18next */
            uself.requestAttempts = 0;
            uself.loader();
        }
    }).always(function() {
        uself.loader();
    });
};
UtilityObj.prototype.initWorker = function(url, params, callbackFunc) {
    var worker = new Worker("/static/js/ajaxWorker.js");
    var self = this;
    worker.postMessage({url: url, params: params});
    worker.addEventListener("message", function(e) {
        (callbackFunc).call(self, e.data);
        worker.terminate();
    }, false);
    worker.addEventListener("error", function(e) {
        console.log("Worker runtime error: Line ", e.lineno, " in ", e.filename, ": ", e.message);
        worker.terminate();
    }, false);
};
UtilityObj.prototype.workerAllowed = function() {
    return window.Worker && !this.isTouchDevice();
};
UtilityObj.prototype.getRequestMethod = function() {
    return this.getIEVersion() ? this.newHttpRequest: this.ajaxRequest; //NOTE JQuery ajax request does not work for IE <= 9
};
UtilityObj.prototype.sendRequest = function(url, params, callback) { /*generic function for sending GET ajax request, make use of worker if possible */
    params = params || {};
    if (params.useWorker && this.workerAllowed()) {
        this.initWorker(url, params, callback);
        return true;
    }
    var useFunc = this.getRequestMethod();
    (useFunc).call(this, url, params, function(data) { (callback).call(this, data);});
};
UtilityObj.prototype.LRKeyEvent = function() {
    var LR_INVOKE_KEYCODE = 187;
    if ($(".button--LR").length > 0) {
        $("html").on("keydown", function(e) {
            if (parseInt(e.keyCode) === parseInt(LR_INVOKE_KEYCODE)) {
                $(".button--LR").toggleClass("data-show");
            }
        });
    }
};
UtilityObj.prototype.appendLREditContainer = function(target, url, show) { /*global i18next */
    if (!this.hasValue(url)) { return false; }
    if (!target) { target = $(document); }
    target.append("<div>" +
        "<button class='btn btn-default button--LR'><a href='" + url + "' target='_blank'>" + i18next.t("Edit in Liferay") + "</a></button>" +
        "</div>"
    );
    if (show) { $(".button--LR").addClass("data-show");}
};
UtilityObj.prototype.getLoaderHTML = function(message) {
    return "<div class=\"loading-message-indicator\"><i class=\"fa fa-spinner fa-spin fa-2x\"></i>" + (message ? "&nbsp;" + message : "") + "</div>";
};
UtilityObj.prototype.convertToNumericField = function(field) {
    if (!field) {
        return;
    }
    if (this.isTouchDevice()) {
        field.each(function() {
            $(this).prop("type", "tel");
        });
    }
};
UtilityObj.prototype.isString = function(obj) {
    return (Object.prototype.toString.call(obj) === "[object String]");
};
UtilityObj.prototype.disableHeaderFooterLinks = function() {
    var links = $("#tnthNavWrapper a, #homeFooter a").not("a[href*='logout']").not("a.required-link").not("a.home-link");
    links.addClass("disabled");
    links.prop("onclick", null).off("click");
    links.on("click", function(e) {
        e.preventDefault();
        return false;
    });
};
UtilityObj.prototype.pad = function(n) {
    n = parseInt(n);
    return (!isNaN(n) && n < 10) ? "0" + n : n;
};
UtilityObj.prototype.escapeHtml = function(text) {
    "use strict";
    if (text === null || text !== "undefined" || String(text).length === 0) {
        return text;
    }
    return text.replace(/[\"&'\/<>]/g, function(a) {
        return {
            '"': "&quot;",
            "&": "&amp;",
            "'": "&#39;",
            "/": "&#47;",
            "<": "&lt;",
            ">": "&gt;"
        }[a];
    });
};
UtilityObj.prototype.containHtmlTags = function(text) {
    if (!text) {
        return false;
    }
    return /[<>]/.test(text);
};
UtilityObj.prototype.getExportFileName = function(prefix) {
    var d = new Date();
    return (prefix ? prefix : "ExportList_") + ("00" + d.getDate()).slice(-2) + ("00" + (d.getMonth() + 1)).slice(-2) + d.getFullYear();
};
UtilityObj.prototype.capitalize = function(str) {
    return str.replace(/\w\S*/g, function(txt) {
        return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
    });
};
UtilityObj.prototype.restoreVis = function() {
    var loadingElement = document.getElementById("loadingIndicator"), mainElement = document.getElementById("mainHolder");
    if (loadingElement) { loadingElement.setAttribute("style", "display:none; visibility:hidden;"); }
    if (mainElement) { mainElement.setAttribute("style", "visibility:visible;-ms-filter:'progid:DXImageTransform.Microsoft.Alpha(Opacity=100)';filter:alpha(opacity=100); -moz-opacity:1; -khtml-opacity:1; opacity:1"); }
};
UtilityObj.prototype.VueErrorHandling = function() {
    if (typeof Vue === "undefined") { return false; } /*global Vue */
    var self = this;
    Vue.config.errorHandler = function (err, vm, info)  {
        var handler, current = vm;
        if (vm.$options.errorHandler) {
            handler = vm.$options.errorHandler;
        } else {
            while (!handler && current.$parent) {
                current = current.$parent;
                handler = current.$options.errorHandler;
            }
        }
        self.restoreVis();
        if (handler) { 
            handler.call(current, err, vm, info);
            return;
        }
        console.log(err);
    };
};
UtilityObj.prototype.checkJQuery = function() {
    if (typeof jQuery === "undefined") {
        this.restoreVis();
        return false;
    }
    return true;
};
UtilityObj.prototype.extend = function(obj, extension) { // Extend an object with an extension
    for (var key in extension) {
        if (extension.hasOwnProperty(key)) {
            obj[key] = extension[key];
        }
    }
    return obj;
};
UtilityObj.prototype.getUrlParameter = function(name) {
    name = name.replace(/[\[]/, "\\[").replace(/[\]]/, "\\]");
    var regex = new RegExp("[\\?&]" + name + "=([^&#]*)");
    var results = regex.exec(location.search);
    return results === null ? "" : decodeURIComponent(results[1]);
};
UtilityObj.prototype.resetBrowserBackHistory = function(locationUrl, stateObject, title) {
    var historyDefined = typeof history !== "undefined" && history.pushState;
    locationUrl = locationUrl || location.href;
    if (historyDefined) {
        history.pushState(stateObject, title, locationUrl);
    }
    window.addEventListener("popstate", function() {
        if (historyDefined) {
            history.pushState(stateObject, title, locationUrl);
        } else {
            window.history.forward(1);
        }
    });
};
UtilityObj.prototype.handlePostLogout = function() {
    if (typeof sessionStorage === "undefined") {
        return false;
    }
    if (sessionStorage.getItem("logout")) {
        this.resetBrowserBackHistory(location.orgin, "logout"); /* global resetBrowserBackHistory */
        sessionStorage.removeItem("logout");
    }
};
UtilityObj.prototype.displaySystemOutageMessage = function(locale) {
    locale = locale || "en-us";
    locale = locale.replace("_", "-");
    var systemMaintenanceElId = "systemMaintenanceContainer";
    if (!document.getElementById(systemMaintenanceElId)) { //check for system outage maintenance message element
        return;
    }
    var self = this;
    this.ajaxRequest("api/settings", {contentType: "application/json; charset=utf-8"}, function(data) {
        if (!data || !(data.MAINTENANCE_MESSAGE || data.MAINTENANCE_WINDOW)) {
            return false;
        }
        var messageElement = document.querySelector(".message-container");
        if (!messageElement) {
            messageElement = document.createElement("div");
            messageElement.classList.add("message-container");
            document.getElementById(systemMaintenanceElId).appendChild(messageElement);
        }
        if (data.MAINTENANCE_MESSAGE) {
            messageElement.innerHTML = self.escapeHtml(data.MAINTENANCE_MESSAGE);
            return;
        }
        if (!data.MAINTENANCE_WINDOW || !data.MAINTENANCE_WINDOW.length) {
            return;
        }
        //use maintenance window specified in config to compose the message, assuming in following example format: ["2018-11-02T12:00:00Z", "2018-11-02T18:00:00Z"], dates in system ISO format
        var hoursDiff = function(d1, d2) {
            if (!d1 || !d2) {
                return 0;
            }
            return Math.floor(((d2.getTime() - d1.getTime())/ (1000 * 60 * 60)) % 24);
        };
        //date object automatically convert iso date/time to local date/time as it assumes a timezone of UTC if date in ISO format
        var startDate = new Date(data.MAINTENANCE_WINDOW[0]), endDate = new Date(data.MAINTENANCE_WINDOW[1]);
        var hoursTil = hoursDiff(new Date(), startDate);
        if (hoursTil < 0 || isNaN(hoursTil)) { //maintenance window has passed
            document.getElementById(systemMaintenanceElId).classList.add("tnth-hide");
            return;
        }
        /*global i18next */
        //construct message based on maintenance window
        try {
            var options = {year: "numeric", month: "long", day: "numeric", hour: "numeric", minute: "numeric", second: "numeric", hour12: true, timeZoneName: "short"};
            var displayStartDate = startDate.toLocaleString(locale,options).replace(/[,]/g, " "); //display language-sensitive representation of date/time
            var displayEndDate = endDate.toLocaleString(locale, options).replace(/[,]/g, " ");
            var message = ["<div>" + i18next.t("Hi there.") + "</div>",
                "<div>" + i18next.t("TrueNTH will be down for website maintenance starting <b>{startdate}</b>. This should last until <b>{enddate}</b>.".replace("{startdate}", displayStartDate).replace("{enddate}", displayEndDate)) + "</div>",
                "<div>" + i18next.t("Thanks for your patience while we upgrade our site.") + "</div>"].join("");
            messageElement.innerHTML = self.escapeHtml(message);
        } catch(e) {
            console.log("Error occurred converting system outage date/time ", e); /*eslint no-console:off */
            document.getElementById(systemMaintenanceElId).classList.add("tnth-hide");
        }
    });
};
UtilityObj.prototype.setCustomJQueryEvents = function($) {
    if (!$) { return false; }
    var __winHeight = $(window).height();
    $.fn.isOnScreen = function() {
        var viewport = {};
        viewport.top = $(window).scrollTop();
        viewport.bottom = viewport.top + __winHeight;
        var bounds = {};
        bounds.top = this.offset() ? this.offset().top : 0;
        bounds.bottom = bounds.top + this.outerHeight();
        return ((bounds.top <= viewport.bottom) && (bounds.bottom >= viewport.top));
    };
    $.fn.sortOptions = function() {
        var selectOptions = $(this).find("option");
        selectOptions.sort(function(a, b) {
            if (a.text > b.text) {
                return 1;
            } else if (a.text < b.text) {
                return -1;
            } else {
                return 0;
            }
        });
        return selectOptions;
    };
};
UtilityObj.prototype.consolePolyFill = function() {
    /**
     * Protect window.console method calls, e.g. console is not defined on IE
     * unless dev tools are open, and IE doesn't define console.debug
     */
    var console = (window.console = window.console || {});
    var noop = function() {};
    var log = console.log || noop;
    var start = function(name) {
        return function(param) {
            log("Start " + name + ": " + param);
        };
    };
    var end = function(name) {
        return function(param) {
            log("End " + name + ": " + param);
        };
    };

    var methods = {
        // Internet Explorer (IE 10): http://msdn.microsoft.com/en-us/library/ie/hh772169(v=vs.85).aspx#methods
        // assert(test, message, optionalParams), clear(), count(countTitle), debug(message, optionalParams), dir(value, optionalParams), dirxml(value), error(message, optionalParams), group(groupTitle), groupCollapsed(groupTitle), groupEnd([groupTitle]), info(message, optionalParams), log(message, optionalParams), msIsIndependentlyComposed(oElementNode), profile(reportName), profileEnd(), time(timerName), timeEnd(timerName), trace(), warn(message, optionalParams)
        // "assert", "clear", "count", "debug", "dir", "dirxml", "error", "group", "groupCollapsed", "groupEnd", "info", "log", "msIsIndependentlyComposed", "profile", "profileEnd", "time", "timeEnd", "trace", "warn"

        // Safari (2012. 07. 23.): https://developer.apple.com/library/safari/#documentation/AppleApplications/Conceptual/Safari_Developer_Guide/DebuggingYourWebsite/DebuggingYourWebsite.html#//apple_ref/doc/uid/TP40007874-CH8-SW20
        // assert(expression, message-object), count([title]), debug([message-object]), dir(object), dirxml(node), error(message-object), group(message-object), groupEnd(), info(message-object), log(message-object), profile([title]), profileEnd([title]), time(name), markTimeline("string"), trace(), warn(message-object)
        // "assert", "count", "debug", "dir", "dirxml", "error", "group", "groupEnd", "info", "log", "profile", "profileEnd", "time", "markTimeline", "trace", "warn"

        // Firefox (2013. 05. 20.): https://developer.mozilla.org/en-US/docs/Web/API/console
        // debug(obj1 [, obj2, ..., objN]), debug(msg [, subst1, ..., substN]), dir(object), error(obj1 [, obj2, ..., objN]), error(msg [, subst1, ..., substN]), group(), groupCollapsed(), groupEnd(), info(obj1 [, obj2, ..., objN]), info(msg [, subst1, ..., substN]), log(obj1 [, obj2, ..., objN]), log(msg [, subst1, ..., substN]), time(timerName), timeEnd(timerName), trace(), warn(obj1 [, obj2, ..., objN]), warn(msg [, subst1, ..., substN])
        // "debug", "dir", "error", "group", "groupCollapsed", "groupEnd", "info", "log", "time", "timeEnd", "trace", "warn"

        // Chrome (2013. 01. 25.): https://developers.google.com/chrome-developer-tools/docs/console-api
        // assert(expression, object), clear(), count(label), debug(object [, object, ...]), dir(object), dirxml(object), error(object [, object, ...]), group(object[, object, ...]), groupCollapsed(object[, object, ...]), groupEnd(), info(object [, object, ...]), log(object [, object, ...]), profile([label]), profileEnd(), time(label), timeEnd(label), timeStamp([label]), trace(), warn(object [, object, ...])
        // "assert", "clear", "count", "debug", "dir", "dirxml", "error", "group", "groupCollapsed", "groupEnd", "info", "log", "profile", "profileEnd", "time", "timeEnd", "timeStamp", "trace", "warn"
        // Chrome (2012. 10. 04.): https://developers.google.com/web-toolkit/speedtracer/logging-api
        // markTimeline(String)
        // "markTimeline"    
        assert: noop,
        clear: noop,
        trace: noop,
        count: noop,
        timeStamp: noop,
        msIsIndependentlyComposed: noop,
        debug: log,
        info: log,
        log: log,
        warn: log,
        error: log,
        dir: log,
        dirxml: log,
        markTimeline: log,
        group: start("group"),
        groupCollapsed: start("groupCollapsed"),
        groupEnd: end("group"),
        profile: start("profile"),
        profileEnd: end("profile"),
        time: start("time"),
        timeEnd: end("time")
    };
    for (var method in methods) {
        if (methods.hasOwnProperty(method) && !(method in console)) { // define undefined methods as best-effort methods
            console[method] = methods[method];
        }
    }
};
var Utility = Object.create(UtilityObj);


