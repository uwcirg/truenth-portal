import tnthDates from "./TnthDate.js";
var Utility = (function() {
    var UtilityObj = function() { /*global $ */
        this.requestAttempts = 0;
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
    UtilityObj.prototype.hideLoaderOncallback = function(time) {
        setTimeout(function() {
            $("#loadingIndicator").fadeOut();
            $("body").removeClass("vis-on-callback");
        }, time || 200);
    };
    UtilityObj.prototype.hideLoader = function(time) {
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
            this.hideLoader(350);
        }
    };
    UtilityObj.prototype.isDelayLoading = function() { /*global DELAY_LOADING*/
        return (typeof DELAY_LOADING !== "undefined") && DELAY_LOADING;
    };
    UtilityObj.prototype.isTouchDevice = function() {
        return true === ("ontouchstart" in window || window.DocumentTouch && document instanceof window.DocumentTouch);
    };
    UtilityObj.prototype.getIEVersion = function() {
        var match = navigator.userAgent.match(/(?:MSIE |Trident\/.*; rv:)(\d+)/);
        return match ? parseInt(match[1]) : false;
    };
    UtilityObj.prototype.newHttpRequest = function(url, params, callBack) { /* note: this function supports older version of IE (version <= 9) - jquery ajax calls errored in older IE version*/
        this.requestAttempts++;
        var xmlhttp, self = this;
        callBack = callBack || function() {};
        if (window.XDomainRequest) { /*global XDomainRequest */
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
    UtilityObj.prototype.getLoaderHTML = function(message) {
        return `<div class="loading-message-indicator"><i class="fa fa-spinner fa-spin fa-2x"></i>${message ? "&nbsp;" + message : ""}</div>`;
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
            if (vm && vm.$options && vm.$options.errorHandler) {
                handler = vm.$options.errorHandler;
            } else {
                while (!handler && current && current.$parent) {
                    current = current.$parent;
                    handler = current.$options ? current.$options.errorHandler : null;
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
    UtilityObj.prototype.extend = function(obj, extension) { // Extend an object with an extension
        for (var key in extension) {
            if (extension.hasOwnProperty(key)) {
                obj[key] = extension[key];
            }
        }
        return obj;
    };
    UtilityObj.prototype.capitalize = function(str) {
        if (!str) {
            return "";
        }
        const word = [];
        for(let char of str.split(" ")){
            word.push(char[0].toUpperCase() + char.slice(1));
        }
        return word.join(" ");
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
    UtilityObj.prototype.isSVGSupported = function() {
        return document.implementation.hasFeature('http://www.w3.org/TR/SVG11/feature#Image', '1.1');
    };
    UtilityObj.prototype.setNoSVGSupportCssClass = function() {
        if (!this.isSVGSupported()) {
            $("body").addClass("no-svg-support");
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
            //use maintenance window specified in config to compose the message
            //assuming in following example format: ["2018-11-02T12:00:00Z", "2018-11-02T18:00:00Z"], dates in system ISO format
            var hoursDiff = function(d1, d2) {
                if (!d1 || !d2) {
                    return 0;
                }
                return Math.floor(((d2.getTime() - d1.getTime())/ (1000 * 60 * 60)) % 24);
            };
            var hideSystemMaintenanceElement = function() {
                document.getElementById(systemMaintenanceElId).classList.add("tnth-hide");
            };
            //date object automatically convert iso date/time to local date/time as it assumes a timezone of UTC if date in ISO format
            //format dates in system ISO 8601 format first, if not already
            //valid date examples: 2018-06-09T16:00:00Z, 2019-07-09T22:30:00-7:00, 2019-05-24T15:54:14.876Z
            var startDate = new Date(tnthDates.formatDateString(data.MAINTENANCE_WINDOW[0], "system")),
                endDate = new Date(tnthDates.formatDateString(data.MAINTENANCE_WINDOW[1], "system"));
            if (!tnthDates.isDate(startDate)) {
                //display error in console
                console.log("invalid start date entry - must be in valid format", data.MAINTENANCE_WINDOW[0]);
                hideSystemMaintenanceElement();
                return;
            }
            if (!tnthDates.isDate(endDate)) {
                //indicate error in console
                console.log("invalid end date entry - must be in valid format", data.MAINTENANCE_WINDOW[1]);
                hideSystemMaintenanceElement();
                return;
            }

            var hoursTilEnd = hoursDiff(new Date(), endDate); //use end date of the maintenance window
            if (hoursTilEnd < 0 || isNaN(hoursTilEnd)) { //maintenance window has passed
                hideSystemMaintenanceElement();
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
                hideSystemMaintenanceElement();
            }
        });
    };
    return new UtilityObj();
})();
export default Utility;
export var getExportFileName = Utility.getExportFileName; /* expose common functions */
export var getUrlParameter= Utility.getUrlParameter;
export var capitalize = Utility.capitalize;
/*
 * sorting an array of object by a field name, in ascending order
 */
export function sortArrayByField(arrObj, fieldName) {
    if (!arrObj || !fieldName) return false;
    let sortedArray = (arrObj).sort((a, b) => {
        var nameA = a[fieldName].toUpperCase(); // ignore upper and lowercase
        var nameB = b[fieldName].toUpperCase(); // ignore upper and lowercase
        if (nameA < nameB) {
          return -1;
        }
        if (nameA > nameB) {
          return 1;
        }
        // names must be equal
        return 0;
    });
    return sortedArray;
}
/*
 * convert an object into array based on an given key
 */
export function convertArrayToObject (array, key) {
    if (!array) {
        return false;
    }
    if (!Array.isArray(array)) {
        return array;
    }
    array.reduce((acc, curr, index) => {
        let useKey = curr[key];
        if (!useKey) useKey = index;
        acc[useKey] = curr;
        return acc;
    }, {});
    return array;
}
