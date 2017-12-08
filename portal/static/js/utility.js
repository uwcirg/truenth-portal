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
        };
        // Otherwise call the native setRequestHeader method
        // Note: setRequestHeader requires its 'this' to be the xhr object,
        // which is what 'this' is here when executed.
        setRequestHeader.call(this, name, value);
    };
    // pass it on to jQuery
    return xhr;
}
// populate portal banner content
function embed_page(data){
    $("#mainNav")
        // Embed data returned by AJAX call into container element
        .html(data);
        loader();
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
    };
}
// Loading indicator that appears in UI on page loads and when saving
var loader = function(show) {
    //landing page
    if ($("#fullSizeContainer").length > 0) {
        hideLoader();
        showMain();
        return false;
    };
    if (show) {
        $("#loadingIndicator").show();
    } else {
        if (!DELAY_LOADING) {
            setTimeout(function() { showMain(); }, 100);
            hideLoader(true);
        };
    };
};

function getIEVersion() {
    var match = navigator.userAgent.match(/(?:MSIE |Trident\/.*; rv:)(\d+)/);
    return match ? parseInt(match[1]) : undefined;
};

var request_attempts = 0;
function newHttpRequest(url,callBack, noCache)
{
    request_attempts++;
    var xmlhttp;
    if (window.XDomainRequest)
    {
        xmlhttp=new XDomainRequest();
        xmlhttp.onload = function(){callBack(xmlhttp.responseText)};
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

funcWrapper = function() {
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

function LRKeyEvent() {
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
                "<button class='btn btn-default button--LR'><a href='" + url + "' target='_blank'>Edit in Liferay</a></button>" +
                "</div>"
                );
    if (show) {
        $(".button--LR").addClass("data-show");
    };

};
function getSaveLoaderDiv(parentID, containerID) {
    var el = $("#" + containerID + "_load");
    if (el.length === 0) {
        var c = $("#" + parentID + " #" + containerID);
        if (c.length > 0) {
            var snippet = '<div class="load-container">' + '<i id="' + containerID + '_load" class="fa fa-spinner fa-spin load-icon fa-lg save-info" style="margin-left:4px; margin-top:5px" aria-hidden="true"></i><i id="' + containerID + '_success" class="fa fa-check success-icon save-info" style="color: green" aria-hidden="true">Updated</i><i id="' + containerID + '_error" class="fa fa-times error-icon save-info" style="color:red" aria-hidden="true">Unable to Update.System error.</i></div>';
            if (window.getComputedStyle) {
                displayStyle = window.getComputedStyle(c.get(0), null).getPropertyValue("display");
            } else {
                displayStyle = (c.get(0)).currentStyle.display;
            };
            if (String(displayStyle) === "block") {
                c.append(snippet);
            } else {
                if (String(displayStyle) === "none" || !hasValue(displayStyle)) {
                    if (c.get(0).nodeName.toUpperCase() === "DIV" || c.get(0).nodeName.toUpperCase() === "P") {
                        c.append(snippet);
                    }
                    else {
                        c.after(snippet);
                    }
                } else {
                    c.after(snippet);
                };
            };
        };
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
            if (a.text > b.text) return 1;
            else if (a.text < b.text) return -1;
            else return 0; });
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


//Promise polyfill - IE doesn't support Promise - so need this
!function(e){function n(){}function t(e,n){return function(){e.apply(n,arguments)}}function o(e){if("object"!=typeof this)throw new TypeError("Promises must be constructed via new");if("function"!=typeof e)throw new TypeError("not a function");this._state=0,this._handled=!1,this._value=void 0,this._deferreds=[],s(e,this)}function i(e,n){for(;3===e._state;)e=e._value;return 0===e._state?void e._deferreds.push(n):(e._handled=!0,void o._immediateFn(function(){var t=1===e._state?n.onFulfilled:n.onRejected;if(null===t)return void(1===e._state?r:u)(n.promise,e._value);var o;try{o=t(e._value)}catch(i){return void u(n.promise,i)}r(n.promise,o)}))}function r(e,n){try{if(n===e)throw new TypeError("A promise cannot be resolved with itself.");if(n&&("object"==typeof n||"function"==typeof n)){var i=n.then;if(n instanceof o)return e._state=3,e._value=n,void f(e);if("function"==typeof i)return void s(t(i,n),e)}e._state=1,e._value=n,f(e)}catch(r){u(e,r)}}function u(e,n){e._state=2,e._value=n,f(e)}function f(e){2===e._state&&0===e._deferreds.length&&o._immediateFn(function(){e._handled||o._unhandledRejectionFn(e._value)});for(var n=0,t=e._deferreds.length;n<t;n++)i(e,e._deferreds[n]);e._deferreds=null}function c(e,n,t){this.onFulfilled="function"==typeof e?e:null,this.onRejected="function"==typeof n?n:null,this.promise=t}function s(e,n){var t=!1;try{e(function(e){t||(t=!0,r(n,e))},function(e){t||(t=!0,u(n,e))})}catch(o){if(t)return;t=!0,u(n,o)}}var a=setTimeout;o.prototype["catch"]=function(e){return this.then(null,e)},o.prototype.then=function(e,t){var o=new this.constructor(n);return i(this,new c(e,t,o)),o},o.all=function(e){var n=Array.prototype.slice.call(e);return new o(function(e,t){function o(r,u){try{if(u&&("object"==typeof u||"function"==typeof u)){var f=u.then;if("function"==typeof f)return void f.call(u,function(e){o(r,e)},t)}n[r]=u,0===--i&&e(n)}catch(c){t(c)}}if(0===n.length)return e([]);for(var i=n.length,r=0;r<n.length;r++)o(r,n[r])})},o.resolve=function(e){return e&&"object"==typeof e&&e.constructor===o?e:new o(function(n){n(e)})},o.reject=function(e){return new o(function(n,t){t(e)})},o.race=function(e){return new o(function(n,t){for(var o=0,i=e.length;o<i;o++)e[o].then(n,t)})},o._immediateFn="function"==typeof setImmediate&&function(e){setImmediate(e)}||function(e){a(e,0)},o._unhandledRejectionFn=function(e){"undefined"!=typeof console&&console&&console.warn("Possible Unhandled Promise Rejection:",e)},o._setImmediateFn=function(e){o._immediateFn=e},o._setUnhandledRejectionFn=function(e){o._unhandledRejectionFn=e},"undefined"!=typeof module&&module.exports?module.exports=o:e.Promise||(e.Promise=o)}(this);

/*!
 * Validator v0.9.0 for Bootstrap 3, by @1000hz
 * Copyright 2015 Cina Saffary
 * Licensed under http://opensource.org/licenses/MIT
 *
 * https://github.com/1000hz/bootstrap-validator
 */

+function(a){"use strict";function b(b){return this.each(function(){var d=a(this),e=a.extend({},c.DEFAULTS,d.data(),"object"==typeof b&&b),f=d.data("bs.validator");(f||"destroy"!=b)&&(f||d.data("bs.validator",f=new c(this,e)),"string"==typeof b&&f[b]())})}var c=function(b,d){this.$element=a(b),this.options=d,d.errors=a.extend({},c.DEFAULTS.errors,d.errors);for(var e in d.custom)if(!d.errors[e])throw new Error("Missing default error message for custom validator: "+e);a.extend(c.VALIDATORS,d.custom),this.$element.attr("novalidate",!0),this.toggleSubmit(),this.$element.on("input.bs.validator change.bs.validator focusout.bs.validator",a.proxy(this.validateInput,this)),this.$element.on("submit.bs.validator",a.proxy(this.onSubmit,this)),this.$element.find("[data-match]").each(function(){var b=a(this),c=b.data("match");a(c).on("input.bs.validator",function(){b.val()&&b.trigger("input.bs.validator")})})};c.INPUT_SELECTOR=':input:not([type="submit"], button):enabled:visible',c.DEFAULTS={delay:500,html:!1,disable:!0,custom:{},errors:{match:"Does not match",minlength:"Not long enough"},feedback:{success:"glyphicon-ok",error:"glyphicon-remove"}},c.VALIDATORS={"native":function(a){var b=a[0];return b.checkValidity?b.checkValidity():!0},match:function(b){var c=b.data("match");return!b.val()||b.val()===a(c).val()},minlength:function(a){var b=a.data("minlength");return!a.val()||a.val().length>=b}},c.prototype.validateInput=function(b){var c=a(b.target),d=c.data("bs.validator.errors");if(c.is('[type="radio"]')&&(c=this.$element.find('input[name="'+c.attr("name")+'"]')),this.$element.trigger(b=a.Event("validate.bs.validator",{relatedTarget:c[0]})),!b.isDefaultPrevented()){var e=this;this.runValidators(c).done(function(f){c.data("bs.validator.errors",f),f.length?e.showErrors(c):e.clearErrors(c),d&&f.toString()===d.toString()||(b=f.length?a.Event("invalid.bs.validator",{relatedTarget:c[0],detail:f}):a.Event("valid.bs.validator",{relatedTarget:c[0],detail:d}),e.$element.trigger(b)),e.toggleSubmit(),e.$element.trigger(a.Event("validated.bs.validator",{relatedTarget:c[0]}))})}},c.prototype.runValidators=function(b){function d(a){return b.data(a+"-error")||b.data("error")||"native"==a&&b[0].validationMessage||g.errors[a]}var e=[],f=a.Deferred(),g=this.options;return b.data("bs.validator.deferred")&&b.data("bs.validator.deferred").reject(),b.data("bs.validator.deferred",f),a.each(c.VALIDATORS,a.proxy(function(a,c){if((b.data(a)||"native"==a)&&!c.call(this,b)){var f=d(a);!~e.indexOf(f)&&e.push(f)}},this)),!e.length&&b.val()&&b.data("remote")?this.defer(b,function(){var c={};c[b.attr("name")]=b.val(),a.get(b.data("remote"),c).fail(function(a,b,c){e.push(d("remote")||c)}).always(function(){f.resolve(e)})}):f.resolve(e),f.promise()},c.prototype.validate=function(){var a=this.options.delay;return this.options.delay=0,this.$element.find(c.INPUT_SELECTOR).trigger("input.bs.validator"),this.options.delay=a,this},c.prototype.showErrors=function(b){var c=this.options.html?"html":"text";this.defer(b,function(){var d=b.closest(".form-group"),e=d.find(".help-block.with-errors"),f=d.find(".form-control-feedback"),g=b.data("bs.validator.errors");g.length&&(g=a("<ul/>").addClass("list-unstyled").append(a.map(g,function(b){return a("<li/>")[c](b)})),void 0===e.data("bs.validator.originalContent")&&e.data("bs.validator.originalContent",e.html()),e.empty().append(g),d.addClass("has-error"),f.length&&f.removeClass(this.options.feedback.success)&&f.addClass(this.options.feedback.error)&&d.removeClass("has-success"))})},c.prototype.clearErrors=function(a){var b=a.closest(".form-group"),c=b.find(".help-block.with-errors"),d=b.find(".form-control-feedback");c.html(c.data("bs.validator.originalContent")),b.removeClass("has-error"),d.length&&d.removeClass(this.options.feedback.error)&&d.addClass(this.options.feedback.success)&&b.addClass("has-success")},c.prototype.hasErrors=function(){function b(){return!!(a(this).data("bs.validator.errors")||[]).length}return!!this.$element.find(c.INPUT_SELECTOR).filter(b).length},c.prototype.isIncomplete=function(){function b(){return"checkbox"===this.type?!this.checked:"radio"===this.type?!a('[name="'+this.name+'"]:checked').length:""===a.trim(this.value)}return!!this.$element.find(c.INPUT_SELECTOR).filter("[required]").filter(b).length},c.prototype.onSubmit=function(a){this.validate(),(this.isIncomplete()||this.hasErrors())&&a.preventDefault()},c.prototype.toggleSubmit=function(){if(this.options.disable){var b=a('button[type="submit"], input[type="submit"]').filter('[form="'+this.$element.attr("id")+'"]').add(this.$element.find('input[type="submit"], button[type="submit"]'));b.toggleClass("disabled",this.isIncomplete()||this.hasErrors())}},c.prototype.defer=function(b,c){return c=a.proxy(c,this),this.options.delay?(window.clearTimeout(b.data("bs.validator.timeout")),void b.data("bs.validator.timeout",window.setTimeout(c,this.options.delay))):c()},c.prototype.destroy=function(){return this.$element.removeAttr("novalidate").removeData("bs.validator").off(".bs.validator"),this.$element.find(c.INPUT_SELECTOR).off(".bs.validator").removeData(["bs.validator.errors","bs.validator.deferred"]).each(function(){var b=a(this),c=b.data("bs.validator.timeout");window.clearTimeout(c)&&b.removeData("bs.validator.timeout")}),this.$element.find(".help-block.with-errors").each(function(){var b=a(this),c=b.data("bs.validator.originalContent");b.removeData("bs.validator.originalContent").html(c)}),this.$element.find('input[type="submit"], button[type="submit"]').removeClass("disabled"),this.$element.find(".has-error").removeClass("has-error"),this};var d=a.fn.validator;a.fn.validator=b,a.fn.validator.Constructor=c,a.fn.validator.noConflict=function(){return a.fn.validator=d,this},a(window).on("load",function(){a('form[data-toggle="validator"]').each(function(){var c=a(this);b.call(c,c.data())})})}(jQuery);

/* ============================================================
 * Bootstrap: rowlink.js v3.1.3
 * http://jasny.github.io/bootstrap/javascript/#rowlink
 * ============================================================
 * Copyright 2012-2014 Arnold Daniels
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ============================================================ */
+function($){"use strict";var Rowlink=function(element,options){this.$element=$(element)
this.options=$.extend({},Rowlink.DEFAULTS,options)
this.$element.on('click.bs.rowlink','td:not(.rowlink-skip)',$.proxy(this.click,this))}
Rowlink.DEFAULTS={target:"a"}
Rowlink.prototype.click=function(e){var target=$(e.currentTarget).closest('tr').find(this.options.target)[0]
if($(e.target)[0]===target)return
e.preventDefault();if(target.click){target.click()}else if(document.createEvent){var evt=document.createEvent("MouseEvents");evt.initMouseEvent("click",true,true,window,0,0,0,0,0,false,false,false,false,0,null);target.dispatchEvent(evt);}}
var old=$.fn.rowlink
$.fn.rowlink=function(options){return this.each(function(){var $this=$(this)
var data=$this.data('bs.rowlink')
if(!data)$this.data('bs.rowlink',(data=new Rowlink(this,options)))})}
$.fn.rowlink.Constructor=Rowlink
$.fn.rowlink.noConflict=function(){$.fn.rowlink=old
return this}
$(document).on('click.bs.rowlink.data-api','[data-link="row"]',function(e){if($(e.target).closest('.rowlink-skip').length!==0)return
var $this=$(this)
if($this.data('bs.rowlink'))return
$this.rowlink($this.data())
$(e.target).trigger('click.bs.rowlink')})}(window.jQuery);