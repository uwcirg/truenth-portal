(function() {
    var CookieMonster = window.CookieMonster = function() {
        this.modalElementId = "modalCookieEnableWarning";
        this.testCookieName = "testCookieMonster";
        this.resizeTimer = 0;
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
        //browsers variations here - safari allowed setting of cookies even when enabling cookie is turned off, but raise runtime security error
        var didRaiseError = this.storageSecurityAccessErrorCheck();
        if (didRaiseError) {
            cookieEnabled = false;
        }
        return (cookieEnabled);
    };
    CookieMonster.prototype.storageSecurityAccessErrorCheck = function() {
        var hasError = false;
        try {
            sessionStorage.setItem("__cookiemonstertest__", "just a storage access test");
            sessionStorage.removeItem("__cookiemonstertest__");
        } catch(e) {
            if (e.name && String(e.name).toLowerCase() === "securityerror") {
                hasError = true;
            }
        }
        return hasError;
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
    CookieMonster.prototype.clearModal = function() {
        var modalElement = document.getElementById(this.modalElementId);
        if (!modalElement) {
            return;
        }
        modalElement.style.display = "none";
        this.removeModalBackdrops();
    };
    CookieMonster.prototype.removeModalBackdrops = function() {
        var modalBackdropElement = document.querySelector(".cookie-monster-backdrop");
        if (modalBackdropElement) {
            modalBackdropElement.parentNode.remove();
        }
        var modalBackdropCoverElement = document.querySelector(".cookie-monster-modal-backdrop-cover");
        if (modalBackdropCoverElement) {
            modalBackdropCoverElement.parentNode.remove();
        }
    };
    CookieMonster.prototype.addModalBackdrops = function() {
        if (!document.querySelector(".cookie-monster-backdrop")) { //modal darker background
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
    CookieMonster.prototype.positionModal = function() {
        var dialogElement =  document.querySelector("#" + this.modalElementId + " .modal-dialog");
        if (!dialogElement) {
            return;
        }
        var domRect = dialogElement.getBoundingClientRect();
        if (!domRect || !domRect.width || !domRect.height) {
            return;
        }
        dialogElement.style.position = "absolute";
        dialogElement.style.left = ((window.innerWidth - domRect.width) / 2) + "px";
        dialogElement.style.top = ((window.innerHeight - domRect.height) / 3) + "px";
    };
    CookieMonster.prototype.initModal = function() {
        if (getUrlParameter("redirect")) { /*global getUrlParameter */
            return false; //do not init modal if this is coming from a redirect as to privacy page
        }
        var modalElement = document.getElementById(this.modalElementId);
        if (!modalElement) {
            return;
        }
        this.addModalBackdrops();
        this.initModalElementEvents();
        modalElement.classList.add("in");
        document.querySelector("body").classList.add("modal-open");
        modalElement.style.display = "block";
        this.positionModal();
        var self = this;
        window.addEventListener("resize", function() {
            this.clearTimeout(self.resizeTimer);
            setTimeout(function() {
                self.positionModal();
            }, 50);
        });
    };
    CookieMonster.prototype.checkSuccessTargetRedirect = function() {
        var targetRedirectElement = document.getElementById("cookieCheckTargetUrl");
        if (targetRedirectElement && targetRedirectElement.value) {
            window.location.replace(targetRedirectElement.value);
            return true;
        }
        return false;
    };
    CookieMonster.prototype.onSuccessCheck = function() {
        this.deleteTestCookie();
        var hasTargetRedirect = this.checkSuccessTargetRedirect();
        if (!hasTargetRedirect) {
            this.restoreVis();
            this.clearModal();
            var defaultContentElement = document.querySelector(".default-content");
            if (defaultContentElement) {
                defaultContentElement.classList.remove("tnth-hide");
            }
        }
    };
    CookieMonster.prototype.onFailCheck = function() {
        var bodyElement = document.querySelector("body");
        if (bodyElement) {
            bodyElement.classList.add("browser-cookie-disabled");
        }
        this.initModal();
        var self = this;
        setTimeout(function() {
            self.restoreVis();
        }, 150);
    };
    CookieMonster.prototype.initCheckAndPostProcesses = function() {
        if (document.getElementById("manualCheckCookieSetting")) { //if manual check is on, don't initiate autocheck
            return false;
        }
        if (this.isCookieEnabled()) {
            this.onSuccessCheck();
            return true;
        }
        this.onFailCheck();

    };
    window.onload = function() {
        var cookieEvil = new CookieMonster();
        cookieEvil.initCheckAndPostProcesses();
    };
}) ();

