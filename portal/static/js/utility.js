function equalHeightBoxes(passClass) {
    var windowsize = $(window).width();
    // Switch back to auto for small screen or to recalculate on larger
    $("."+passClass).css("height","auto");
    if (windowsize > 768 && $("."+passClass).length > 1) {
        var elementHeights = $("."+passClass).map(function() {
            return $(this).height();
        }).get();
        // Math.max takes a variable number of arguments
        // `apply` is equivalent to passing each height as an argument
        var maxHeight = Math.max.apply(null, elementHeights);
        // Set each height to the max height
        $("."+passClass).height(maxHeight);
    }
}
// Return an XHR without XHR header so  it doesn't need to be explicitly allowed with CORS
function xhr_function(){
    // Get new xhr object using default factory
    var xhr = jQuery.ajaxSettings.xhr();
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
                          "visibility" : "visible",
                          "-ms-filter": "progid:DXImageTransform.Microsoft.Alpha(Opacity=100)",
                          "filter": "alpha(opacity=100)",
                          "-moz-opacity": 1,
                          "-khtml-opacity": 1,
                          "opacity": 1
                        });

}
function hideLoader(delay, time ) {
    if (delay) {
        $("#loadingIndicator").hide();
    } else {
        setTimeout(function() { $("#loadingIndicator").fadeOut();}, time||200);
    }
}
// Loading indicator that appears in UI on page loads and when saving
var loader = function(show) {
    //landing page
    if ($("#fullSizeContainer").length > 0) {
        hideLoader();
        showMain();
        return false;
    }
    if (show) {
        $("#loadingIndicator").show();
    } else {
        if (!DELAY_LOADING) {
            setTimeout(function() { showMain(); }, 100);
            hideLoader(true);
        }
    }
};

// populate portal banner content
function embed_page(data){
    $("#mainNav")
        // Embed data returned by AJAX call into container element
        .html(data);
        loader();
}

function getIEVersion() {
    var match = navigator.userAgent.match(/(?:MSIE |Trident\/.*; rv:)(\d+)/);
    return match ? parseInt(match[1]) : undefined;
};

var request_attempts = 0;
/*
 * note: this function supports older version of IE (version <= 9)
 * jquery ajax calls errored in older IE version
 */
function newHttpRequest(url,callBack, noCache)
{
    request_attempts++;
    var xmlhttp;
    if (window.XDomainRequest)
    {
        xmlhttp=new XDomainRequest();
        xmlhttp.onload = function(){callBack(xmlhttp.responseText);};
    } else if (window.XMLHttpRequest) {
        xmlhttp=new XMLHttpRequest();
    }
    else {
        xmlhttp=new ActiveXObject("Microsoft.XMLHTTP");
    };
    xmlhttp.onreadystatechange=function()
    {
        if (xmlhttp.readyState===4) {
            if (xmlhttp.status===200) {
                if (callBack) {
                    callBack(xmlhttp.responseText);
                };
            } else {
                if (request_attempts < 3) {
                    setTimeout ( function(){ newHttpRequest(url,callBack, noCache); }, 3000 );
                }
                else {
                    loader();
                };
            };
        };
    };
    if (noCache) {
        url = url + ((/\?/).test(url) ? "&" : "?") + (new Date()).getTime();
    };
    xmlhttp.open("GET",url,true);
    xmlhttp.send();
};

funcWrapper = function(PORTAL_NAV_PAGE) {
    if (PORTAL_NAV_PAGE) {
        request_attempts++;
        $.ajax({
            url: PORTAL_NAV_PAGE,
            type:"GET",
            contentType:"text/plain",
            timeout: 5000,
            cache: (getIEVersion() ? false : true)
        }, "html")
        .done(function(data) {
            embed_page(data);
        })
        .fail(function(jqXHR, textStatus, errorThrown) {
          //  console.log("Error loading nav elements from " + PORTAL_HOSTNAME);
            if (request_attempts < 3) {
                setTimeout ( function(){ funcWrapper( ) }, 3000 );
            } else {
                loader();
            };
        })
        .always(function() {
            loader();
            request_attempts = 0;
        });
    };
};

function LRKeyEvent() {
    var LR_INVOKE_KEYCODE = 187;
    if ($(".button--LR").length > 0) {
        $("html").on("keydown", function(e) {
            if (parseInt(e.keyCode) === parseInt(LR_INVOKE_KEYCODE)) {
               $(".button--LR").toggleClass("data-show");
            };
        });
    };
};

