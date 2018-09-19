$("document").ready(function() {
    DELAY_LOADING = true; /* global DELAY_LOADING */
    setTimeout(function() {
        DELAY_LOADING = false;
        showMain(); /* global showMain */
        hideLoader(true); /* global hideLoader */
    }, 150);
    if (typeof sessionStorage !== "undefined") {
        sessionStorage.clear();
    }
    $("#email").on("focus touchstart", function() {
        $(this).removeAttr("readonly");
    });
    $("#email, #password").on("change", function() {
        if ($(this).val()) {
            $("#btnLogin").attr("disabled", false).removeClass("disabled");
            return;
        }
        $("#btnLogin").attr("disabled", true).addClass("disabled");
    });
});

