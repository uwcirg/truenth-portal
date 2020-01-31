(function() { /* global $ i18next */
    var RegisterObj = window.RegisterObj = function() {
        this.init = function() {
            var self = this;
            $(document).ready(function(){
                self.initVis();
                self.initFieldEvents();
            });
        };
        this.initVis = function() {
            // Need to properly form attribute name
            $("[data-match_error]").each(function(){
                $(this).attr("data-match-error", $(this).attr("data-match_error"));
            });
            $("input[type='submit']").addClass("disabled");
        };
        this.checkValidity = function() {
            var allowed = true;
            ["#email", "#password", "#retype_password"].forEach(function(fieldId) {
                if (!$(fieldId).val()) {
                    allowed = false;
                }
            });
            if (allowed) {
                allowed = !($(".form-group.has-error").length);
            }
            if (allowed) {
                $("input[type='submit']").removeClass("disabled");
            } else {
                $("input[type='submit']").addClass("disabled");
            }
        };
        this.initFieldEvents = function() {
            var self = this;
            $("input.input-field").each(function() {
                $(this).on("change", function() {
                    setTimeout(function() { self.checkValidity(); }, 350);
                });
                $(this).on("keyup", function(e) {
                    e.preventDefault();
                    if ($(this).val()) {
                        $(this).closest(".form-group").removeClass("has-error");
                    }
                    setTimeout(function() { self.checkValidity(); } , 350);
                });
            });
            $("#retype_password").on("keyup change", function() {
                if (!$(this).val()) {
                    $("#errorretype_password").addClass("has-error").text(i18next.t("Please re-type your password."));
                } else {
                    $("#errorretype_password").text("").removeClass("has-error");
                    self.checkValidity();
                }
            });
            $("#password").on("keyup", function() {
                self.checkValidity(); //check field validity
            });
            $("#email").on("change", function() {
                $("#erroremail").text("");
            });
        };
    };
    (new RegisterObj()).init();
})();