function appendLREditContainer(target, url, show) {
    if (!hasValue(url)) {
        return false;
    };
    if (!target) {
        target = $(document);
    };
    target.append("<div>" +
                "<button class='btn btn-default button--LR'><a href='" + url + "' target='_blank'>" + i18next.t("Edit in Liferay") + "</a></button>" +
                "</div>"
                );
    if (show) {
        $(".button--LR").addClass("data-show");
    };

};

function __getLoaderHTML(message) {
    return '<div class="loading-message-indicator"><i class="fa fa-spinner fa-spin fa-2x"></i>' + (hasValue(message)?"&nbsp;"+message:"") + '</div>';
}
function _isTouchDevice(){
    return true === ("ontouchstart" in window || window.DocumentTouch && document instanceof DocumentTouch);
};
function __convertToNumericField(field) {
    if (field) {
        if (_isTouchDevice()) {
            field.each(function() {$(this).prop("type", "tel");});
        };
    };
};
function hasValue(val) {
    return val != null && val != "" && val != "undefined";
};
function isString (obj) {
    return (Object.prototype.toString.call(obj) === '[object String]');
};
function disableHeaderFooterLinks() {
    var links = $("#tnthNavWrapper a, #homeFooter a").not("a[href*='logout']").not("a.required-link").not("a.home-link");
    links.addClass("disabled");
    links.prop("onclick",null).off("click");
    links.on("click", function(e) {
        e.preventDefault();
        return false;
    });
};
function pad(n) {
    n = parseInt(n); return (n < 10) ? '0' + n : n;
};
function escapeHtml(text) {
    "use strict";
    if (text === null || text !== "undefined" || String(text).length === 0) {
        return text;
    }
    return text.replace(/[\"&'\/<>]/g, function (a) {
        return {
            '"': "&quot;", "&": "&amp;", "'": "&#39;",
            "/": "&#47;",  "<": "&lt;",  ">": "&gt;"
        }[a];
    });
};
function containHtmlTags(text) {
    if (!hasValue(text)) {
        return false;
    };
    return /[<>]/.test(text);
};
function __getExportFileName(prefix) {
    var d = new Date();
    return (prefix?prefix:"ExportList_")+("00" + d.getDate()).slice(-2)+("00" + (d.getMonth() + 1)).slice(-2)+d.getFullYear();
}
function capitalize(str)
{
    return str.replace(/\w\S*/g, function(txt){return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();});
}
var __winHeight = $(window).height(), __winWidth = $(window).width();
$.fn.isOnScreen = function(){
    var viewport = {};
    viewport.top = $(window).scrollTop();
    viewport.bottom = viewport.top + __winHeight;
    var bounds = {};
    bounds.top = this.offset().top;
    bounds.bottom = bounds.top + this.outerHeight();
    return ((bounds.top <= viewport.bottom) && (bounds.bottom >= viewport.top));
};
$.fn.sortOptions = function() {
    var selectOptions = $(this).find("option");
    selectOptions.sort(function(a, b) {
        if (a.text > b.text) {
            return 1;
        }
        else if (a.text < b.text) {
            return -1;
        }
        else {
            return 0;
        }
    });
      return selectOptions;
};
// Extend an object with an extension
function extend( obj, extension ){
  for ( var key in extension ){
    obj[key] = extension[key];
  }
};

/**
 * Protect window.console method calls, e.g. console is not defined on IE
 * unless dev tools are open, and IE doesn't define console.debug
 */
(function() {
    var console = (window.console = window.console || {});
    var noop = function () {};
    var log = console.log || noop;
    var start = function(name) { return function(param) { log("Start " + name + ": " + param); } };
    var end = function(name) { return function(param) { log("End " + name + ": " + param); } };

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

        assert: noop, clear: noop, trace: noop, count: noop, timeStamp: noop, msIsIndependentlyComposed: noop,
        debug: log, info: log, log: log, warn: log, error: log,
        dir: log, dirxml: log, markTimeline: log,
        group: start('group'), groupCollapsed: start('groupCollapsed'), groupEnd: end('group'),
        profile: start('profile'), profileEnd: end('profile'),
        time: start('time'), timeEnd: end('time')
    };

    for (var method in methods) {
        if ( methods.hasOwnProperty(method) && !(method in console) ) { // define undefined methods as best-effort methods
            console[method] = methods[method];
        }
    }
})();