function hasValue(val) {
    return val != null && val != "" && val != "undefined";
}
function equalHeightBoxes(passClass) { /*global $ */
    var windowsize = $(window).width();
    // Switch back to auto for small screen or to recalculate on larger
    $("." + passClass).css("height", "auto");
    if (windowsize > 768 && $("." + passClass).length > 1) {
        var elementHeights = $("." + passClass).map(function() {
            return $(this).height();
        }).get();
        // Math.max takes a variable number of arguments
        // `apply` is equivalent to passing each height as an argument
        var maxHeight = Math.max.apply(null, elementHeights);
        // Set each height to the max height
        $("." + passClass).height(maxHeight);
    }
}
// Return an XHR without XHR header so  it doesn't need to be explicitly allowed with CORS
function xhr_function() {
    // Get new xhr object using default factory
    var xhr = jQuery.ajaxSettings.xhr(); /*global jQuery */
    // Copy the browser's native setRequestHeader method
    var setRequestHeader = xhr.setRequestHeader;
    // Replace with a wrapper
    xhr.setRequestHeader = function(name, value) {
        // Ignore the X-Requested-With header
        if (String(name) === "X-Requested-With") {
            return;
        }
        // Otherwise call the native setRequestHeader method
        // Note: setRequestHeader requires its 'this' to be the xhr object,
        // which is what 'this' is here when executed.
        setRequestHeader.call(this, name, value);
    };
    // pass it on to jQuery
    return xhr;
}
function showMain() {
    $("#mainHolder").css({
        "visibility": "visible",
        "-ms-filter": "progid:DXImageTransform.Microsoft.Alpha(Opacity=100)",
        "filter": "alpha(opacity=100)",
        "-moz-opacity": 1,
        "-khtml-opacity": 1,
        "opacity": 1
    });
}
function hideLoader(delay, time) {
    if (delay) {
        $("#loadingIndicator").hide();
    } else {
        setTimeout(function() {
            $("#loadingIndicator").fadeOut();
        }, time || 200);
    }
}
// Loading indicator that appears in UI on page loads and when saving
function loader(show) {
    //landing page
    if ($("#fullSizeContainer").length > 0) {
        hideLoader();
        showMain();
        return false;
    }
    if (show) {
        $("#loadingIndicator").show();
    } else {
        if ((typeof DELAY_LOADING !== "undefined") && !DELAY_LOADING) { /*global DELAY_LOADING*/
            setTimeout(function() {
                showMain();
            }, 100);
            hideLoader(true, 350);
        }
    }
}
function _isTouchDevice() {
    return true === ("ontouchstart" in window || window.DocumentTouch && document instanceof window.DocumentTouch);
}
// populate portal banner content
function embed_page(data) {
    if (data && !data.error) {
        $("#mainNav").html(data);
    }
    setTimeout(function() {
        loader();
    }, 0);
}
function getIEVersion() {
    var match = navigator.userAgent.match(/(?:MSIE |Trident\/.*; rv:)(\d+)/);
    return match ? parseInt(match[1]) : false;
}
var request_attempts = 0;
/*
 * note: this function supports older version of IE (version <= 9)
 * jquery ajax calls errored in older IE version
 */
function newHttpRequest(url, params, callBack) {
    request_attempts++;
    var xmlhttp;
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
            } else {
                if (request_attempts < 3) {
                    setTimeout(function() {
                        newHttpRequest(url, params, callBack);
                    }, 3000);
                } else {
                    callBack({error: xmlhttp.responseText});
                    loader();
                }
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
}
function ajaxRequest(url, params, callback) {
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
    request_attempts++;
    $.ajax(params).done(function(data) {
        callback(data);
        request_attempts = 0;
    }).fail(function(jqXHR, textStatus) {
        if (request_attempts <= 3) {
            setTimeout(function() { ajaxRequest(url, params, callback);}, 3000);
        } else {
            callback({error: i18next.t("Error occurred processing request")}); /*global i18next */
            request_attempts = 0;
            loader();
        }
    }).always(function() {
        loader();
    });
}
function initWorker(url, params, callbackFunc) {
    var worker = new Worker('/static/js/ajaxWorker.js');
    worker.postMessage({url: url, params: params});
    worker.addEventListener("message", function(e) {
        callbackFunc(e.data);
        worker.terminate();
    }, false);
    worker.addEventListener("error", function(e) {
        console.log("Worker runtime error: Line ", e.lineno, " in ", e.filename, ": ", e.message);
        worker.terminate();
    }, false);
}
function sendRequest(url, params, callback) { /*generic function for sending GET ajax request, make use of worker if possible */
    params = params || {};
    if (params.useWorker && window.Worker && !_isTouchDevice()) {
       initWorker(url, params, callback);
       return true;
    }
    var useFunc = getIEVersion() ? newHttpRequest: ajaxRequest; //NOTE JQuery ajax request does not work for IE <= 9
    useFunc(url, params, function(data) { callback(data);});
}
function LRKeyEvent() {
    var LR_INVOKE_KEYCODE = 187;
    if ($(".button--LR").length > 0) {
        $("html").on("keydown", function(e) {
            if (parseInt(e.keyCode) === parseInt(LR_INVOKE_KEYCODE)) {
                $(".button--LR").toggleClass("data-show");
            }
        });
    }
}
function appendLREditContainer(target, url, show) { /*global i18next */
    if (!hasValue(url)) { return false; }
    if (!target) { target = $(document); }
    target.append("<div>" +
        "<button class='btn btn-default button--LR'><a href='" + url + "' target='_blank'>" + i18next.t("Edit in Liferay") + "</a></button>" +
        "</div>"
    );
    if (show) { $(".button--LR").addClass("data-show");}
}
function __getLoaderHTML(message) {
    return '<div class="loading-message-indicator"><i class="fa fa-spinner fa-spin fa-2x"></i>' + (hasValue(message) ? "&nbsp;" + message : "") + '</div>';
}
function __convertToNumericField(field) {
    if (field) {
        if (_isTouchDevice()) {
            field.each(function() {
                $(this).prop("type", "tel");
            });
        }
    }
}
function isString(obj) {
    return (Object.prototype.toString.call(obj) === "[object String]");
}
function disableHeaderFooterLinks() {
    var links = $("#tnthNavWrapper a, #homeFooter a").not("a[href*='logout']").not("a.required-link").not("a.home-link");
    links.addClass("disabled");
    links.prop("onclick", null).off("click");
    links.on("click", function(e) {
        e.preventDefault();
        return false;
    });
}

