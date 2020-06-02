$(document).ready(function() {
    $("#confirmIdentityModal").modal({
        "show":true,
        "backdrop": "static",
        "focus": true,
        "keyboard": false
    });
    $("#btnConfirmIdentity").on("click", function(e) {
        e.stopPropagation();
        /*
         * record an audit event before redirecting user to survey
         */
        $.ajax({
            type: "POST",
            url: "/api/auditlog",
            data: {
                "message": "User confirmed identity as survey taker"
            },
            async: false
        }).done(function(data) {
            $("#confirmationErrorMessage").html("");
            window.location = $("#surveyRedirectURL").val();
        }).fail(function() {
            $("#confirmationErrorMessage").html(i18next.t("Unable to update. System/Server Error."));
        });
    });
});
