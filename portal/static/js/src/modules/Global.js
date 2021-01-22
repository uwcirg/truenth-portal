import Utility from "./Utility.js";
import Validator from "./Validator.js";
import {EPROMS_SUBSTUDY_ID} from "../data/common/consts.js";

export default { /*global $ i18next */ /*initializing functions performed only once on page load */
    "init": function(){
        this.registerModules();
        this.setCustomJQueryEvents(this.checkJQuery()?(jQuery): null); /*global jQuery*/
        this.consolePolyFill();
        Utility.setNoSVGSupportCssClass();
    },
    "registerModules": function() {
        if (typeof i18next === "undefined") { i18next = {t: function(key) { return key; }}; } //fallback for i18next in older browser?
        if (!window.portalModules) {
            window.portalModules = {};
        }
        if (typeof i18next !== "undefined") {
            window.portalModules.i18next = i18next;
        }
        window.portalModules.Global = this;
    },
    "checkJQuery": function() {
        if (typeof jQuery === "undefined") {
            this.restoreVis();
            return false;
        }
        return true;
    },
    "handleClientInterventionForm": function() {
        if (document.querySelector("#clientAppForm")) {
            $("#confirmDel").popover({
                html : true, //internal use, so no need to translate here?
                content: "Are you sure you want to delete this app?<br /><br /><button type='submit' name='delete' value='delete' class='btn-tnth-primary btn'>Delete Now</button> &nbsp; <div class='btn btn-default' id='cancelDel'>Cancel</div>"
            });
            $("body").on("click","#cancelDel",function(){
                $("#confirmDel").popover("hide");
            });
        }
    },
    "onPageDidLoad": function(userSetLang) {
        //note: display system outage message only after i18next has been instantiated - allowing message to be translated
        Utility.displaySystemOutageMessage(userSetLang); /*global displaySystemOutageMessage */
        this.showAlert();
        this.handleNumericFields();
        var LREditElement = document.getElementById("LREditUrl");
        if (LREditElement) {
            this.appendLREditContainer(document.querySelector("#mainHolder .LREditContainer"), LREditElement.value, LREditElement.getAttribute("data-show"));
        }
        this.prePopulateEmail();
        this.beforeSendAjax();
        this.unloadEvent();
        this.footer();
        this.loginAs();
        this.initValidator();
        this.handleClientInterventionForm();
    },
    "getCurrentUser": function(callback) {
        callback = callback || function() {};
        let cachedCurrentUserId = sessionStorage.getItem("current_user_id");
        if (cachedCurrentUserId) {
            callback(cachedCurrentUserId);
            return cachedCurrentUserId;
        }
        $.ajax({
            type: "GET",
            url: "/api/me",
            async: false
        }).done(function(data) {
            var userId = "";
            if (data) { userId = data.id; }
            if (!userId) {
                callback();
                return;
            }
            sessionStorage.setItem("current_user_id", userId);
            callback(userId);
        }).fail(function() {
            callback();
        });

        return cachedCurrentUserId;
    },
    /*
     * dynamically show/hide sub-study specific UI resources elements
     * for the consumption by staff users
     * @param elementSelector A DOMString containing one or more selectors to match, e.g. #tnthWrapper .blah
     */
    setSubstudyResourcesVis: function(elementSelector, callback) {
        callback = callback || function() {};
        if (!elementSelector) {
            callback({error: true});
            return;
        }
        this.getCurrentUser((userId) => {
            if (!userId) return;
            $.ajax({
                type: "GET",
                url: `/api/staff/${userId}/research_study`
            }).done(data => {
                if (!data || !data.research_study || !data.research_study.length) {
                    callback({error: true});
                    return;
                }
                let substudyRS = (data.research_study).filter(item => item.id === EPROMS_SUBSTUDY_ID);
                if (substudyRS.length) {
                    $(elementSelector).show();
                } else {
                    $(elementSelector).hide();
                }
                callback(data);
            });
        });
    },
    "prePopulateEmail": function() {
        var requestEmail =  Utility.getUrlParameter("email"), emailField = document.querySelector("#email");
        if (requestEmail && emailField) { /*global Utility getUrlParameter */
            emailField.value = requestEmail;
        }
    },
    "handleDisableLinks": function() {
        if (Utility.getUrlParameter("disableLinks")) {
            Utility.disableHeaderFooterLinks();
        }
    },
    "beforeSendAjax": function() {
        $.ajaxSetup({
            beforeSend: function(xhr, settings) {
                if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                    xhr.setRequestHeader("X-CSRFToken", $("#__CRSF_TOKEN").val());
                }
            }
        });
    },
    "showAlert": function() {
        if ($("#alertModal").length > 0) {  $("#alertModal").modal("show");}
    },
    "restoreVis": function() {
        var loadingElement = document.getElementById("loadingIndicator"), mainElement = document.getElementById("mainHolder");
        if (loadingElement) { loadingElement.setAttribute("style", "display:none; visibility:hidden;"); }
        if (mainElement) { mainElement.setAttribute("style", "visibility:visible;-ms-filter:'progid:DXImageTransform.Microsoft.Alpha(Opacity=100)';filter:alpha(opacity=100); -moz-opacity:1; -khtml-opacity:1; opacity:1"); }
    },
    "showLoader": function() {
        document.querySelector("#loadingIndicator").setAttribute("style", "display:block; visibility:visible;");
    },
    "embedPortalWrapperContent": function(data) {
        if (data && !data.error) {
            $("#mainNav").html(data);
        }
    },
    "initPortalWrapper": function(PORTAL_NAV_PAGE, callback) {
        var self = this;
        callback = callback || function() {};
        this.showLoader();
        Utility.sendRequest(PORTAL_NAV_PAGE, {cache: false}, function(data) { /*global sendRequest */
            if (!data || data.error) {
                document.querySelector("#mainNavLoadingError").innerHTML = i18next.t("Error loading portal wrapper");
                self.restoreVis();
                callback();
                return false;
            }
            self.embedPortalWrapperContent(data);
            setTimeout(function() {
                self.restoreVis();
                $("#tnthNavWrapper .logout").on("click", function(event) {
                    event.stopImmediatePropagation();
                    self.handleLogout();
                });
                self.handleDisableLinks();
                /*
                 * show sub-study specific resources links
                 */
                self.setSubstudyResourcesVis("#tnthNavWrapper .empro-resources");
            }, 350);
            self.getNotification(function(data) { //ajax to get notifications information
                self.notifications(data);
            });
            callback();
        });
    },
    "loginAs": function() {
        var LOGIN_AS_PATIENT = (typeof sessionStorage !== "undefined") ? sessionStorage.getItem("loginAsPatient") : null;
        if (!LOGIN_AS_PATIENT) { return false; }
        this.clearSessionLocale();
        this.getUserLocale(); //need to clear current user locale in session storage when logging in as patient
        Utility.resetBrowserBackHistory(); /*global resetBrowserBackHistory */
    },
    "handleLogout": function() {
        sessionStorage.clear();
        sessionStorage.setItem("logout", "true"); //set session storage logout indicator
    },
    "unloadEvent": function() {
        var self = this;
        $(window).on("beforeunload", function() {
            if (Utility.getUrlParameter("logout")) { //taking into consideration that user may type in logout in url
                self.handleLogout();
            }
        });
    },
    "localeSessionKey": "currentUserLocale",
    "clearSessionLocale": function() {
        sessionStorage.removeItem(this.localeSessionKey);
    },
    "appendLREditContainer": function(target, url, show) { /*global i18next */
        if (!url) { return false; }
        if (!target) { return false; }
        $(target).append(`<div><button class="btn btn-default button--LR"><a href="${url}" target="_blank">${i18next.t("Edit in Liferay")}</a></button></div>`);
        if (String(show).toLowerCase() === "true") { $(".button--LR").addClass("data-show");}
        else {
            $(".button--LR").addClass("tnth-hide");
        }
    },
    "getUserLocale": function() {
        var sessionKey = this.localeSessionKey;
        var sessionLocale = sessionStorage.getItem(sessionKey);
        var sessionLocaleElement = document.querySelector("#userSessionLocale");
        var userSessionLocale = sessionLocaleElement ? sessionLocaleElement.value: "";
        if (userSessionLocale) {
            //note this is a template variable whose value is set at the backend.  Note, it will set to EN_US pre-authentication, cannot set sessionStorage here as it will be incorrect
            sessionStorage.setItem(sessionKey, userSessionLocale);
            return userSessionLocale;
        }
        if (sessionLocale) {
            return sessionLocale;
        }
        if (!this.checkJQuery()) {
            return false;
        }
        var locale = "en_us";
        this.getCurrentUser(function(userId) {
            if (!userId) {
                locale = "en_us";
                return false;
            }
            $.ajax({
                type: "GET",
                url: "/api/demographics/" + userId, //dont use tnthAjax method - don't want to report error here if failed
                async: false
            }).done(function(data) {
                if (!data || !data.communication) {
                    locale = "en_us";
                    return false;
                }
                data.communication.forEach(function(item) {
                    if (item.language) {
                        locale = item.language.coding[0].code;
                        sessionStorage.setItem(sessionKey, locale);
                    }
                });
            });
        });
        return locale;
    },
    "getCopyrightYear": function(callback) {
        callback = callback || function() {};
        var configSuffix = "COPYRIGHT_YEAR";
        var stCopyRight = sessionStorage.getItem("config_"+configSuffix);
        if (stCopyRight) {
            let copyrightObject = {};
             //specifically set property key of object via variable, otherwise it will be interpreted literally as string
             //caveat for setting object key via variable: https://stackoverflow.com/questions/11508463/javascript-set-object-key-by-variable
            copyrightObject[configSuffix] = stCopyRight;
            callback(copyrightObject);
            return;
        }
        Utility.ajaxRequest("/api/settings/"+configSuffix, false, function(data) {
            if (data && data.hasOwnProperty(configSuffix)) {
                sessionStorage.setItem("config_"+configSuffix, data[configSuffix]);
            }
            callback(data);
        });
    },
    "footer": function() {
        var self = this, logoLinks = $("#homeFooter .logo-link");
        if (logoLinks.length > 0) {
            logoLinks.each(function() {
                if (!$.trim($(this).attr("href"))) {
                    $(this).removeAttr("target");
                    $(this).on("click", function(e) {
                        e.preventDefault();
                        return false;
                    });
                }
            });
        }
        setTimeout(function() { //Reveal footer after load to avoid any flashes will above content loads
            $("#homeFooter").show();
        }, 100);

        setTimeout(function() {
            var userLocale = self.getUserLocale(), footerElements = $("#homeFooter .copyright");
            var copyright_year = new Date().getFullYear();
            self.getCopyrightYear(function(data) {
                if (data && data.hasOwnProperty("COPYRIGHT_YEAR")) {
                    copyright_year = data.COPYRIGHT_YEAR;
                }
                var getContent = (country_code, copyright_year) => {
                    var content = ""; //need to set this on callback as the call is asynchronous - otherwise the copyright value can be set before config value is returned
                    switch (String(country_code.toUpperCase())) { /* replace year with copyright year after text is translated */
                        case "US":
                            content = i18next.t("&copy; {year} Movember Foundation. All rights reserved. A registered 501(c)3 non-profit organization (Movember Foundation).").replace("{year}", copyright_year);
                            break;
                        case "AU":
                            content = i18next.t("&copy; {year} Movember Foundation. All rights reserved. Movember Foundation is a registered charity in Australia ABN 48894537905 (Movember Foundation).").replace("{year}", copyright_year);
                            break;
                        case "NZ":
                            content = i18next.t("&copy; {year} Movember Foundation. All rights reserved. Movember Foundation is a New Zealand registered charity number CC51320 (Movember Foundation).").replace("{year}", copyright_year);
                            break;
                        case "CA":
                        default:
                            content = i18next.t("&copy; {year} Movember Foundation (Movember Foundation). All rights reserved.").replace("{year}", copyright_year);
                        }
                    return content;
                };
                // todo: properly decouple country/locale
                var country_code = userLocale.split("_")[1];
                if (userLocale.toUpperCase() !== "EN_US"){ // shortcut - infer country from locale if locale isn't default (en_us)
                    footerElements.html(getContent(country_code, copyright_year));
                } else {
                    $.getJSON("//geoip.cirg.washington.edu/json/", function(data) {
                        //country code Australia AU New Zealand NZ USA US
                        if (data && data.country_code) {
                            footerElements.html(getContent(data.country_code, copyright_year));
                        } else {
                            footerElements.html(getContent(country_code, copyright_year));
                        }
                    });
                }
            });
        }, 500);
    },
    "getNotification": function(callback) {
        var userId = $("#notificationUserId").val();
        callback = callback || function() {};
        if (!userId) {
            callback({"error": i18next.t("User id is required")});
            return false;
        }
        $.ajax({
            type:"GET",
            url: "/api/user/"+userId+"/notification"
        }).done(function(data) {
            if (data) {
                callback(data);
            } else {
                callback({"error": i18next.t("no data returned")});
            }
        }).fail(function(){
            callback({"error": i18next.t("Error occurred retrieving notification.")});
        });
    },
    "deleteNotification": function(userId, notificationId) {
        if (!userId || parseInt(notificationId) < 0 || !notificationId) {
            return false;
        }
        var self = this;
        this.getNotification(function(data) {
            if (!data.notifications || !data.notifications.length) {
                return;
            }
            var arrNotification = $.grep(data.notifications, function(notification) { //check if there is notification for this id -dealing with use case where user deletes same notification in a separate open window
                return parseInt(notification.id) === parseInt(notificationId);
            });
            var userId = $("#notificationUserId").val();
            if (arrNotification.length) { //delete notification only if it exists
                $.ajax({
                    type: "DELETE",
                    url: "/api/user/" + userId + "/notification/" + notificationId
                }).done(function() {
                    $("#notification_" + notificationId).attr("data-visited", true);
                    $("#notification_" + notificationId).find("[data-action-required]").removeAttr("data-action-required");
                    self.setNotificationsDisplay();
                });
            }
        });
    },
    "notifications": function(data) {
        if (!data || !data.notifications || data.notifications.length === 0) {
            $("#notificationBanner").hide();
            return false;
        }
        var arrNotificationText = (data.notifications).map(function(notice) {
            return `<div class="notification" id="notification_${notice.id}" data-id="${notice.id}" data-name="${notice.name}">${notice.content}</div>`;
        });
        var self = this;
        $("#notificationBanner .content").html(arrNotificationText.join(""));
        $("#notificationBanner .notification").addClass("active");
        $("#notificationBanner").show();
        $("#notificationBanner [data-id] a").each(function() {
            $(this).on("click", function(e) {
                e.stopPropagation();
                var parentElement = $(this).closest(".notification");
                parentElement.attr("data-visited", "true"); //adding the attribute data-visited will hide the notification entry
                self.deleteNotification($("#notificationUserId").val(), parentElement.attr("data-id")); //delete relevant notification
                self.setNotificationsDisplay();
            });
        });
        $("#notificationBanner .close").on("click", function(e) { //closing the banner
            e.stopPropagation();
            $("#notificationBanner [data-id]").each(function() {
                var actionRequired = $(this).find("[data-action-required]").length > 0;
                if (!actionRequired) {
                    $(this).attr("data-visited", true);
                    self.deleteNotification($("#notificationUserId").val(), $(this).attr("data-id"));
                }
            });
            self.setNotificationsDisplay();
        });
        self.setNotificationsDisplay();
    },
    "setNotificationsDisplay": function() {
        if ($("#notificationBanner [data-action-required]").length > 0) { //requiring user action
            $("#notificationBanner .close").removeClass("active");
            return false;
        }
        var allVisited = true;
        $("#notificationBanner [data-id]").each(function() {
            if (allVisited && !$(this).attr("data-visited")) { //check if all links have been visited
                allVisited = false;
                return false;
            }
        });
        if (allVisited) {
            $("#notificationBanner").hide();
        } else {
            $("#notificationBanner .close").addClass("active");
        }
    },
    "setCustomJQueryEvents": function($) {
        if (!$) { return false; }
        var __winHeight = $(window).height();
        jQuery.fn.isOnScreen = function() {
            var viewport = {};
            viewport.top = $(window).scrollTop();
            viewport.bottom = viewport.top + __winHeight;
            var bounds = {};
            bounds.top = this && this.offset() ? this.offset().top : 0;
            bounds.bottom = bounds.top + this.outerHeight();
            return ((bounds.top <= viewport.bottom) && (bounds.bottom >= viewport.top));
        };
        jQuery.fn.sortOptions = function() {
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
    },
    "consolePolyFill": function() {
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
    },
    "handleNumericFields": function() {
        //display keyboard for numeric fields on mobile devices
        if (Utility.isTouchDevice()) {
            Utility.convertToNumericField($("#date, #year")); /*global Utility convertToNumericField */
        }
    },
    "initValidator": function() {
        Validator.initValidator();
    }
};

