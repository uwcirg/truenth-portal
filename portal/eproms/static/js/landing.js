$(document).ready(function() {
    DELAY_LOADING = true; /* global DELAY_LOADING */
    setTimeout(function() {
        DELAY_LOADING = false;
        showMain(); /* global showMain */
        hideLoader(true); /* global hideLoader */
    }, 150);
    if (typeof sessionStorage !== "undefined") {
        sessionStorage.clear();
    }
    $("#email, #password").on("keyup", function() {
        if ($(this).val()) {
            $("#btnLogin").attr("disabled", false).removeClass("disabled");
            return;
        }
        $("#btnLogin").attr("disabled", true).addClass("disabled");
    });
    setTimeout(function() { 
        $("#email").val(""); //clear fields on initial load
        $("#password").val("");
    }, 300);
});

