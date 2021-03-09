import Utility from "./modules/Utility.js";
$(document).ready(function() {
    $("body").attr("class", "page-home");
    Utility.handlePostLogout(); /*global Utility handlePostLogout */
    if ($("#initLoginModal").val() === "true") {
        $("#modal-login-register").modal("show");
    }
    var sessionStorageDefined = (typeof sessionStorage != "undefined");
    if (sessionStorageDefined) {
        sessionStorage.clear();
    }
    if (/applewebkit/i.test(String(navigator.userAgent)) &&
        /ipad/i.test(String(navigator.userAgent))) {
        window.kp_Browser_clearCookies();
    }
    $("#naModal").modal({
        show: true,
        backdrop: "static"
    });
});

