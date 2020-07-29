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
 * set UI element with matching CSS class identifier to trigger the login modal
 */
URLAuthenticatedModalObj.prototype.setURLAuthenticatedUI = function() {
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
                //links needing to redirect to login page
                $("body").delegate(".portal-weak-auth-disabled", "click", function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    var originalHref = $(this).attr("href");
                    var redirectHref = self.getPromoteEncounterURL()+"?next="+originalHref;
                    $(this).attr("href", redirectHref);
                    $("#btnUrlAuthenticatedContinue").attr("href", redirectHref);
                    $("#"+self.MODAL_ELEMENT_IDENTIFIER).modal("show");
                })
                //elements needing to be hidden
                $(".portal-weak-auth-hide").each(
                    function() {
                        $(this).hide();
                    }
                );
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
    console.log("PORTAL BASE ? ", this.getPortalBaseURL())
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
    this.setURLAuthenticatedUI();
};
