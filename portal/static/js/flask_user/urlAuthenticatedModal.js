/* 
 * see urlAuthenticatedLoginModal macro in /templates/flask_user/_macros for modal HTML
 */
function URLAuthenticatedModalObj() {
    this.URL_AUTH_METHOD_IDENTIFIER = "url_authenticated";
    this.MODAL_ELEMENT_IDENTIFIER = "urlAuthenticatedModal";
};

/*
 * return Portal base URL, important to affix when calling api from intervention
 */
URLAuthenticatedModalObj.prototype.getPortalBaseURL = function() {
    return $("#"+this.MODAL_ELEMENT_IDENTIFIER).attr("data-ref-url") || (window.location.protocol + "//" + window.location.host);
}

/*
 * return URL for promoting encounter
 */
URLAuthenticatedModalObj.prototype.getPromoteEncounterURL = function() {
    return this.getPortalBaseURL() + "/promote-encounter";
}

/*
 * initialized login prompt modal
 */
URLAuthenticatedModalObj.prototype.initURLAuthenticatedModal = function() {
    $("#"+this.MODAL_ELEMENT_IDENTIFIER).modal({
        "show":false,
        "backdrop": "static",
        "focus": true,
        "keyboard": false
    });
};

/*
 *  get the provided user encounter auth method, usually passed in as a parameter by the caller of module
 */
URLAuthenticatedModalObj.prototype.getProvidedAuthMethod = function() {
    return $("#"+this.MODAL_ELEMENT_IDENTIFIER).attr("data-auth-method");
};

/*
 * update UI state and attribute, e.g. href, when encounter auth method is url-authenticated
 */
URLAuthenticatedModalObj.prototype.setUI = function() {
    var self = this;
    //links needing to redirect to login page
    $("body").delegate(".portal-weak-auth-disabled", "click", function(e) {
        e.preventDefault();
        e.stopPropagation();
        var originalHref = $(this).attr("href");
        if (! /next\=/.test(originalHref)) {
            var redirectHref = self.getPromoteEncounterURL()+"?next="+originalHref;
            $(this).attr("href", redirectHref);
            $("#btnUrlAuthenticatedContinue").attr("href", redirectHref);
        }
        $(".modal").modal("hide");
        $("#"+self.MODAL_ELEMENT_IDENTIFIER).modal("show");
    })
    //elements needing to be hidden
    $(".portal-weak-auth-hide").each(
        function() {
            $(this).hide();
        }
    );
}

/*
 * check user current encounter and set UI element with matching CSS class identifier to trigger the login modal when * needed
 */
URLAuthenticatedModalObj.prototype.handleURLAuthenticatedUI = function() {
    var providedAuthMethod = this.getProvidedAuthMethod();
    /*
     * if user encounter auth method is known then just set state of relevant UI elements
     */
    if (String(providedAuthMethod).toLowerCase() === this.URL_AUTH_METHOD_IDENTIFIER) {
        this.setUI();
        return;
    }
    var self = this;
    this.getCurrentUser(function(data) {
        if (!data || !data.id) {
            return;
        }
        //call to check if the current user is authenticated via url authenticated method
        $.ajax({
            type: "GET",
            url: self.getPortalBaseURL() + "/api/user/" + data.id + "/encounter"
        }).done(function(data) {
            if (!data || !data.auth_method) {
                return;
            }
            if (String(data.auth_method).toLowerCase() === self.URL_AUTH_METHOD_IDENTIFIER) {
                self.setUI();
            }
        });
    });
};

/*
 * get current user information
 * @param callback function to execute when data is returned from API
 */
URLAuthenticatedModalObj.prototype.getCurrentUser = function(callback) {
    callback = callback || function() {};
    $.ajax({
        type: "GET",
        url: this.getPortalBaseURL() + "/api/me"
    }).done(function(data) {
        if (!data || !data.id) {
            callback({error: true});
            return;
        }
        callback(data);
    }).fail(function() {
        callback({error: true});
    });
};

/*
 * initializing object
 * this will initialize the login modal and set UI states/events appropiately
 */
URLAuthenticatedModalObj.prototype.init = function() {
    this.initURLAuthenticatedModal();
    this.handleURLAuthenticatedUI();
};
