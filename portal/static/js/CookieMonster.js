(function() {
    var CookieMonster = window.CookieMonster = function(selectorsToDisable) {
        this.selectorsToDisable = selectorsToDisable;
        this.defaultSelectorsToDisable = "[data-target='#modal-login'], [data-target='#modal-register'], .btn-social";
        this.testCookieName = "testCookieMonster";
    };
    CookieMonster.prototype.getSelectorsToDisable = function() {
        return this.selectorsToDisable || this.defaultSelectorsToDisable;
    };
    CookieMonster.prototype.deleteTestCookie = function() {
        var d = new Date();
        d.setTime(d.getTime() - (1000*60*60*24)); //set the time to the past. 1000 milliseonds = 1 second
        var expires = "expires=" + d.toGMTString(); //compose the expirartion date
        window.document.cookie = this.testCookieName+"="+"; "+expires;//set the cookie with name and the expiration date
    }
    CookieMonster.prototype.isCookieEnabled = function() {
        var cookieEnabled = navigator.cookieEnabled;
        if (!cookieEnabled) { 
            document.cookie = this.testCookieName;
            cookieEnabled = document.cookie.indexOf(this.testCookieName) !== -1;
        }
        try {  //workaround for safari - which allows cookie setting even setting blocking cookies in preference
            sessionStorage.setItem("__cookiemonstertest__");
            sessionStorage.removeItem("__cookiemonstertest__");
        } catch(e) {
            if (e.name && String(e.name).toLowerCase() === "securityerror") {
                cookieEnabled = false;
            }
        }
        if (cookieEnabled) {
            this.deleteTestCookie();
        }
        return (cookieEnabled);
    };
    CookieMonster.prototype.restoreVis = function() {
        var loadingElements = document.querySelectorAll("#loadingIndicator, .loading-indicator, .loading-indicator-placeholder"), mainElement = document.getElementById("mainHolder");
        if (loadingElements) {
            for (var index = 0; index < loadingElements.length; index++) {
                loadingElements[index].setAttribute("style", "display:none; visibility:hidden;"); 
            }
        }
        if (mainElement) { mainElement.setAttribute("style", "visibility:visible;-ms-filter:'progid:DXImageTransform.Microsoft.Alpha(Opacity=100)';filter:alpha(opacity=100); -moz-opacity:1; -khtml-opacity:1; opacity:1"); }
    };
    CookieMonster.prototype.disableElements = function() {
        var selectors = document.getElementById("modalCookieEnableWarning").getAttribute("data-disable-selectors") || this.getSelectorsToDisable();
        selectors += (selectors?",":"") + "form";
        var el = document.querySelectorAll(selectors);
        var childElements, self = this;
        if (el) {
            for (var index = 0; index < el.length; index++) {
                self.setElementVis(el[index]);
                childElements = el[index].querySelectorAll("a, .btn, button, input[type='submit'], .button");
                if (childElements) {
                    for (var iindex = 0; iindex < childElements.length; iindex++) {
                        self.setElementVis(childElements[iindex]);
                    }
                }
            }
        }
    };
    CookieMonster.prototype.setElementVis = function(el) {
        if (!el) {
            return;
        }
        el.classList.add("disabled", "cookie-disabled");
        el.style.zIndex = -1;
        el.removeAttribute("data-toggle");
        el.setAttribute("disabled", "disabled");
    };
    CookieMonster.prototype.initModal = function() {
        if (getUrlParameter("redirect")) { /*global getUrlParameter */
            return false; //do not init modal if this is coming from a redirect as to privacy page
        }
        var modalElement = document.getElementById("modalCookieEnableWarning");
        if (modalElement) {
            modalElement.classList.add("in");
            document.querySelector("body").classList.add("modal-open");
            modalElement.style.display = "block";
            if (!document.querySelector(".modal-backdrop")) {
                var backdropElement = document.createElement("div");
                backdropElement.classList.add("modal-backdrop","fade", "in", "cookie-monster-backdrop");
                document.querySelector("body").appendChild(backdropElement);
            }
            if (!document.querySelector(".cookie-monster-modal-backdrop-cover")) {
                var backdropCoverElement = document.createElement("div");
                backdropCoverElement.classList.add("cookie-monster-modal-backdrop-cover");
                document.querySelector("body").appendChild(backdropCoverElement);
            }
        }
        var tryAgainElement = document.getElementById("btnCookieTryAgain");
        if (tryAgainElement) {
            tryAgainElement.addEventListener("click", function() {
                window.location.reload();
            });
        }
        var closeElements = document.querySelectorAll("#modalCookieEnableWarning [data-dismiss='modal']");
        if (closeElements && closeElements.length) {
            for (var index = 0; index < closeElements.length; index++) {
                closeElements[index].addEventListener("click", function() {
                    var backdropElement = document.querySelector(".modal-backdrop");
                    if (backdropElement) {
                        backdropElement.parentNode.removeChild(backdropElement);
                    }
                    document.querySelector("body").classList.remove("modal-open");
                    document.getElementById("modalCookieEnableWarning").classList.remove("in");
                    document.getElementById("modalCookieEnableWarning").style.display = "none";
                });
            }
        }
    };
    CookieMonster.prototype.checkSuccessTargetRedirect = function() {
        var targetRedirectElement = document.getElementById("cookieCheckTargetUrl");
        if (targetRedirectElement && targetRedirectElement.value) {
            window.location.replace(targetRedirectElement.value);
        }
    };
    CookieMonster.prototype.checkCookiesSetting = function() {
        if (document.getElementById("manualCheckCookieSetting")) { //if manual check is on, don't initiate autocheck
            return false;
        }
        window.__PORTAL_COOKIE_DISABLED = !this.isCookieEnabled();
        if (!window.__PORTAL_COOKIE_DISABLED) {
            this.checkSuccessTargetRedirect();
            return true;
        }
        this.disableElements();
        this.initModal();
        var self = this;
        setTimeout(function() {
            self.restoreVis();
        }, 150);
    };
    window.onload = function() {
        var cookieEvil = new CookieMonster();
        cookieEvil.checkCookiesSetting();
    };
}) ();



