(function() {
    var CookieMonster = window.CookieMonster = function() {
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
    };
    CookieMonster.prototype.isCookieEnabled = function() {
        var cookieEnabled = navigator.cookieEnabled;
        if (!cookieEnabled) { 
            document.cookie = this.testCookieName;
            cookieEnabled = document.cookie.indexOf(this.testCookieName) !== -1;
        }
        cookieEnabled = this.storageAccessCheck();
        return (cookieEnabled);
    };
    CookieMonster.prototype.storageAccessCheck = function() {
        var accessEnabled = true;
        try {  //workaround for safari - which allows cookie setting even setting blocking cookies in preference
            sessionStorage.setItem("__cookiemonstertest__", "just a storage access test");
            sessionStorage.removeItem("__cookiemonstertest__");
        } catch(e) {
            if (e.name && String(e.name).toLowerCase() === "securityerror") {
                accessEnabled = false;
            }
        }
        return accessEnabled;
    };
    CookieMonster.prototype.restoreVis = function() {
        var loadingElements = document.querySelectorAll("#loadingIndicator, .loading-indicator, .loading-indicator-placeholder"), mainElement = document.getElementById("mainHolder");
        if (mainElement) { mainElement.setAttribute("style", "visibility:visible;-ms-filter:'progid:DXImageTransform.Microsoft.Alpha(Opacity=100)';filter:alpha(opacity=100); -moz-opacity:1; -khtml-opacity:1; opacity:1"); }
        if (!loadingElements) {
            return;
        }
        for (var index = 0; index < loadingElements.length; index++) {
            loadingElements[index].setAttribute("style", "display:none; visibility:hidden;"); 
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
    CookieMonster.prototype.addModalBackdrops = function() {
        if (!document.querySelector(".modal-backdrop")) { //modal darker background
            var backdropElement = document.createElement("div");
            backdropElement.classList.add("modal-backdrop","fade", "in", "cookie-monster-backdrop");
            document.querySelector("body").appendChild(backdropElement);
        }
        if (!document.querySelector(".cookie-monster-modal-backdrop-cover")) { //modal lighter background - should cover any content from affected page if need to
            var backdropCoverElement = document.createElement("div");
            backdropCoverElement.classList.add("cookie-monster-modal-backdrop-cover");
            document.querySelector("body").appendChild(backdropCoverElement);
        }
    };
    CookieMonster.prototype.initModalElementEvents =  function() {
        var tryAgainElement = document.getElementById("btnCookieTryAgain");
        if (tryAgainElement) {
            tryAgainElement.addEventListener("click", function() {
                window.location.reload();
            });
        }
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
        }
        this.addModalBackdrops();
        this.initModalElementEvents();
    };
    CookieMonster.prototype.checkSuccessTargetRedirect = function() {
        var targetRedirectElement = document.getElementById("cookieCheckTargetUrl");
        if (targetRedirectElement && targetRedirectElement.value) {
            window.location.replace(targetRedirectElement.value);
        }
    };
    CookieMonster.prototype.initCheckAndPostProcesses = function() {
        if (document.getElementById("manualCheckCookieSetting")) { //if manual check is on, don't initiate autocheck
            return false;
        }
        if (this.isCookieEnabled()) {
            this.deleteTestCookie();
            this.checkSuccessTargetRedirect();
            return true;
        }
        this.initModal();
        var self = this;
        setTimeout(function() {
            self.restoreVis();
        }, 150);
    };
    window.onload = function() {
        var cookieEvil = new CookieMonster();
        cookieEvil.initCheckAndPostProcesses();
    };
}) ();