function pad(n) {
    n = parseInt(n);
    return (!isNaN(n) && n < 10) ? "0" + n : n;
}
function escapeHtml(text) {
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
}
function containHtmlTags(text) {
    if (!hasValue(text)) {
        return false;
    }
    return /[<>]/.test(text);
}
function __getExportFileName(prefix) {
    var d = new Date();
    return (prefix ? prefix : "ExportList_") + ("00" + d.getDate()).slice(-2) + ("00" + (d.getMonth() + 1)).slice(-2) + d.getFullYear();
}
function capitalize(str) {
    return str.replace(/\w\S*/g, function(txt) {
        return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
    });
}
function restoreVis() {
    var loadingElement = document.getElementById("loadingIndicator"), mainElement = document.getElementById("mainHolder");
    if (loadingElement) { loadingElement.setAttribute("style", "display:none; visibility:hidden;"); }
    if (mainElement) { mainElement.setAttribute("style", "visibility:visible;-ms-filter:'progid:DXImageTransform.Microsoft.Alpha(Opacity=100)';filter:alpha(opacity=100); -moz-opacity:1; -khtml-opacity:1; opacity:1"); }
}
function VueErrorHandling() {
    if (typeof Vue === "undefined") { return false; } /*global Vue */
    Vue.config.errorHandler = function (err, vm, info)  {
        var handler, current = vm;
        if (vm.$options.errorHandler) {
            handler = vm.$options.errorHandler;
        } else {
            while (current.$parent) {
                current = current.$parent;
                handler = current.$options.errorHandler;
                if (handler) {
                    break;
                }
            }
        }
        if (handler) { handler.call(current, err, vm, info); }
        else {
            console.log(err);
        }
        restoreVis();
    };
}
function checkJQuery() {
    if (typeof jQuery === "undefined") {
        restoreVis();
        return false;
    }
    return true;
}
(function($) {
    if (!$) { return false; }
    var __winHeight = $(window).height(), __winWidth = $(window).width();
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
})(checkJQuery()?jQuery: null);
// Extend an object with an extension
function extend(obj, extension) {
    for (var key in extension) {
        obj[key] = extension[key];
    }
    return obj;
}
function getUrlParameter(name) {
    name = name.replace(/[\[]/, "\\[").replace(/[\]]/, "\\]");
    var regex = new RegExp("[\\?&]" + name + "=([^&#]*)");
    var results = regex.exec(location.search);
    return results === null ? "" : decodeURIComponent(results[1].replace(/\+/g, " "));
}
function displaySystemOutageMessage(locale) {
    locale = locale || "en-us";
    locale = locale.replace("_", "-");
    var systemMaintenanceElId = "systemMaintenanceContainer";
    if (!document.getElementById(systemMaintenanceElId)) { //check for system outage maintenance message element
        return;
    }
    ajaxRequest("api/settings", {contentType: "application/json; charset=utf-8"}, function(data) {
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
            messageElement.innerHTML = escapeHtml(data.MAINTENANCE_MESSAGE);
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
            var displayStartDate = startDate.toLocaleString(locale,options).replace(/\,/g, " "); //display language-sensitive representation of date/time
            var displayEndDate = endDate.toLocaleString(locale, options).replace(/\,/g, " ");
            var message = ["<div>" + i18next.t("Hi there.") + "</div>",
                            "<div>" + i18next.t("TrueNTH will be down for website maintenance starting <b>{startdate}</b>. This should last until <b>{enddate}</b>.".replace("{startdate}", displayStartDate).replace("{enddate}", displayEndDate)) + "</div>",
                            "<div>" + i18next.t("Thanks for your patience while we upgrade our site.") + "</div>"].join("");
            messageElement.innerHTML = escapeHtml(message);
        } catch(e) {
            console.log("Error occurred converting system outage date/time ", e);
            document.getElementById(systemMaintenanceElId).classList.add("tnth-hide");
        }
    });
}
/**
 * Protect window.console method calls, e.g. console is not defined on IE
 * unless dev tools are open, and IE doesn't define console.debug
 */
(function() {
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
})();