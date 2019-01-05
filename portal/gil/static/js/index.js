$(document).ready(function() {
    $("body").attr("class", "page-home");
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
});
