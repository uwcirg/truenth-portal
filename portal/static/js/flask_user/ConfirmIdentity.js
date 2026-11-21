import { getSafeLocalUrl } from "../src/modules/Utility.js";

$(document).ready(function() {
    $("#confirmIdentityModal").modal({
        show: true,
        backdrop: "static",
        focus: true,
        keyboard: false
    });

    async function confirmIdentity() {
        const $error = $("#confirmationErrorMessage");

        try {
            await $.ajax({
                type: "POST",
                url: "/api/auditlog",
                data: {
                    message: "User confirmed identity as survey taker"
                }
            });
        } catch (e) {
            console.log("Error ", e);
        }

        const redirectURL = getSafeLocalUrl($("#surveyRedirectURL").val());

        if (!redirectURL) {
            $error.text(i18next.t("Unable to update. System/Server Error."));
            return;
        }

        $error.text("");
        window.location.assign(redirectURL);
    }

    $("#btnConfirmIdentity").on("click", async function() {
        const $button = $(this);

        $button.prop("disabled", true);

        try {
            await confirmIdentity();
        } finally {
            $button.prop("disabled", false);
        }
    });
});
