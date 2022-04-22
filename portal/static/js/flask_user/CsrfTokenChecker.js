/*
 * helper object for checking the validity of CSRF token
 */
var CsrfTokenChecker = window.CsrfTokenChecker = (function() {
    /*
     * object with private properties
     */
    var csrfTokenChecker = function() {
        var tokenLifetimeElement = document.querySelector("#__CRSF_TOKEN_LIFETIME");
        var tokenElement = document.querySelector("#__CRSF_TOKEN");
        var tokenId = tokenElement? tokenElement.value : "";
        this.timerId = 0;
        this.tokenId = tokenId;
        this.modalElementId = "csrfTokenExpiredModal";
        this.timeOnLoadIdentifier = "truenth-TimeOnLoad_"+tokenId;
        this.lifeTime = tokenLifetimeElement ? tokenLifetimeElement.value : 0;
    };
    /*
     * @return stored start date/time in miliseconds
     */
    csrfTokenChecker.prototype.getStorageTimeOnLoad = function() {
        return localStorage.getItem(this.timeOnLoadIdentifier);
    };
    /*
     * set/store start date/time
     */
    csrfTokenChecker.prototype.setStorageTimeOnLoad = function() {
        return localStorage.setItem(this.timeOnLoadIdentifier, Date.now());
    };
    /*
     * clear timer and stored start date/time
     */
    csrfTokenChecker.prototype.clearCheck = function() {
        clearInterval(this.timerId);
        localStorage.removeItem(this.timeOnLoadIdentifier);
    };

    /*
     * create/initialize dialog element
     */
    csrfTokenChecker.prototype.initDialog = function() {
        if (document.querySelector("#"+this.modalElementId)) {
            return;
        }
        var modalDialogElement = (document.createElement("div"));
        modalDialogElement.classList.add("modal-dialog");
        var modalContentElement = (document.createElement("div"));
        modalContentElement.classList.add("modal-content");
        //header
        var modalHeaderElement = document.createElement("div");
        modalHeaderElement.classList.add("modal-header");
        var modalTitleElement = document.createElement("h2");
        modalTitleElement.classList.add("modal-title");
        modalTitleElement.appendChild(document.createTextNode(i18next.t("Login Attempt Expired")));
        modalHeaderElement.appendChild(modalTitleElement);
        //body
        var modalBodyElement = (document.createElement("div"));
        modalBodyElement.classList.add("modal-body");
        //body text
        var modalBodyContentElement = (document.createElement("div"));
        modalBodyContentElement.classList.add("text-center");
        modalBodyContentElement.appendChild(document.createTextNode(i18next.t("Your login attempt timed out. Refreshing the page...")));
        //button
        var modalButtonContainerElement = (document.createElement("div"));
        modalButtonContainerElement.classList.add("text-center");
        var buttonElement = (document.createElement("button"));
        buttonElement.classList.add("btn", "btn-default", "btn-tnth-primary", "btn-lg");
        buttonElement.addEventListener("click", function() {
            location.reload();
        });
        buttonElement.appendChild(document.createTextNode(i18next.t("Refresh Page")));
        modalButtonContainerElement.appendChild(buttonElement);
        modalBodyElement.appendChild(modalBodyContentElement);
        modalBodyElement.appendChild(document.createElement("br"));
        modalBodyElement.appendChild(modalButtonContainerElement);
        modalContentElement.appendChild(modalHeaderElement);
        modalContentElement.appendChild(modalBodyElement);
        modalDialogElement.appendChild(modalContentElement);

        var modalElement = document.createElement("div");
        modalElement.setAttribute("id", this.modalElementId);
        modalElement.setAttribute("tabIndex", -1);
        modalElement.setAttribute("role", "dialog");
        modalElement.classList.add("modal");
        modalElement.classList.add("fade");
        modalElement.append(modalDialogElement);
        
        document.querySelector("body").append(modalElement);
        setTimeout(function() {
            $("#"+this.modalElementId).modal({
                show: false,
                backdrop : "static"
            });
        }, 50);
    };
    /*
     * display dialog
     */
    csrfTokenChecker.prototype.showDialog = function() {
        $("#"+this.modalElementId).modal("show");
    };
    /*
     * check if there is sufficient information, e.g. token lifetime, to determine the validity of the CSRF token
     * @return stored date/time in miliseconds
     */
    csrfTokenChecker.prototype.hasEnoughToProceed = function() {
        return this.lifeTime && this.getStorageTimeOnLoad();
    };
    /*
     * determine if the CSRF token is valid
     * @return boolean true if valid false if not
     */
    csrfTokenChecker.prototype.checkTokenValidity = function() {
        if (!this.tokenId) return false;
        if (!this.hasEnoughToProceed()) return false;
        var endTime = Date.now();
        var startTime = this.getStorageTimeOnLoad();
        var duration = (endTime - parseFloat(startTime)) / 1000; //seconds
        return  duration < this.lifeTime;
    };
    /*
     * determine if the CSRF token is about to expire in a minute
     * @return boolean true if valid false if not
     */
    csrfTokenChecker.prototype.isTokenAboutToExpire = function() {
        if (!this.hasEnoughToProceed()) return false;
        var endTime = Date.now();
        var startTime = this.getStorageTimeOnLoad();
        var duration = (parseFloat(endTime) - parseFloat(startTime)) / 1000; //seconds
        var aboutToExpireTime = this.lifeTime > 95 ? this.lifeTime - 95: this.lifeTime;
        //console.log("duration ? ", duration, " start ", startTime, " end ", endTime)
        return (duration >= aboutToExpireTime);
    };

    /*
     * post groundwork after determined that token is about to expire
     * show dialog
     * refresh page in 3 seconds
     * cleanup - clear timer and stored start time
     */
    csrfTokenChecker.prototype.handleTokenAboutToExpire = function() {
        if (!this.isTokenAboutToExpire()) {
            return;
        }
        this.showDialog();
        setTimeout(function() {
            location.reload();
        }, 3000);
        this.clearCheck();
    };
    /*
     * timer for periodically check if the CSRF token is about to expire
     * applicable to pages that POST form with CSRF token
     */
    csrfTokenChecker.prototype.startTimer = function() {
        if (!this.hasEnoughToProceed()) {
            return;
        }
        if (!$("form[method='POST'] #csrf_token").length) {
            return;
        }
        clearInterval(this.timerId);
        this.timerId = setInterval(function() {
            this.handleTokenAboutToExpire();
        }.bind(this), 15000);
    };
    /*
     * initializing any UI event(s)
     */
    csrfTokenChecker.prototype.initEvents = function() {
        $(window).on("beforeunload", function() {
            this.clearCheck();
        }.bind(this));
    };
    /*
     * method for initializing all that is necessary for the check
     */
    csrfTokenChecker.prototype.init  = function() {
        //clear everything first
        this.clearCheck();
        //set start time if not already
        this.setStorageTimeOnLoad();
        this.initEvents();
        //initialized dialog
        this.initDialog();
        //initial check to see whether CSRF token has expired
        setTimeout(function() {
            this.handleTokenAboutToExpire();
             //start timer if applicable
            this.startTimer();
        }.bind(this), 150);
    };
    return new csrfTokenChecker();
})();
$(document).ready(function() {
    CsrfTokenChecker.init();
});
