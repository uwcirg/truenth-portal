var URLAuthenticatedModalObj = function() {
    this.URL_AUTH_METHOD_IDENTIFIER = "url_authenticated";
    this.PROMOTE_ENCOUNTER_URL = "/promote-encounter";
    /*
     * initialized modal
     */
    this.initURLAuthenticatedModal = function() {
        $("#urlAuthenticatedModal").modal({
            "show":false,
            "backdrop": "static",
            "focus": true,
            "keyboard": false
        });
    }
    /*
     * set UI element with matching CSS class identifier to trigger modal
     */
    this.setURLAuthenticatedUI = function(data) {
        if (!data || !data.id) {
            return;
        }
        var self = this;
        //call to check if the current user is authenticated via url authenticated method
        $.ajax({
            type: "GET",
            url: "/api/user/" + data.id + "/encounter"
        }).done(function(data) {
            if (!data || !data.auth_method) {
                return;
            }
            if (String(data.auth_method).toLowerCase() === self.URL_AUTH_METHOD_IDENTIFIER) {
                //links needing to redirect to login page 
                $(".portal-weak-auth-disabled").each(function() {
                    $(this).on("click", function(e) {
                        e.preventDefault();
                        var originalHref = $(this).attr("href");
                        var redirectHref = self.PROMOTE_ENCOUNTER_URL+"?next="+originalHref;
                        $(this).attr("href", redirectHref);
                        $("#btnUrlAuthenticatedContinue").attr("href", redirectHref);
                        $("#urlAuthenticatedModal").modal("show");
                    });
                });
                //elements needing to be hidden
                $(".portal-weak-auth-hide").each(function() {
                    $(this).hide();
                });
            }
        });
    };
    this.getCurrentUser = function (callback) {
        callback = callback || function() {};
        $.ajax({
            type: "GET",
            url: "/api/me"
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
    this.init = function() {
        this.initURLAuthenticatedModal();
        this.getCurrentUser(this.setURLAuthenticatedUI);
    };
};
